"""Franjas horarias semanales: días como máscara de bits (bit 0 = lunes) y horas "HH:MM" en hora local del NAS."""
import re
from datetime import datetime

WEEK = 7 * 1440
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_hhmm(value: str) -> int:
    m = _HHMM.match(value or "")
    if not m:
        raise ValueError("invalid_time")
    return int(m.group(1)) * 60 + int(m.group(2))


def week_ranges(days: int, start: str, end: str) -> list:
    """Rangos [inicio, fin) en minutos de la semana; una franja que cruza medianoche termina al día siguiente."""
    s, e = parse_hhmm(start), parse_hhmm(end)
    length = (e - s) % 1440
    ranges = []
    for day in range(7):
        if days & (1 << day):
            begin = day * 1440 + s
            ranges.append((begin, begin + length))
    return ranges


def _overlap(a, b) -> bool:
    # Se comparan también desplazados una semana para cubrir la franja de domingo que cruza a lunes
    for shift in (-WEEK, 0, WEEK):
        if a[0] < b[1] + shift and b[0] + shift < a[1]:
            return True
    return False


def slots_overlap(a: tuple, b: tuple) -> bool:
    """a y b son (days, start, end)."""
    return any(_overlap(x, y) for x in week_ranges(*a) for y in week_ranges(*b))


def minute_of_week(now: datetime) -> int:
    return now.weekday() * 1440 + now.hour * 60 + now.minute


def slot_active(days: int, start: str, end: str, now: datetime) -> bool:
    t = minute_of_week(now)
    return any(b <= t < e or b <= t + WEEK < e for b, e in week_ranges(days, start, end))


def active_slot(slots, now: datetime):
    for slot in slots:
        if slot.enabled and slot_active(slot.days, slot.start, slot.end, now):
            return slot
    return None
