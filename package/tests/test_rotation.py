"""App-driven rotation (every interval)."""
import random
import unittest
from datetime import timedelta
from unittest.mock import patch

import requests

from app.core.database import SessionLocal
from app.models.schemas import Album, AlbumSource, ScheduleSlot, Tv, TvContent
from app.services import rotation, supervisor
from app.services.albums import rescan_source
from app.services.rotation import Deck, next_content
from app.services.tv_client import TvClient, TvError
from tests.test_source_local import MediaRootMixin, make_image
from tests.test_supervisor import MONDAY_NOON, FakeClient


class RotatingClient(FakeClient):
    def __init__(self, state="art"):
        super().__init__(state)
        self.selected = []
        self.fail_select = None
        self.busy = False

    def session(self, wait=60):
        if self.busy:
            raise TvError("tv_busy")
        return super().session(wait)

    def select(self, content_id):
        if self.fail_select:
            raise TvError(self.fail_select)
        self.selected.append(content_id)


class DeckTest(unittest.TestCase):
    def test_sequential_wraps_and_follows_current(self):
        deck = Deck(1, False, MONDAY_NOON)
        items = ["a", "b", "c"]
        seen = []
        for _ in range(4):
            deck.current = next_content(deck, items)
            seen.append(deck.current)
        self.assertEqual(seen, ["a", "b", "c", "a"])
        deck.current = "gone"
        self.assertEqual(next_content(deck, items), "a")

    def test_shuffle_without_repeats_until_exhausted(self):
        rng = random.Random(3)
        deck = Deck(1, True, MONDAY_NOON)
        items = [f"MY_F{i:04d}" for i in range(7)]
        for _ in range(20):
            round_ = []
            for _ in items:
                deck.current = next_content(deck, items, rng)
                round_.append(deck.current)
            self.assertEqual(sorted(round_), items)
        # Reshuffling never repeats the image on screen
        for _ in range(50):
            last = deck.current
            deck.pending = []
            deck.current = next_content(deck, items, rng)
            self.assertNotEqual(deck.current, last)

    def test_removed_items_leave_the_deck(self):
        deck = Deck(1, True, MONDAY_NOON, pending=["x", "b", "c"])
        self.assertEqual(next_content(deck, ["b", "c"]), "b")


class SleepStateTest(unittest.TestCase):
    def client(self, artmode="on", paired=True):
        client = TvClient("192.0.2.50", token_file=__file__ if paired else "/nonexistent/token")

        class Art:
            def get_artmode(self):
                if isinstance(artmode, Exception):
                    raise artmode
                return artmode

        def fake_art(deadline=None):
            from contextlib import contextmanager

            @contextmanager
            def ctx():
                if isinstance(artmode, TvError):
                    raise artmode
                yield Art()
            return ctx()

        client._art = fake_art
        return client

    def test_rest_down_never_touches_the_art_channel(self):
        # Connecting to the art channel turns on a screen the sensor turned off
        client = self.client("on")
        client._art = lambda deadline=None: self.fail("must not open the art channel")
        with patch.object(TvClient, "rest_info", side_effect=requests.ConnectionError()):
            self.assertEqual(client.state(), "offline")

    def test_select_timeout_is_confirmed_with_current_image(self):
        client = self.client(TvError("tv_timeout"))
        with patch.object(TvClient, "current", return_value="MY_F0002"):
            client.select("MY_F0002")  # the TV applied the change without answering
            with self.assertRaises(TvError) as ctx:
                client.select("MY_F0003")
        self.assertEqual(ctx.exception.code, "tv_timeout")
        with self.assertRaises(TvError) as ctx:
            self.client(TvError("tv_unavailable")).select("MY_F0002")
        self.assertEqual(ctx.exception.code, "tv_unavailable")


