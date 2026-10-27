"""Fase 11.4: detección del sujeto con Gemini y recortes orientados."""
import base64
import io
import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from app.main import app as fastapi_app
from app.models.schemas import Tv, TvContent
from app.services import composition, subject_ai
from app.services.composition import centering
from app.services.sync import sync_tv
from tests.test_composition import CompositionDbMixin
from tests.test_date_stamp import RecordingClient, dated_photo

KEY = "AIzaTestKey_0123456789abcdef"
RED, BLUE = (220, 30, 30), (30, 30, 220)


def gemini_reply(subjects):
    text = json.dumps({"subjects": subjects})
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class AiConfigMixin:
    def setUp(self):
        super().setUp()
        self.reset_ai()

    def tearDown(self):
        self.reset_ai()
        super().tearDown()

    @staticmethod
    def reset_ai():
        for path in (subject_ai._config_path(), subject_ai._usage_path()):
            path.unlink(missing_ok=True)


class ParseAndCenteringTest(unittest.TestCase):
    def test_union_of_valid_boxes(self):
        data = gemini_reply([{"label": "dog", "box_2d": [100, 200, 500, 400]},
                             {"label": "cat", "box_2d": [300, 100, 900, 300]},
                             {"label": "bad", "box_2d": [600, 600, 500, 700]}])
        self.assertEqual(subject_ai.parse_boxes(data), [0.1, 0.1, 0.4, 0.9])

    def test_empty_and_malformed(self):
        self.assertIsNone(subject_ai.parse_boxes(gemini_reply([])))
        for data in ({}, {"candidates": [{"content": {"parts": [{"text": "no json"}]}}]},
                     gemini_reply([{"box_2d": [1, 2]}])):
            with self.assertRaises(subject_ai.SubjectError) as ctx:
                subject_ai.parse_boxes(data)
            self.assertEqual(str(ctx.exception), "gemini_response_invalid")

    def test_window_keeps_the_subject(self):
        # Vertical 3:4 recortada a 16:9: queda visible el 42 % del alto
        self.assertEqual(centering(None, 0.75, 16 / 9), (0.5, 0.5))
        _, cy = centering([0.3, 0.05, 0.7, 0.3], 0.75, 16 / 9)
        self.assertEqual(cy, 0.0)
        _, cy = centering([0.3, 0.7, 0.7, 0.95], 0.75, 16 / 9)
        self.assertEqual(cy, 1.0)
        # Sujeto más alto que la ventana: se conserva su parte superior (las cabezas)
        visible = 0.75 / (16 / 9)
        _, cy = centering([0.3, 0.2, 0.7, 0.9], 0.75, 16 / 9)
        self.assertAlmostEqual(cy * (1 - visible), 0.2 - composition.SUBJECT_PAD, places=6)
        # Horizontal recortada por los lados, sujeto a la derecha
        cx, cy = centering([0.8, 0.2, 0.95, 0.8], 16 / 9, 0.75)
        self.assertEqual((cx, cy), (1.0, 0.5))


