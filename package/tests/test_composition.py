import random
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import create_engine, inspect, text

import app.main  # noqa: F401 - creates the tables
from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app as fastapi_app
from app.models.schemas import (Album, AlbumSource, CompositionPage, Image, ScheduleSlot, Tv, TvContent,
                                init_db_migrations)
from app.services import composition, supervisor
from app.services.albums import rescan_source
from app.services.composition import FRAME_SIZE, GAP, MARGIN, MAX_CROP, fill_score, group, layout
from app.services.image_proc import oriented_size
from app.services.sync import sync_tv
from tests.test_source_local import MediaRootMixin
from tests.test_supervisor import MONDAY_NOON, FakeClient

PORTRAIT, LANDSCAPE, SQUARE, PANO = 2 / 3, 3 / 2, 1.0, 3.0


def make_photo(path: Path, size, color=(200, 120, 40), orientation=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = PILImage.new("RGB", size, color)
    if orientation:
        exif = PILImage.Exif()
        exif[274] = orientation
        img.save(path, "JPEG", exif=exif)
    else:
        img.save(path, "JPEG")


def members(result):
    keep, new = result
    return [ids for _, ids in keep.values()] + [ids for _, ids in new]


class GroupingTest(unittest.TestCase):
    def test_templates(self):
        cases = [
            ([PORTRAIT, PORTRAIT], "pair_v"),
            ([SQUARE, SQUARE], "pair_v"),
            ([PANO, PANO], "pair_h"),
            ([PORTRAIT, LANDSCAPE, LANDSCAPE], "trio_v2h"),
            ([PORTRAIT, LANDSCAPE], "duo_vh"),
        ]
        for ratios, template in cases:
            _, new = group(list(enumerate(ratios, start=1)))
            self.assertEqual([t for t, _ in new], [template], ratios)
            self.assertEqual(sorted(new[0][1]), list(range(1, len(ratios) + 1)))

    def test_landscapes_that_fill_the_screen_stay_single(self):
        # Two stacked 3:2 photos would cover 36 % of the canvas: on their own they lose very little
        self.assertEqual(group([(1, LANDSCAPE), (2, LANDSCAPE)]), ({}, []))
        self.assertIsNone(fill_score("pair_h", [16 / 9, 16 / 9]))

    def test_odd_counts_and_unmeasured(self):
        # The leftover portrait joins the pair instead of staying alone cropped to 16:9
        keep, new = group([(1, PORTRAIT), (2, PORTRAIT), (3, PORTRAIT), (4, None)])
        self.assertEqual(new, [("trio_v", [1, 2, 3])])
        _, new = group([(i, PORTRAIT) for i in range(1, 6)])
        self.assertEqual(new, [("pair_v", [1, 2]), ("trio_v", [3, 4, 5])])  # joins the nearest pair
        _, new = group([(i, PORTRAIT) for i in range(1, 5)])
        self.assertEqual(new, [("pair_v", [1, 2]), ("pair_v", [3, 4])])

    def test_leftover_vertical_extends_existing_pair(self):
        existing = {7: ("pair_v", [1, 2])}
        keep, new = group([(1, PORTRAIT), (2, PORTRAIT), (3, PORTRAIT)], existing)
        self.assertEqual((keep, new), ({7: ("trio_v", [1, 2, 3])}, []))

    def test_positions_follow_template_slots(self):
        _, new = group([(1, LANDSCAPE), (2, LANDSCAPE), (3, PORTRAIT)])
        self.assertEqual(new, [("trio_v2h", [3, 1, 2])])

    def test_every_candidate_exactly_once_and_deterministic(self):
        rng = random.Random(7)
        shapes = [PORTRAIT, LANDSCAPE, SQUARE, PANO, 9 / 16, 4 / 3, 16 / 9, 0.8, None]
        for _ in range(50):
            cands = [(i, rng.choice(shapes)) for i in range(1, rng.randint(1, 40))]
            first = group(cands)
            self.assertEqual(first, group(cands))
            grouped = [i for ids in members(first) for i in ids]
            self.assertEqual(len(grouped), len(set(grouped)))
            self.assertTrue(set(grouped) <= {i for i, _ in cands})
            for template, ids in first[1]:
                self.assertIsNotNone(fill_score(template, [dict(cands)[i] for i in ids]))

    def test_existing_pages_are_stable(self):
        cands = [(1, PORTRAIT), (2, PORTRAIT), (3, LANDSCAPE), (4, PORTRAIT), (5, PANO), (6, PANO)]
        _, new = group(cands)
        existing = {10 + n: g for n, g in enumerate(new)}
        keep, again = group(cands, existing)
        self.assertEqual(keep, existing)
        self.assertEqual(again, [])

    def test_new_photo_reuses_incomplete_page_without_touching_others(self):
        existing = {1: ("pair_v", [1, 2]), 2: ("duo_vh", [3, 4])}
        cands = [(1, PORTRAIT), (2, PORTRAIT), (3, PORTRAIT), (4, LANDSCAPE), (5, LANDSCAPE)]
        keep, new = group(cands, existing)
        self.assertEqual(keep, {1: ("pair_v", [1, 2]), 2: ("trio_v2h", [3, 4, 5])})
        self.assertEqual(new, [])

    def test_page_with_missing_member_is_dissolved(self):
        existing = {1: ("pair_v", [1, 2]), 2: ("pair_v", [3, 4])}
        keep, new = group([(1, PORTRAIT), (2, PORTRAIT), (3, PORTRAIT), (5, PORTRAIT)], existing)
        self.assertEqual(keep, {1: ("pair_v", [1, 2])})
        self.assertEqual(new, [("pair_v", [3, 5])])

    def test_exif_orientation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rot.jpg"
            make_photo(path, (600, 400), orientation=6)
            self.assertEqual(oriented_size(path), (400, 600))


class LayoutTest(unittest.TestCase):
    def test_boxes_keep_ratio_margins_and_gaps(self):
        for template, ratios in [("pair_v", [PORTRAIT, 0.75]), ("trio_v2h", [PORTRAIT, LANDSCAPE, 16 / 9]),
                                 ("duo_vh", [SQUARE, PANO]), ("pair_h", [PANO, 2.5]), ("trio_v", [0.75] * 3),
                                 ("single", [9 / 16])]:
            boxes = layout(template, ratios)
            f = composition.crop_factor(template, ratios)
            self.assertTrue(1 - MAX_CROP - 1e-9 <= f <= 1 / (1 - MAX_CROP) + 1e-9)
            for (x, y, w, h), r in zip(boxes, ratios):
                # Every cell has the same crop, at most MAX_CROP per axis
                self.assertAlmostEqual(w / h, r * f, delta=0.01)
                self.assertGreaterEqual(min(x, y), MARGIN - 1)
                self.assertLessEqual(x + w, FRAME_SIZE[0] - MARGIN + 1)
                self.assertLessEqual(y + h, FRAME_SIZE[1] - MARGIN + 1)
            # The group touches the margin on at least one axis: no more background than unavoidable
            self.assertLessEqual(min(min(x for x, _, _, _ in boxes), min(y for _, y, _, _ in boxes)), MARGIN + 1)
            if template in ("pair_v", "duo_vh"):
                self.assertAlmostEqual(boxes[1][0] - (boxes[0][0] + boxes[0][2]), GAP, delta=1)
            if template == "pair_h":
                self.assertAlmostEqual(boxes[1][1] - (boxes[0][1] + boxes[0][3]), GAP, delta=1)

    def test_crop_fills_the_canvas_better(self):
        # iPhone photos (3:4 and 4:3): trio_v2h side background of 518 px without cropping, about 276 px with it
        boxes = layout("trio_v2h", [0.75, 4 / 3, 4 / 3])
        self.assertAlmostEqual(boxes[0][0], 276, delta=8)
        self.assertEqual(composition.crop_factor("trio_v2h", [0.75, 4 / 3, 4 / 3]), 1 / (1 - MAX_CROP))
        # If the crop is enough, the group fills the whole usable area
        boxes = layout("trio_v", [PORTRAIT] * 3)
        self.assertEqual((boxes[0][0], boxes[0][1]), (MARGIN, MARGIN))
        self.assertAlmostEqual(boxes[2][0] + boxes[2][2], FRAME_SIZE[0] - MARGIN, delta=1)

    def test_single_loss(self):
        self.assertAlmostEqual(composition.single_loss(16 / 9), 0)
        self.assertAlmostEqual(composition.single_loss(4 / 3), 0.25)
        self.assertGreater(composition.single_loss(0.75), 0.5)


class CompositionDbMixin(MediaRootMixin):
    def setUp(self):
        super().setUp()
        self.db = SessionLocal()
        self.album = Album(name="Comp", composition_mode="auto", interval=30, shuffle=False)
        self.db.add(self.album)
        self.db.commit()
        self.source = AlbumSource(album_id=self.album.id, path=str(self.root))
        self.db.add(self.source)
        self.db.commit()

    def tearDown(self):
        composition.remove_cache(self.album.id)
        self.db.query(Tv).filter(Tv.host.like("198.51.100.%")).delete(synchronize_session=False)
        self.db.delete(self.album)
        self.db.commit()
        self.db.close()
        super().tearDown()

    def photos(self, spec):
        """spec: {nombre: (ancho, alto, color)}"""
        for name, (w, h, color) in spec.items():
            make_photo(self.root / name, (w, h), color)
        self.rescan()

    def rescan(self):
        rescan_source(self.db, self.source)
        composition.process_album(self.db, self.album.id)

    def pages(self):
        return composition.active_pages(self.db, self.album.id)

    def image(self, key):
        return self.db.query(Image).filter(Image.album_id == self.album.id, Image.key == key).one()


class RenderTest(CompositionDbMixin, unittest.TestCase):
    def test_render_exact_size_with_cells_in_place(self):
        self.photos({"a.jpg": (800, 1200, (255, 0, 0)), "b.jpg": (1200, 800, (0, 0, 255)),
                     "c.jpg": (1200, 800, (0, 255, 0))})
        page = self.pages()[0]
        self.assertEqual((page.template, page.status), ("trio_v2h", "ready"))
        path = composition.page_file(self.album.id, page.id, page.revision)
        with PILImage.open(path) as img:
            self.assertEqual(img.size, FRAME_SIZE)
            rgb = img.convert("RGB")
            boxes = layout(page.template, [PORTRAIT, LANDSCAPE, LANDSCAPE])
            for (x, y, w, h), color in zip(boxes, [(255, 0, 0), (0, 0, 255), (0, 255, 0)]):
                for px, py in ((x + 4, y + 4), (x + w - 5, y + h - 5), (x + w // 2, y + h // 2)):
                    self.assertTrue(all(abs(a - b) < 40 for a, b in zip(rgb.getpixel((px, py)), color)))
                outside = rgb.getpixel((x - 8, y + h // 2))
                self.assertTrue(all(abs(a - b) < 20 for a, b in zip(outside, composition.BACKGROUND)))
        self.assertTrue(composition.page_thumb(self.album.id, page.id, page.revision).exists())

    def test_rotated_exif_is_grouped_as_vertical(self):
        make_photo(self.root / "a.jpg", (1200, 800), orientation=6)
        make_photo(self.root / "b.jpg", (1200, 800), orientation=8)
        self.rescan()
        self.assertEqual([p.template for p in self.pages()], ["pair_v"])
        self.assertEqual((self.image("a.jpg").width, self.image("a.jpg").height), (800, 1200))


class LifecycleTest(CompositionDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.photos({"a.jpg": (800, 1200, (255, 0, 0)), "b.jpg": (800, 1200, (0, 255, 0)),
                     "c.jpg": (900, 1200, (0, 0, 255)), "d.jpg": (900, 1200, (90, 90, 90)),
                     "e.jpg": (1600, 900, (10, 10, 10))})

    def snapshot(self):
        return [(p.id, p.template, p.revision, p.signature, [m.image_id for m in p.members]) for p in self.pages()]

    def test_rescan_without_changes_regenerates_nothing(self):
        before = self.snapshot()
        self.assertEqual(len(before), 2)
        with patch.object(composition, "render_page", wraps=composition.render_page) as render:
            self.rescan()
            render.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_changed_photo_only_updates_its_page(self):
        first, second = self.snapshot()
        make_photo(self.root / "a.jpg", (800, 1200), (250, 250, 0))
        self.rescan()
        updated, untouched = self.snapshot()
        self.assertEqual(untouched, second)
        self.assertEqual((updated[0], updated[2]), (first[0], first[2] + 1))
        page = self.pages()[0]
        self.assertEqual((page.status, page.rendered_revision), ("ready", 2))
        # No TV uses the previous revision: it is cleaned up
        self.assertFalse(composition.page_file(self.album.id, page.id, 1).exists())

    def test_exclusion_dissolves_page_and_original_files_stay(self):
        img = self.image("a.jpg")
        img.excluded = True
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        grouped = {m.image_id for p in self.pages() for m in p.members}
        self.assertNotIn(img.id, grouped)
        self.assertTrue((self.root / "a.jpg").exists())
        self.assertFalse(self.image("b.jpg").excluded)
        out = composition.effective_output(self.db, self.album)
        self.assertEqual(out.photos, 4)
        self.assertEqual(sum(len(it.page.members) if it.page else 1 for it in out.items), 4)

    def test_disable_restores_individual_output(self):
        self.album.composition_mode = "off"
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        self.assertEqual(self.pages(), [])
        self.assertEqual(self.db.query(CompositionPage).filter(CompositionPage.album_id == self.album.id).count(), 0)
        out = composition.effective_output(self.db, self.album)
        self.assertEqual((out.photos, out.total, len(out.items)), (5, 5, 5))
        self.assertFalse(any(composition.cache_dir(self.album.id).iterdir()))

    def test_removed_photo_dissolves_page(self):
        first, second = self.snapshot()
        (self.root / "c.jpg").unlink()
        self.rescan()
        kept, regrouped = self.snapshot()
        self.assertEqual(kept, first)
        # The portrait left alone takes the landscape that was single
        self.assertEqual(regrouped[1], "duo_vh")
        self.assertNotEqual(regrouped[0], second[0])
        self.assertEqual(self.db.get(CompositionPage, second[0]), None)
        out = composition.effective_output(self.db, self.album)
        self.assertEqual((out.photos, out.total), (4, 2))

    def test_missing_source_is_reported_and_blocks_completion(self):
        page = self.pages()[0]
        page.status = "pending"
        page.revision += 1
        self.db.commit()
        (self.root / "a.jpg").unlink()  # without rescanning: the file disappears during rendering
        composition.render_pending(self.db, self.album.id)
        self.assertEqual((page.status, page.last_error), ("error", "composition_source_unavailable"))
        out = composition.effective_output(self.db, self.album)
        self.assertFalse(out.complete)
        self.assertEqual(out.error, "composition_source_unavailable")

    def test_corrupt_file_reports_render_failure(self):
        page = self.pages()[0]
        page.status = "pending"
        self.db.commit()
        (self.root / "a.jpg").write_bytes((self.root / "a.jpg").read_bytes()[:400])  # JPEG truncado
        composition.render_pending(self.db, self.album.id)
        self.assertEqual((page.status, page.last_error), ("error", "composition_render_failed"))
        # The last valid version stays available for the preview and the TVs
        self.assertTrue(composition.page_file(self.album.id, page.id, page.rendered_revision).exists())

    def test_restart_during_generation_is_recovered(self):
        page = self.pages()[0]
        page.revision += 1
        page.status = "pending"
        self.db.commit()
        leftover = composition.page_file(self.album.id, page.id, page.revision)
        leftover.with_name(leftover.name + ".tmp").write_bytes(b"half")
        composition.process_album(self.db, self.album.id)
        self.assertEqual(page.status, "ready")
        self.assertTrue(leftover.exists())
        self.assertEqual([p for p in composition.cache_dir(self.album.id).iterdir() if p.suffix == ".tmp"], [])

    def test_jobs_for_different_albums_do_not_render_at_once(self):
        other = Album(name="Other", composition_mode="auto")
        self.db.add(other)
        self.db.commit()
        active, peak = [0], [0]
        real = composition.render_page

        def slow(db, page):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            active[0] -= 1
            return real(db, page)

        def run(album_id):
            db = SessionLocal()
            try:
                for p in composition.active_pages(db, album_id):
                    p.status = "pending"
                db.commit()
                composition.process_album(db, album_id)
            finally:
                db.close()

        try:
            with patch.object(composition, "render_page", side_effect=slow):
                threads = [threading.Thread(target=run, args=(a,)) for a in (self.album.id, other.id, self.album.id)]
                for th in threads:
                    th.start()
                for th in threads:
                    th.join()
            self.assertEqual(peak[0], 1)
        finally:
            self.db.delete(other)
            self.db.commit()


class CompositionSyncTest(CompositionDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.photos({"a.jpg": (800, 1200, (255, 0, 0)), "b.jpg": (800, 1200, (0, 255, 0)),
                     "c.jpg": (1600, 900, (0, 0, 255))})
        self.tv = Tv(name="Frame A", host="198.51.100.1", paired=True)
        self.tv2 = Tv(name="Frame B", host="198.51.100.2", paired=True)
        self.db.add_all([self.tv, self.tv2])
        self.db.commit()
        self.client, self.client2 = FakeClient(), FakeClient()

    def sync(self, tv=None, client=None):
        return sync_tv(self.db, tv or self.tv, self.album, client or self.client)

    def rows(self, tv=None):
        return self.db.query(TvContent).filter(TvContent.tv_id == (tv or self.tv).id).all()

    def test_grouped_originals_are_not_uploaded(self):
        result = self.sync()
        self.assertEqual(result.uploaded, 2)  # one page and the single landscape
        page = self.pages()[0]
        keys = {(r.page_id, r.page_revision, r.image_id) for r in self.rows()}
        self.assertEqual(keys, {(page.id, 1, None), (None, None, self.image("c.jpg").id)})
        self.assertIn("MY_F9999", self.client.photos)

    def test_enabling_replaces_individual_photos_only_when_ready(self):
        self.album.composition_mode = "off"
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        self.sync()
        self.assertEqual(len(self.rows()), 3)
        self.album.composition_mode = "auto"
        self.db.commit()
        # No grouping yet: nothing is touched
        result = self.sync()
        self.assertFalse(result.changed)
        self.assertEqual(len(self.rows()), 3)
        composition.process_album(self.db, self.album.id)
        result = self.sync()
        self.assertEqual((result.uploaded, result.deleted), (1, 2))
        self.assertEqual(len(self.client.photos), 3)

    def test_failed_page_keeps_previous_output(self):
        self.sync()
        page = self.pages()[0]
        page.status, page.last_error = "error", "composition_render_failed"
        img = self.image("c.jpg")
        img.excluded = True
        self.db.commit()
        composition.plan_album(self.db, self.album)
        page.status = "error"
        self.db.commit()
        result = self.sync()
        self.assertEqual(result.deleted, 0)
        self.assertEqual(len(self.rows()), 2)

    def test_page_revision_is_replaced_after_upload(self):
        self.sync()
        old = {r.content_id for r in self.rows() if r.page_id}
        make_photo(self.root / "a.jpg", (800, 1200), (250, 250, 0))
        self.client.fail_upload = True
        self.rescan()
        from app.services.tv_client import TvError
        with self.assertRaises(TvError):
            self.sync()
        # No space or no connection: the previous version stays on the TV
        self.assertTrue(old <= set(self.client.photos))
        self.client.fail_upload = False
        result = self.sync()
        self.assertEqual((result.uploaded, result.deleted), (1, 1))
        self.assertFalse(old & set(self.client.photos))
        self.assertEqual({r.page_revision for r in self.rows() if r.page_id}, {2})

    def test_batches_keep_old_output_until_all_uploaded(self):
        self.album.composition_mode = "off"
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        self.sync()
        self.album.composition_mode = "auto"
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        make_photo(self.root / "d.jpg", (800, 1200))
        make_photo(self.root / "e.jpg", (800, 1200))
        self.rescan()
        old = settings["frame"].get("uploads_per_tick")
        settings["frame"]["uploads_per_tick"] = 1
        try:
            first = self.sync()
            self.assertEqual((first.uploaded, first.deleted), (1, 0))
            second = self.sync()
            self.assertEqual((second.uploaded, second.deleted), (1, 2))
        finally:
            settings["frame"]["uploads_per_tick"] = old

    def test_several_tvs_share_the_file_and_keep_own_revision(self):
        self.sync()
        self.sync(self.tv2, self.client2)
        make_photo(self.root / "a.jpg", (800, 1200), (250, 250, 0))
        self.rescan()
        self.sync()  # TV B is still not updated (off)
        page = self.pages()[0]
        composition.cleanup(self.db, self.album.id)
        self.assertTrue(composition.page_file(self.album.id, page.id, 1).exists())
        self.assertEqual({r.page_revision for r in self.rows(self.tv2) if r.page_id}, {1})
        self.sync(self.tv2, self.client2)
        composition.cleanup(self.db, self.album.id)
        self.assertFalse(composition.page_file(self.album.id, page.id, 1).exists())
        self.assertTrue(composition.page_file(self.album.id, page.id, 2).exists())

    def test_supervisor_rotates_pages(self):
        self.db.add(ScheduleSlot(tv_id=self.tv.id, album_id=self.album.id, days=1, start="08:00", end="23:00"))
        self.db.commit()
        supervisor.tick(self.db, self.tv, now=MONDAY_NOON, client_factory=lambda tv: self.client)
        self.assertEqual(self.client.rotations, [(0, False)])
        self.assertEqual(len(self.client.photos), 3)

    def test_gallery_delete_of_page_excludes_members(self):
        self.sync()
        row = next(r for r in self.rows() if r.page_id)
        member_ids = [m.image_id for m in self.pages()[0].members]
        http = TestClient(fastapi_app)
        with patch("app.api.tvs.client_for", return_value=self.client), patch("app.api.tvs.run_now") as queued:
            items = http.get(f"/api/tvs/{self.tv.id}/gallery").json()
            item = next(i for i in items if i["content_id"] == row.content_id)
            self.assertEqual((item["page_id"], item["members"]), (row.page_id, 2))
            thumb = http.get(f"/api/tvs/{self.tv.id}/gallery/{row.content_id}/thumb")
            self.assertEqual(thumb.status_code, 200)
            res = http.post(f"/api/tvs/{self.tv.id}/gallery/delete", json={"content_ids": [row.content_id]})
            self.assertEqual(res.json()["deleted"], [row.content_id])
            self.assertEqual(queued.call_count, 1)
        self.db.expire_all()
        self.assertTrue(all(self.db.get(Image, i).excluded for i in member_ids))
        self.assertTrue((self.root / "a.jpg").exists())


class CompositionApiTest(CompositionDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.http = TestClient(fastapi_app)
        self.photos({"a.jpg": (800, 1200, (255, 0, 0)), "b.jpg": (800, 1200, (0, 255, 0)),
                     "c.jpg": (1600, 900, (0, 0, 255))})

    def test_mode_validation_and_counters(self):
        res = self.http.post("/api/albums", json={"name": "x", "composition_mode": "magic"})
        self.assertEqual(res.json()["detail"], "invalid_composition_mode")
        res = self.http.patch(f"/api/albums/{self.album.id}", json={"composition_mode": "wrong"})
        self.assertEqual(res.json()["detail"], "invalid_composition_mode")
        album = next(a for a in self.http.get("/api/albums").json() if a["id"] == self.album.id)
        self.assertEqual(album["composition_mode"], "auto")
        self.assertEqual((album["output"]["photos"], album["output"]["total"]), (3, 2))
        with patch("app.api.albums.run_now") as queued:
            res = self.http.patch(f"/api/albums/{self.album.id}", json={"composition_mode": "off"})
            self.assertEqual(res.json()["composition_mode"], "off")
            self.assertEqual(queued.call_count, 1)

    def test_pages_and_preview(self):
        pages = self.http.get(f"/api/albums/{self.album.id}/pages").json()
        self.assertEqual(len(pages), 1)
        self.assertEqual([m["key"] for m in pages[0]["members"]], ["a.jpg", "b.jpg"])
        thumb = self.http.get(f"/api/pages/{pages[0]['id']}/thumb")
        self.assertEqual(thumb.headers["content-type"], "image/jpeg")
        full = self.http.get(f"/api/pages/{pages[0]['id']}/image")
        path = composition.page_file(self.album.id, pages[0]["id"], pages[0]["revision"])
        self.assertEqual(full.content, path.read_bytes())
        self.assertEqual(self.http.get("/api/pages/999999/thumb").status_code, 404)

    def test_new_albums_default_to_off(self):
        res = self.http.post("/api/albums", json={"name": "Nuevo"}).json()
        try:
            self.assertEqual(res["composition_mode"], "off")
            self.assertEqual(self.http.post(f"/api/albums/{res['id']}/compose").json()["detail"],
                             "invalid_composition_mode")
        finally:
            self.http.delete(f"/api/albums/{res['id']}")


class MigrationTest(unittest.TestCase):
    def test_existing_database_gets_new_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(f"sqlite:///{Path(tmp) / 'old.db'}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE albums (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"))
                conn.execute(text("CREATE TABLE images (id INTEGER PRIMARY KEY, key VARCHAR)"))
                conn.execute(text("CREATE TABLE tv_contents (id INTEGER PRIMARY KEY, content_id VARCHAR)"))
                conn.execute(text("INSERT INTO albums (name) VALUES ('viejo')"))
            init_db_migrations(engine)
            cols = {t: {c["name"] for c in inspect(engine).get_columns(t)} for t in ("albums", "images", "tv_contents")}
            self.assertTrue({"composition_mode", "composition_plan"} <= cols["albums"])
            self.assertTrue({"width", "height"} <= cols["images"])
            self.assertTrue({"page_id", "page_revision"} <= cols["tv_contents"])
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT composition_mode FROM albums")).scalar(), "off")
            init_db_migrations(engine)  # idempotente
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
