"""Fase 11.3: fotos sueltas completas (single_fit = "fit") y fondo desenfocado."""
import io
import unittest

from fastapi.testclient import TestClient
from PIL import Image as PILImage

from app.main import app as fastapi_app
from app.models.schemas import Tv, TvContent
from app.services import composition
from app.services.composition import BACKGROUND, FRAME_SIZE, MARGIN, layout
from app.services.sync import sync_tv
from tests.test_composition import CompositionDbMixin
from tests.test_date_stamp import RecordingClient

RED, BLUE = (220, 30, 30), (30, 30, 220)


def near(color, ref, tol=30):
    return all(abs(a - b) <= tol for a, b in zip(color, ref))


class SingleFitTest(CompositionDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.album.composition_mode = "off"
        self.album.single_fit = "fit"
        self.tv = Tv(name="Frame A", host="198.51.100.1", paired=True)
        self.db.add(self.tv)
        self.db.commit()
        self.client = RecordingClient()
        self.photos({"v.jpg": (900, 1600, RED), "h.jpg": (1200, 900, BLUE)})

    def sync(self):
        return sync_tv(self.db, self.tv, self.album, self.client)

    def uploads(self):
        rows = self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).all()
        return {self.db.get(type(self.image("v.jpg")), r.image_id).key: r for r in rows}

    def picture(self, row):
        return PILImage.open(io.BytesIO(self.client.data[row.content_id])).convert("RGB")

    def test_vertical_shown_whole_and_landscape_still_fills(self):
        self.assertEqual(self.sync().uploaded, 2)
        rows = self.uploads()
        self.assertEqual(rows["v.jpg"].render_sig, "fit2:0.15:paper")
        self.assertIsNone(rows["h.jpg"].render_sig)  # 4:3 pierde el 25 %: sigue llenando la pantalla
        vertical = self.picture(rows["v.jpg"])
        self.assertEqual(vertical.size, FRAME_SIZE)
        (x, y, w, h), = layout("single", [900 / 1600])
        self.assertTrue(near(vertical.getpixel((x + w // 2, y + h // 2)), RED))
        self.assertTrue(near(vertical.getpixel((x // 2, FRAME_SIZE[1] // 2)), BACKGROUND, 3))
        self.assertTrue(near(self.picture(rows["h.jpg"]).getpixel((5, 5)), BLUE))

    def test_switching_back_to_crop_replaces_safely(self):
        self.sync()
        old = self.uploads()["v.jpg"].content_id
        self.album.single_fit = "crop"
        self.db.commit()
        result = self.sync()
        self.assertEqual((result.uploaded, result.deleted), (1, 1))
        row = self.uploads()["v.jpg"]
        self.assertIsNone(row.render_sig)
        self.assertNotIn(old, self.client.photos)
        self.assertTrue(near(self.picture(row).getpixel((5, 5)), RED))

    def test_blur_background_uses_the_photo(self):
        self.album.background = "blur"
        self.db.commit()
        self.sync()
        row = self.uploads()["v.jpg"]
        self.assertEqual(row.render_sig, "fit2:0.15:blur")
        side = self.picture(row).getpixel((MARGIN, FRAME_SIZE[1] // 2))
        # Rojo oscurecido, no el papel
        self.assertGreater(side[0], side[2] + 60)
        self.assertFalse(near(side, BACKGROUND))


class BlurPageTest(CompositionDbMixin, unittest.TestCase):
    def test_page_background_and_new_revision(self):
        self.photos({"a.jpg": (900, 1600, RED), "b.jpg": (900, 1600, RED)})
        page = composition.active_pages(self.db, self.album.id)[0]
        self.assertEqual((page.template, page.revision), ("pair_v", 1))
        self.album.background = "blur"
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        self.db.refresh(page)
        self.assertEqual((page.revision, page.status), (2, "ready"))
        with PILImage.open(composition.page_file(self.album.id, page.id, page.revision)) as img:
            corner = img.convert("RGB").getpixel((10, 10))
        self.assertGreater(corner[0], corner[2] + 60)


class FitApiTest(CompositionDbMixin, unittest.TestCase):
    def test_defaults_and_validation(self):
        client = TestClient(fastapi_app)
        created = client.post("/api/albums", json={"name": "Nuevo"}).json()
        try:
            self.assertEqual((created["background"], created["single_fit"]), ("paper", "crop"))
            for body, code in (({"background": "neon"}, "invalid_background"),
                               ({"single_fit": "stretch"}, "invalid_single_fit")):
                resp = client.patch(f"/api/albums/{created['id']}", json=body)
                self.assertEqual((resp.status_code, resp.json()["detail"]), (400, code))
            patched = client.patch(f"/api/albums/{created['id']}",
                                   json={"background": "blur", "single_fit": "fit"}).json()
            self.assertEqual((patched["background"], patched["single_fit"]), ("blur", "fit"))
        finally:
            client.delete(f"/api/albums/{created['id']}")


if __name__ == "__main__":
    unittest.main()
