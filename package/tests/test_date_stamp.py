"""Fase 11.1: fecha de la toma en las fotos de iCloud."""
import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import create_engine, inspect, text

from app.core.database import SessionLocal
from app.main import app as fastapi_app
from app.models.schemas import Album, AlbumSource, Image, Tv, TvContent, init_db_migrations
from app.services import composition, source_icloud
from app.services.albums import date_label, fill_meta
from app.services.image_proc import DATE_MARGIN, FRAME_SIZE, draw_date, image_meta
from app.services.sync import sync_tv
from tests.test_composition import CompositionDbMixin, make_photo
from tests.test_supervisor import FakeClient

ICLOUD_URL = "https://www.icloud.com/sharedalbum/#B0aGtest123"


def dated_photo(path: Path, size, taken=None, color=(40, 90, 160), plain=None):
    """JPEG con DateTimeOriginal en el IFD Exif (taken) o solo DateTime en el principal (plain)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = PILImage.new("RGB", size, color)
    exif = PILImage.Exif()
    if taken:
        exif.get_ifd(0x8769)[36867] = taken
    if plain:
        exif[306] = plain
    img.save(path, "JPEG", exif=exif)


class RecordingClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.data = {}

    def upload(self, data, matte):
        cid = super().upload(data, matte)
        self.data[cid] = data
        return cid


class MetaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_original_date_with_fractions(self):
        dated_photo(self.dir / "a.jpg", (60, 40), taken="2019:01:26 18:33:25.002")
        self.assertEqual(image_meta(self.dir / "a.jpg"), (60, 40, "2019-01-26T18:33:25"))

    def test_falls_back_to_datetime_and_rejects_invalid(self):
        dated_photo(self.dir / "b.jpg", (60, 40), plain="2021:04:24 15:50:59")
        self.assertEqual(image_meta(self.dir / "b.jpg")[2], "2021-04-24T15:50:59")
        dated_photo(self.dir / "c.jpg", (60, 40), taken="0000:00:00 00:00:00")
        self.assertEqual(image_meta(self.dir / "c.jpg")[2], "")
        make_photo(self.dir / "d.jpg", (60, 40))
        self.assertEqual(image_meta(self.dir / "d.jpg")[2], "")

    def test_draws_in_lower_right_corner_only(self):
        color = (40, 90, 160)
        canvas = PILImage.new("RGB", (1200, 800), color)
        box = (100, 100, 900, 600)
        draw_date(canvas, box, "2021-04-24")
        changed = [(x, y) for x in range(0, 1200, 4) for y in range(0, 800, 4) if canvas.getpixel((x, y)) != color]
        self.assertTrue(changed)
        # Todo el texto y su sombra quedan dentro de la foto, en su esquina inferior derecha
        self.assertTrue(all(600 < x < 1000 - DATE_MARGIN // 2 and 600 < y < 700 for x, y in changed))
        # Las tintas más claras son el texto blanco
        self.assertGreater(max(sum(canvas.getpixel(p)) for p in changed), sum(color) + 200)

    def test_skips_boxes_too_small(self):
        canvas = PILImage.new("RGB", (300, 120), (0, 0, 0))
        draw_date(canvas, (0, 0, 200, 60), "2021-04-24")
        self.assertEqual(canvas.getextrema(), ((0, 0), (0, 0), (0, 0)))


class DateStampDbMixin(CompositionDbMixin):
    """Álbum con una fuente local (self.source) y otra de iCloud con fotos en su caché."""

    def setUp(self):
        super().setUp()
        self.album.composition_mode = "off"
        self.icloud = AlbumSource(album_id=self.album.id, kind="icloud", path=ICLOUD_URL, label="Perros")
        self.db.add(self.icloud)
        self.tv = Tv(name="Frame A", host="198.51.100.1", paired=True)
        self.db.add(self.tv)
        self.db.commit()
        self.client = RecordingClient()

    def tearDown(self):
        source_icloud.remove_cache(self.icloud.id)
        super().tearDown()

    def cloud_photo(self, key, size, taken=None, color=(40, 90, 160)):
        path = source_icloud.cache_dir(self.icloud.id) / key
        dated_photo(path, size, taken, color)
        st = path.stat()
        img = Image(album_id=self.album.id, source_id=self.icloud.id, key=key, size=st.st_size, mtime=st.st_mtime)
        self.db.add(img)
        self.db.commit()
        return img

    def sync(self):
        return sync_tv(self.db, self.tv, self.album, self.client)

    def rows(self):
        return self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).all()

    def uploaded(self, row):
        return PILImage.open(io.BytesIO(self.client.data[row.content_id])).convert("RGB")


class SingleStampTest(DateStampDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.cloud = self.cloud_photo("perro-1.jpg", (1600, 900), taken="2021:04:24 15:50:59")
        dated_photo(self.root / "local.jpg", (1600, 900), taken="2022:07:03 15:18:45")
        self.rescan()  # escanea la fuente local y lee los metadatos pendientes

    def test_only_icloud_photos_get_the_date(self):
        local = self.image("local.jpg")
        self.assertEqual((self.cloud.taken_at, local.taken_at), ("2021-04-24T15:50:59", "2022-07-03T15:18:45"))
        self.assertEqual(date_label(self.db, self.album, self.cloud), "2021-04-24")
        self.assertEqual(date_label(self.db, self.album, local), "")
        self.assertEqual(self.sync().uploaded, 2)
        sigs = {r.image_id: r.render_sig for r in self.rows()}
        self.assertEqual(sigs, {self.cloud.id: "date=2021-04-24", local.id: None})
        dated = self.uploaded(next(r for r in self.rows() if r.image_id == self.cloud.id))
        self.assertEqual(dated.size, FRAME_SIZE)
        corner = dated.crop((3840 - 400, 2160 - 100, 3840 - DATE_MARGIN, 2160 - DATE_MARGIN))
        self.assertGreater(corner.getextrema()[0][1], 200)  # texto blanco sobre una foto azul oscura

    def test_toggle_replaces_upload_without_gaps(self):
        self.sync()
        old = {r.image_id: r.content_id for r in self.rows()}
        self.album.date_stamp = False
        self.db.commit()
        result = self.sync()
        self.assertEqual((result.uploaded, result.deleted), (1, 1))
        rows = {r.image_id: r for r in self.rows()}
        self.assertNotEqual(rows[self.cloud.id].content_id, old[self.cloud.id])
        self.assertIsNone(rows[self.cloud.id].render_sig)
        self.assertNotIn(old[self.cloud.id], self.client.photos)
        self.assertIn("MY_F9999", self.client.photos)  # las fotos ajenas no se tocan
        self.assertEqual(self.sync().uploaded, 0)

    def test_failed_upload_keeps_previous_variant(self):
        self.sync()
        before = set(self.client.photos)
        self.album.date_stamp = False
        self.db.commit()
        self.client.fail_upload = True
        with self.assertRaises(Exception):
            self.sync()
        self.assertEqual(set(self.client.photos), before)

    def test_waits_until_the_date_is_read(self):
        self.cloud_photo("perro-2.jpg", (1600, 900), taken="2023:10:29 16:10:08")
        self.assertFalse(composition.effective_output(self.db, self.album).current)
        result = self.sync()
        self.assertEqual((result.uploaded, result.deleted), (0, 0))
        fill_meta(self.db, self.album)
        self.assertTrue(composition.effective_output(self.db, self.album).current)
        self.assertEqual(self.sync().uploaded, 3)

    def test_photo_without_date_is_uploaded_unchanged(self):
        plain = self.cloud_photo("perro-3.jpg", (1600, 900))
        fill_meta(self.db, self.album)
        self.assertEqual(plain.taken_at, "")
        self.sync()
        self.assertIsNone(next(r for r in self.rows() if r.image_id == plain.id).render_sig)

    def test_changed_file_rereads_the_date(self):
        self.sync()
        path = source_icloud.cache_dir(self.icloud.id) / self.cloud.key
        dated_photo(path, (1600, 900), taken="2020:02:02 10:00:00")
        st = path.stat()
        self.cloud.size, self.cloud.mtime = st.st_size, st.st_mtime + 1
        self.cloud.width = self.cloud.height = self.cloud.taken_at = None
        self.db.commit()
        fill_meta(self.db, self.album)
        self.sync()
        self.assertIn("date=2020-02-02", {r.render_sig for r in self.rows()})


class PageStampTest(DateStampDbMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.album.composition_mode = "auto"
        self.db.commit()
        self.a = self.cloud_photo("v-1.jpg", (800, 1200), taken="2019:12:29 16:26:17.918", color=(30, 30, 120))
        self.b = self.cloud_photo("v-2.jpg", (800, 1200), taken="2021:10:24 20:19:13", color=(30, 120, 30))
        composition.process_album(self.db, self.album.id)

    def page(self):
        pages = composition.active_pages(self.db, self.album.id)
        self.assertEqual([p.template for p in pages], ["pair_v"])
        return pages[0]

    def test_each_cell_gets_its_own_date(self):
        page = self.page()
        self.assertEqual(page.status, "ready")
        boxes = composition.layout(page.template, [800 / 1200, 800 / 1200])
        with PILImage.open(composition.page_file(self.album.id, page.id, page.revision)) as img:
            rgb = img.convert("RGB")
            for x, y, w, h in boxes:
                corner = rgb.crop((x + w - 360, y + h - 80, x + w - DATE_MARGIN, y + h - DATE_MARGIN))
                self.assertGreater(corner.getextrema()[0][1], 200)
                middle = rgb.crop((x + w // 2 - 20, y + h // 2 - 20, x + w // 2 + 20, y + h // 2 + 20))
                self.assertLess(middle.getextrema()[0][1], 80)

    def test_toggle_creates_a_new_revision(self):
        page = self.page()
        self.album.date_stamp = False
        self.db.commit()
        composition.process_album(self.db, self.album.id)
        self.db.refresh(page)
        self.assertEqual((page.revision, page.status), (2, "ready"))

    def test_pages_without_dates_keep_their_signature(self):
        imgs = [self.a, self.b]
        self.assertEqual(composition.page_signature("pair_v", imgs, ["", ""]),
                         composition.page_signature("pair_v", imgs))


class DateStampApiTest(CompositionDbMixin, unittest.TestCase):
    def test_default_on_and_patch(self):
        client = TestClient(fastapi_app)
        created = client.post("/api/albums", json={"name": "Nuevo"}).json()
        try:
            self.assertTrue(created["date_stamp"])
            patched = client.patch(f"/api/albums/{created['id']}", json={"date_stamp": False}).json()
            self.assertFalse(patched["date_stamp"])
        finally:
            client.delete(f"/api/albums/{created['id']}")

    def test_migration_adds_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(f"sqlite:///{Path(tmp) / 'old.db'}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE albums (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"))
                conn.execute(text("CREATE TABLE images (id INTEGER PRIMARY KEY, key VARCHAR)"))
                conn.execute(text("CREATE TABLE tv_contents (id INTEGER PRIMARY KEY, content_id VARCHAR)"))
                conn.execute(text("INSERT INTO albums (name) VALUES ('viejo')"))
            init_db_migrations(engine)
            cols = {t: {c["name"] for c in inspect(engine).get_columns(t)} for t in ("albums", "images", "tv_contents")}
            self.assertTrue({"date_stamp", "background", "single_fit"} <= cols["albums"])
            self.assertIn("taken_at", cols["images"])
            self.assertIn("render_sig", cols["tv_contents"])
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT date_stamp FROM albums")).scalar(), 1)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