class RotationTickTest(MediaRootMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        rotation.reset()
        for name in ("a.jpg", "b.jpg", "c.jpg"):
            make_image(self.root / name)
        self.db = SessionLocal()
        self.album = Album(name="Fast", interval=2, shuffle=False)
        self.other = Album(name="Lento", interval=30, shuffle=False)
        self.tv = Tv(name="Frame", host="192.0.2.11", mac="D4:9D:C0:00:00:02", paired=True)
        self.db.add_all([self.album, self.other, self.tv])
        self.db.commit()
        self.source = AlbumSource(album_id=self.album.id, path=str(self.root))
        self.db.add(self.source)
        self.slot = ScheduleSlot(tv_id=self.tv.id, album_id=self.album.id, days=1, start="08:00", end="23:00")
        self.db.add(self.slot)
        self.db.commit()
        rescan_source(self.db, self.source)
        self.client = RotatingClient()

    def tearDown(self):
        rotation.reset()
        for obj in (self.tv, self.album, self.other):
            self.db.delete(obj)
        self.db.commit()
        self.db.close()
        super().tearDown()

    def supervise(self, now=MONDAY_NOON):
        supervisor.tick(self.db, self.tv, now=now, client_factory=lambda tv: self.client)

    def rotate(self, minutes):
        return rotation.tick(self.db, self.tv, now=MONDAY_NOON + timedelta(minutes=minutes),
                             client_factory=lambda tv: self.client)

    def own_ids(self):
        rows = self.db.query(TvContent).filter(TvContent.tv_id == self.tv.id).all()
        return sorted(r.content_id for r in rows)

    def test_supervisor_turns_native_rotation_off(self):
        self.supervise()
        self.assertEqual(self.client.rotations, [(0, False)])

    def test_rotates_only_album_photos_on_schedule(self):
        self.supervise()
        self.assertTrue(self.rotate(0))  # the first image is shown on entering the slot
        self.assertFalse(self.rotate(1))
        self.assertTrue(self.rotate(2))
        self.assertFalse(self.rotate(3))
        self.assertTrue(self.rotate(4))
        self.assertTrue(self.rotate(6))
        own = self.own_ids()
        self.assertEqual(self.client.selected, own + own[:1])
        self.assertNotIn("MY_F9999", self.client.selected)  # the foreign photo does not enter the rotation

    def test_long_intervals_are_rotated_by_the_app(self):
        self.album.interval = 30
        self.db.commit()
        self.supervise()
        self.assertEqual(self.client.rotations, [(0, False)])
        self.assertTrue(self.rotate(0))
        self.assertFalse(self.rotate(10))
        self.assertTrue(self.rotate(30))

    def test_screen_off_or_in_use_is_not_touched(self):
        self.supervise()
        for state in ("tv", "offline", "standby"):
            self.client.state_value = state
            self.assertFalse(self.rotate(0))
        self.assertEqual(self.client.selected, [])
        self.client.state_value = "art"
        self.assertTrue(self.rotate(0))  # recovers as soon as the screen comes back on

    def test_busy_channel_waits_without_error(self):
        self.supervise()
        self.rotate(0)
        self.client.busy = True
        self.assertFalse(self.rotate(2))
        self.assertIsNone(self.tv.last_error)
        self.client.busy = False
        self.assertTrue(self.rotate(2))

    def test_failed_select_is_recorded_and_retried(self):
        self.supervise()
        self.rotate(0)
        self.client.fail_select = "tv_timeout"
        self.assertFalse(self.rotate(2))
        self.assertEqual(self.tv.last_error, "tv_timeout")
        self.client.fail_select = None
        self.assertTrue(self.rotate(2))

    def test_new_album_is_shown_right_away_and_outside_slots_left_alone(self):
        self.supervise()
        self.rotate(0)
        self.slot.album_id = self.other.id
        self.db.commit()
        self.assertFalse(self.rotate(10))  # nothing of that album on the TV yet
        self.slot.album_id = self.album.id
        self.db.commit()
        self.assertTrue(self.rotate(12))  # new deck: no full interval wait
        self.assertFalse(self.rotate(13))
        night = rotation.tick(self.db, self.tv, now=MONDAY_NOON + timedelta(hours=12),
                              client_factory=lambda tv: self.client)
        self.assertFalse(night)


if __name__ == "__main__":
    unittest.main()
