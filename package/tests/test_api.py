import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.schemas import Album, Tv, TvContent
from tests.test_source_local import MediaRootMixin, make_image


class HealthApiTest(unittest.TestCase):
    def setUp(self):
        # Without "with": startup events do not fire (the scheduler does not run in tests)
        self.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_index(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Frame Art Relay", res.text)


class AlbumsApiTest(MediaRootMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(app)
        make_image(self.root / "fotos" / "a.jpg", size=(800, 600))
        make_image(self.root / "fotos" / "b.jpg")

    def test_album_flow(self):
        res = self.client.post("/api/albums", json={"name": "  Otoño ", "interval": 30, "shuffle": False})
        self.assertEqual(res.status_code, 200)
        album = res.json()
        self.assertEqual(album["name"], "Otoño")

        res = self.client.post(f"/api/albums/{album['id']}/sources", json={"path": str(self.root / "fotos")})
        self.assertEqual(res.json()["images"], 2)
        dup = self.client.post(f"/api/albums/{album['id']}/sources", json={"path": str(self.root / "fotos")})
        self.assertEqual(dup.json()["detail"], "source_exists")

        images = self.client.get(f"/api/albums/{album['id']}/images").json()
        self.assertEqual([i["key"] for i in images], ["a.jpg", "b.jpg"])
        thumb = self.client.get(f"/api/images/{images[0]['id']}/thumb")
        self.assertEqual(thumb.headers["content-type"], "image/jpeg")
        self.assertEqual(thumb.headers["cache-control"], "no-cache")
        # Deleted ids are reused: only the versioned URL may be cached
        versioned = self.client.get(f"/api/images/{images[0]['id']}/thumb", params={"v": images[0]["v"]})
        self.assertIn("immutable", versioned.headers["cache-control"])
        self.client.patch(f"/api/images/{images[0]['id']}", json={"excluded": True})
        listed = [a for a in self.client.get("/api/albums").json() if a["id"] == album["id"]][0]
        self.assertEqual((listed["images"], listed["included"]), (2, 1))

        self.assertEqual(self.client.delete(f"/api/albums/{album['id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/albums/{album['id']}/images").status_code, 404)

    def test_validation(self):
        self.assertEqual(self.client.post("/api/albums", json={"name": " "}).json()["detail"], "invalid_name")
        self.assertEqual(self.client.post("/api/albums", json={"name": "x", "interval": 7}).json()["detail"],
                         "invalid_interval")
        self.assertEqual(self.client.post("/api/albums", json={"name": "x", "matte": "gold"}).json()["detail"],
                         "invalid_matte")

    def test_icloud_formats_are_preserved_and_deduplicated(self):
        urls = ("https://photos.icloud.com/shared/album/06aExamplePublicAlbumLink",
                "https://www.icloud.com/sharedalbum/#B0z5qAGN1JIFd3y")
        album = self.client.post("/api/albums", json={"name": "iCloud"}).json()
        try:
            with patch("app.api.albums.source_icloud.album_name", return_value="Cloud album") as lookup, \
                    patch("app.api.albums.run_now") as schedule:
                for url in urls:
                    submitted = url + "/" if "photos.icloud.com" in url else url + ";x"
                    res = self.client.post(f"/api/albums/{album['id']}/sources",
                                           json={"kind": "icloud", "path": submitted})
                    self.assertEqual(res.status_code, 200, res.text)
                    self.assertEqual(res.json()["sources"][-1]["path"], url)
                    self.assertEqual(lookup.call_args.args[1], url)
                    dup = self.client.post(f"/api/albums/{album['id']}/sources",
                                           json={"kind": "icloud", "path": url})
                    self.assertEqual(dup.status_code, 409)
                    self.assertEqual(dup.json()["detail"], "source_exists")
                self.assertEqual(schedule.call_count, 2)
        finally:
            self.client.delete(f"/api/albums/{album['id']}")

    def test_browse_rejects_outside_roots(self):
        res = self.client.get("/api/browse", params={"path": str(self.root / "..")})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "path_not_allowed")
        self.assertEqual(self.client.get("/api/browse", params={"path": str(self.root)}).json()["dirs"][0]["name"],
                         "fotos")


class ScheduleApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        db = SessionLocal()
        self.tv = Tv(name="Frame", host="192.0.2.20")
        self.album = Album(name="A")
        db.add_all([self.tv, self.album])
        db.commit()
        self.ids = (self.tv.id, self.album.id)
        db.close()

    def tearDown(self):
        db = SessionLocal()
        db.delete(db.get(Tv, self.ids[0]))
        db.delete(db.get(Album, self.ids[1]))
        db.commit()
        db.close()

    def slot(self, **kw):
        body = {"tv_id": self.ids[0], "album_id": self.ids[1], "days": 1, "start": "08:00", "end": "12:00"}
        body.update(kw)
        return self.client.post("/api/schedule", json=body)

    def test_overlap_and_validation(self):
        self.assertEqual(self.slot().status_code, 200)
        self.assertEqual(self.slot(start="11:00", end="13:00").json()["detail"], "slot_overlap")
        self.assertEqual(self.slot(start="12:00", end="13:00").status_code, 200)
        self.assertEqual(self.slot(start="10:00", end="10:00").json()["detail"], "invalid_time_range")
        self.assertEqual(self.slot(start="25:00").json()["detail"], "invalid_time")
        self.assertEqual(self.slot(days=0).json()["detail"], "invalid_days")
        self.assertEqual(self.slot(days=2, enabled=False, start="11:00").status_code, 200)

    def test_tv_view_and_invalid_host(self):
        tvs = {t["id"]: t for t in self.client.get("/api/tvs").json()}
        self.assertFalse(tvs[self.ids[0]]["paired"])
        res = self.client.post("/api/tvs", json={"name": "x", "host": "bad host!"})
        self.assertEqual(res.json()["detail"], "invalid_host")

    def test_sizes_on_the_tv_and_purge_on_album_delete(self):
        db = SessionLocal()
        other = Tv(name="Frame B", host="192.0.2.21")
        db.add(other)
        db.commit()
        mb = 1048576
        db.add_all([TvContent(tv_id=tv, album_id=self.ids[1], render_sig=sig, content_id=cid, size=size)
                    for tv, sig, cid, size in ((self.ids[0], "a", "MY_F0001", 2 * mb),
                                               (self.ids[0], "b", "MY_F0002", mb),
                                               (other.id, "a", "MY_F0001", 2 * mb))])
        db.commit()
        try:
            album = next(a for a in self.client.get("/api/albums").json() if a["id"] == self.ids[1])
            self.assertEqual(album["tv_bytes"], 3 * mb)  # the same image on two TVs counts once
            tvs = {t["id"]: t for t in self.client.get("/api/tvs").json()}
            self.assertEqual((tvs[self.ids[0]]["uploaded_bytes"], tvs[other.id]["uploaded_bytes"]), (3 * mb, 2 * mb))
            self.assertEqual(self.client.get("/api/meta").json()["storage_warn_mb"], 1024)

            gone = Album(name="Gone")
            db.add(gone)
            db.commit()
            db.add(TvContent(tv_id=other.id, album_id=gone.id, content_id="MY_F0003", size=mb))
            db.commit()
            with patch("app.api.albums.run_now") as queued:
                self.assertEqual(self.client.delete(f"/api/albums/{gone.id}").status_code, 200)
            self.assertEqual(queued.call_args.args[1:], (other.id,))
            # The rows stay until the supervisor deletes the photos from the TV
            db.expire_all()
            self.assertEqual(db.query(TvContent).filter(TvContent.content_id == "MY_F0003").count(), 1)
        finally:
            db.query(TvContent).filter(TvContent.tv_id.in_((self.ids[0], other.id))).delete()
            db.delete(db.get(Tv, other.id))
            db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
