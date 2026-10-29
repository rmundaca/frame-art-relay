import unittest
from contextlib import contextmanager
from datetime import datetime

import app.main  # noqa: F401 - creates the tables
from app.core.database import SessionLocal
from app.models.schemas import Album, AlbumSource, Image, ScheduleSlot, Tv, TvContent
from app.services import supervisor
from app.services.albums import rescan_source
from app.services.tv_client import TvError
from tests.test_source_local import MediaRootMixin, make_image

MONDAY_NOON = datetime(2026, 10, 26, 12, 0)
MONDAY_NIGHT = datetime(2026, 10, 26, 23, 30)


class FakeClient:
    def __init__(self, state="art"):
        self.state_value = state
        self.photos = {"MY_F9999": "ajena"}
        self.rotations, self.woken = [], []
        self.fail_upload = False
        self._next = 1

    @contextmanager
    def session(self, wait=60):
        yield self

    def state(self):
        return self.state_value

    def my_photos(self):
        return [{"content_id": cid} for cid in self.photos]

    def upload(self, data, matte):
        if self.fail_upload:
            raise TvError("tv_unavailable")
        cid = f"MY_F{self._next:04d}"
        self._next += 1
        self.photos[cid] = matte
        return cid

    def delete(self, ids):
        for cid in ids:
            self.photos.pop(cid, None)

    def set_rotation(self, minutes, shuffle):
        self.rotations.append((minutes, shuffle))

    def wake(self, mac):
        self.woken.append(mac)


class SupervisorTest(MediaRootMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for name in ("a.jpg", "b.jpg", "c.jpg"):
            make_image(self.root / name)
        self.db = SessionLocal()
        self.album = Album(name="Test", matte="modern_black", interval=30, shuffle=False)
        self.tv = Tv(name="Frame", host="192.0.2.10", mac="D4:9D:C0:00:00:01", paired=True)
        self.db.add_all([self.album, self.tv])
        self.db.commit()
        self.source = AlbumSource(album_id=self.album.id, path=str(self.root))
        self.db.add(self.source)
        self.db.add(ScheduleSlot(tv_id=self.tv.id, album_id=self.album.id, days=1, start="08:00", end="23:00"))
        self.db.commit()
        rescan_source(self.db, self.source)
        self.client = FakeClient()

    def tearDown(self):
        self.db.delete(self.tv)
        self.db.delete(self.album)
        self.db.commit()
        self.db.close()
        super().tearDown()

    def tick(self, now=MONDAY_NOON):
        supervisor.tick(self.db, self.tv, now=now, client_factory=lambda tv: self.client)

    def test_uploads_album_and_starts_rotation(self):
        self.tick()
        self.assertEqual(len(self.client.photos), 4)
        self.assertEqual(set(self.client.photos.values()) - {"ajena"}, {"modern_black"})
        # The native slideshow would mix every album in "My Photos": the app rotates
        self.assertEqual(self.client.rotations, [(0, False)])
        self.assertEqual(self.tv.last_state, "art")
        self.tick()
        self.assertEqual(self.client.rotations, [(0, False)])

    def test_uploads_record_album_and_size(self):
        self.tick()
        rows = self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).all()
        self.assertEqual({r.album_id for r in rows}, {self.album.id})
        self.assertTrue(all(r.size and r.size > 0 for r in rows))

    def test_excluded_image_is_removed_but_foreign_photo_kept(self):
        self.tick()
        img = self.db.query(Image).filter(Image.key == "b.jpg").one()
        img.excluded = True
        self.db.commit()
        self.tick()
        self.assertEqual(self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).count(), 2)
        self.assertIn("MY_F9999", self.client.photos)
        self.assertEqual(len(self.client.photos), 3)

    def test_photo_deleted_by_hand_is_uploaded_again(self):
        self.tick()
        self.client.photos.pop("MY_F0001")
        self.tick()
        self.assertEqual(len(self.client.photos), 4)

    def test_tv_in_use_is_not_touched(self):
        self.client.state_value = "tv"
        self.tick()
        self.assertEqual(self.client.photos, {"MY_F9999": "ajena"})
        self.assertEqual(self.client.rotations, [])

    def test_outside_slot_stops_rotation_once(self):
        self.tick()
        self.tick(MONDAY_NIGHT)
        self.tick(MONDAY_NIGHT)
        self.assertEqual(self.client.rotations, [(0, False), (0, False)])

    def test_offline_in_slot_sends_wol(self):
        self.client.state_value = "offline"
        self.tick()
        self.assertEqual(self.client.woken, ["D4:9D:C0:00:00:01"])
        self.tick(MONDAY_NIGHT)
        self.assertEqual(len(self.client.woken), 1)

    def test_tv_error_is_recorded(self):
        self.client.fail_upload = True
        self.tick()
        self.assertEqual(self.tv.last_error, "tv_unavailable")


class AlbumSwitchTest(MediaRootMixin, unittest.TestCase):
    """Albums stay on the TV when the slot changes and are only deleted with the album."""

    def setUp(self):
        super().setUp()
        for name in ("a.jpg", "b.jpg"):
            make_image(self.root / "one" / name)
        make_image(self.root / "two" / "c.jpg")
        self.db = SessionLocal()
        self.one, self.two = Album(name="One", interval=30), Album(name="Two", interval=30)
        self.tv = Tv(name="Frame", host="192.0.2.12", paired=True)
        self.db.add_all([self.one, self.two, self.tv])
        self.db.commit()
        for album, folder in ((self.one, "one"), (self.two, "two")):
            source = AlbumSource(album_id=album.id, path=str(self.root / folder))
            self.db.add(source)
            self.db.commit()
            rescan_source(self.db, source)
        self.slot = ScheduleSlot(tv_id=self.tv.id, album_id=self.one.id, days=1, start="08:00", end="23:00")
        self.db.add(self.slot)
        self.db.commit()
        self.client = FakeClient()

    def tearDown(self):
        for obj in (self.tv, self.one, self.two):
            if self.db.get(type(obj), obj.id):
                self.db.delete(obj)
        self.db.commit()
        self.db.close()
        super().tearDown()

    def tick(self, now=MONDAY_NOON):
        supervisor.tick(self.db, self.tv, now=now, client_factory=lambda tv: self.client)

    def switch(self, album):
        self.slot.album_id = album.id
        self.db.commit()
        self.tick()

    def test_switching_keeps_previous_album_and_does_not_upload_it_again(self):
        self.tick()
        first = set(self.client.photos)
        self.switch(self.two)
        self.assertTrue(first <= set(self.client.photos))
        self.assertEqual(len(self.client.photos), 4)
        uploads = self.client._next
        self.switch(self.one)
        self.assertEqual(self.client._next, uploads)

    def test_deleting_the_album_deletes_its_photos_from_the_tv(self):
        self.tick()
        self.switch(self.two)
        self.db.delete(self.one)
        self.db.commit()
        self.client.state_value = "offline"
        self.tick(MONDAY_NIGHT)
        self.assertEqual(len(self.client.photos), 4)  # pending until the TV is reachable
        self.client.state_value = "art"
        self.tick(MONDAY_NIGHT)  # also outside the slots
        self.assertEqual(len(self.client.photos), 2)
        self.assertIn("MY_F9999", self.client.photos)
        rows = self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).all()
        self.assertEqual({r.album_id for r in rows}, {self.two.id})


if __name__ == "__main__":
    unittest.main()