class ClientTest(AiConfigMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.photo = Path(self.tmp.name) / "p.jpg"
        dated_photo(self.photo, (3000, 4000), taken="2021:04:24 15:50:59")
        self.requests = []

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def client(self, status=200, body=None):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(status, json=body if body is not None else gemini_reply(
                [{"label": "dog", "box_2d": [100, 250, 600, 750]}]))
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_config_validation_and_public_view(self):
        self.assertFalse(subject_ai.configured())
        for kwargs, code in (({"api_key": "short"}, "gemini_key_invalid"), ({"model": "../x"}, "invalid_gemini_model"),
                             ({"max_calls_per_day": 0}, "invalid_gemini_limit")):
            with self.assertRaises(ValueError) as ctx:
                subject_ai.save_config(**kwargs)
            self.assertEqual(str(ctx.exception), code)
        subject_ai.save_config(api_key=KEY)
        view = subject_ai.public_view()
        self.assertEqual((view["configured"], view["key_hint"], view["model"]), (True, "cdef", subject_ai.DEFAULT_MODEL))
        self.assertNotIn(KEY, json.dumps(view))
        subject_ai.save_config(api_key="")
        self.assertFalse(subject_ai.configured())

    def test_request_sends_reduced_photo_without_metadata(self):
        subject_ai.save_config(api_key=KEY, model="gemini-test")
        with self.client() as client:
            box = subject_ai.detect(self.photo, client)
        self.assertEqual(box, [0.25, 0.1, 0.75, 0.6])
        request = self.requests[0]
        self.assertEqual((request.url.host, request.url.path),
                         (subject_ai.API_HOST, "/v1beta/models/gemini-test:generateContent"))
        self.assertEqual(request.headers["x-goog-api-key"], KEY)
        self.assertNotIn(KEY, str(request.url))
        body = json.loads(request.content)
        sent = PILImage.open(io.BytesIO(base64.b64decode(body["contents"][0]["parts"][0]["inline_data"]["data"])))
        self.assertLessEqual(max(sent.size), subject_ai.SEND_SIZE)
        self.assertEqual(dict(sent.getexif()), {})
        self.assertEqual(subject_ai.calls_today(), 1)

    def test_errors_and_daily_limit(self):
        with self.assertRaises(subject_ai.SubjectError) as ctx:
            subject_ai.detect(self.photo)
        self.assertEqual(str(ctx.exception), "gemini_key_missing")
        subject_ai.save_config(api_key=KEY, max_calls_per_day=5)
        for status, code in ((401, "gemini_key_invalid"), (429, "gemini_quota_exceeded"),
                             (503, "gemini_unreachable"), (400, "gemini_response_invalid")):
            with self.client(status, {}) as client, self.assertRaises(subject_ai.SubjectError) as ctx:
                subject_ai.detect(self.photo, client)
            self.assertEqual(str(ctx.exception), code)
        with self.client() as client:
            subject_ai.detect(self.photo, client)
            with self.assertRaises(subject_ai.SubjectError) as ctx:
                subject_ai.detect(self.photo, client)
        self.assertEqual(str(ctx.exception), "gemini_quota_exceeded")
        self.assertEqual(len(self.requests), 5)  # la sexta no llega a enviarse


class DetectionFlowTest(AiConfigMixin, CompositionDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        subject_ai.save_config(api_key=KEY)
        self.album.composition_mode = "off"
        self.album.subject_detection = True
        self.tv = Tv(name="Frame A", host="198.51.100.1", paired=True)
        self.db.add(self.tv)
        self.db.commit()
        self.client = RecordingClient()
        # Vertical con el sujeto (rojo) arriba: el recorte al centro lo perdería
        img = PILImage.new("RGB", (900, 1600), BLUE)
        img.paste(RED, (0, 0, 900, 400))
        self.root.joinpath("v.jpg").parent.mkdir(parents=True, exist_ok=True)
        img.save(self.root / "v.jpg", "JPEG")
        self.calls = []

    def fake_detect(self, result):
        def detect(path, client=None):
            self.calls.append(path.name)
            if isinstance(result, Exception):
                raise result
            return result
        return patch.object(subject_ai, "detect", side_effect=detect)

    def uploaded(self):
        row = self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).one()
        return row, PILImage.open(io.BytesIO(self.client.data[row.content_id])).convert("RGB")

    def test_crop_follows_the_subject_and_is_cached(self):
        with self.fake_detect([0.1, 0.02, 0.9, 0.24]):
            self.rescan()
            composition.process_album(self.db, self.album.id)
        self.assertEqual(self.calls, ["v.jpg"])  # una sola consulta por versión de la foto
        img = self.image("v.jpg")
        self.assertEqual(json.loads(img.subject_box), [0.1, 0.02, 0.9, 0.24])
        self.sync_tv()
        row, picture = self.uploaded()
        self.assertIn("subj=0.100,0.020,0.900,0.240", row.render_sig)
        self.assertGreater(picture.getpixel((1920, 60))[0], 150)  # arriba se ve el sujeto rojo

    def test_waits_for_detection_then_continues_centered_on_failure(self):
        self.rescan_only()
        self.assertFalse(composition.effective_output(self.db, self.album).current)
        with self.fake_detect(subject_ai.SubjectError("gemini_unreachable")):
            composition.process_album(self.db, self.album.id)
        self.db.refresh(self.album)
        self.assertEqual(self.album.subject_error, "gemini_unreachable")
        self.assertTrue(composition.effective_output(self.db, self.album).current)
        self.sync_tv()
        row, picture = self.uploaded()
        self.assertEqual(row.render_sig, None)
        self.assertGreater(picture.getpixel((1920, 1080))[2], 150)  # al centro: azul

    def test_invalid_answer_for_one_photo_is_not_retried(self):
        self.rescan_only()
        with self.fake_detect(subject_ai.SubjectError("gemini_response_invalid")):
            composition.process_album(self.db, self.album.id)
            composition.process_album(self.db, self.album.id)
        self.assertEqual(self.calls, ["v.jpg"])
        self.assertEqual(self.image("v.jpg").subject_box, "")
        self.assertIsNone(self.album.subject_error)

    def test_disabled_album_sends_nothing(self):
        self.album.subject_detection = False
        self.db.commit()
        with self.fake_detect([0, 0, 1, 1]):
            self.rescan()
        self.assertEqual(self.calls, [])

    def rescan_only(self):
        from app.services.albums import rescan_source
        rescan_source(self.db, self.source)

    def sync_tv(self):
        return sync_tv(self.db, self.tv, self.album, self.client)


class SettingsApiTest(AiConfigMixin, CompositionDbMixin, unittest.TestCase):
    def test_settings_and_album_option(self):
        client = TestClient(fastapi_app)
        album = client.post("/api/albums", json={"name": "Nuevo"}).json()
        try:
            self.assertFalse(album["subject_detection"])
            resp = client.patch(f"/api/albums/{album['id']}", json={"subject_detection": True})
            self.assertEqual((resp.status_code, resp.json()["detail"]), (400, "gemini_key_missing"))
            self.assertFalse(client.get("/api/meta").json()["ai"])
            resp = client.put("/api/settings/ai", json={"api_key": "x"})
            self.assertEqual(resp.json()["detail"], "gemini_key_invalid")
            view = client.put("/api/settings/ai", json={"api_key": KEY, "max_calls_per_day": 50}).json()
            self.assertEqual((view["configured"], view["key_hint"], view["max_calls_per_day"]), (True, "cdef", 50))
            self.assertNotIn(KEY, json.dumps(client.get("/api/settings/ai").json()))
            self.assertTrue(client.get("/api/meta").json()["ai"])
            patched = client.patch(f"/api/albums/{album['id']}", json={"subject_detection": True}).json()
            self.assertTrue(patched["subject_detection"])
            with patch.object(subject_ai, "test_connection", side_effect=subject_ai.SubjectError("gemini_key_invalid")):
                resp = client.post("/api/settings/ai/test")
            self.assertEqual((resp.status_code, resp.json()["detail"]), (400, "gemini_key_invalid"))
            with patch.object(subject_ai, "test_connection"):
                self.assertTrue(client.post("/api/settings/ai/test").json()["ok"])
        finally:
            client.delete(f"/api/albums/{album['id']}")


if __name__ == "__main__":
    unittest.main()
