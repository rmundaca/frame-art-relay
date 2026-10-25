import unittest
from datetime import datetime

from app.services.schedule import active_slot, slot_active, slots_overlap

MON, TUE, SUN = 1, 2, 64


class Slot:
    def __init__(self, days, start, end, enabled=True):
        self.days, self.start, self.end, self.enabled = days, start, end, enabled


class ScheduleTest(unittest.TestCase):
    # 2026-10-26 es lunes
    def at(self, day, hhmm):
        h, m = map(int, hhmm.split(":"))
        return datetime(2026, 10, 26 + day, h, m)

    def test_same_day_range(self):
        self.assertTrue(slot_active(MON, "08:00", "23:00", self.at(0, "08:00")))
        self.assertFalse(slot_active(MON, "08:00", "23:00", self.at(0, "23:00")))
        self.assertFalse(slot_active(MON, "08:00", "23:00", self.at(1, "12:00")))

    def test_crosses_midnight(self):
        self.assertTrue(slot_active(MON, "22:00", "02:00", self.at(0, "23:30")))
        self.assertTrue(slot_active(MON, "22:00", "02:00", self.at(1, "01:59")))
        self.assertFalse(slot_active(MON, "22:00", "02:00", self.at(1, "22:30")))

    def test_sunday_night_wraps_to_monday(self):
        self.assertTrue(slot_active(SUN, "23:00", "01:00", self.at(0, "00:30")))

    def test_overlap(self):
        self.assertTrue(slots_overlap((MON, "08:00", "12:00"), (MON, "11:00", "13:00")))
        self.assertFalse(slots_overlap((MON, "08:00", "12:00"), (MON, "12:00", "13:00")))
        self.assertFalse(slots_overlap((MON, "08:00", "12:00"), (TUE, "08:00", "12:00")))
        self.assertTrue(slots_overlap((MON, "22:00", "02:00"), (TUE, "01:00", "03:00")))
        self.assertTrue(slots_overlap((SUN, "23:00", "02:00"), (MON, "01:00", "03:00")))

    def test_active_slot_skips_disabled(self):
        slots = [Slot(127, "00:00", "12:00", enabled=False), Slot(127, "06:00", "18:00")]
        self.assertIs(active_slot(slots, self.at(2, "07:00")), slots[1])
        self.assertIsNone(active_slot(slots, self.at(2, "19:00")))

    def test_invalid_time(self):
        with self.assertRaises(ValueError):
            slot_active(MON, "24:00", "02:00", self.at(0, "00:00"))


if __name__ == "__main__":
    unittest.main()
