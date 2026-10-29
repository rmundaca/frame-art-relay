"""App-driven rotation for every interval.

The native slideshow rotates all of "My Photos", which keeps the photos of every album, so the supervisor turns it
off and this task shows the next image with select_image. Changing the image, and even connecting to the art
channel, turns the screen on even if the motion sensor turned it off. So rotation only happens with the TV in the
"art" state: state() queries REST first, which does not answer with the screen off, and in that case does not touch
the art channel.

The order lives in memory per TV: a restart starts a new deck.
"""
import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.schemas import Album, ScheduleSlot, TvContent
from app.services.composition import effective_output, row_key
from app.services.schedule import active_slot
from app.services.tv_client import TvError, client_for

logger = logging.getLogger("rotation")

# Maximum wait for the art channel: if the supervisor is uploading photos, try again next round
BUSY_WAIT = 2


@dataclass
class Deck:
    album_id: int
    shuffle: bool
    last_change: datetime
    current: str = ""
    pending: list = field(default_factory=list)  # orden aleatorio restante


_decks = {}
_guard = threading.Lock()


def playlist(db: Session, tv_id: int, album: Album) -> list:
    """TV content_ids of the album's current output, in order. Excludes foreign and retired photos."""
    on_tv = {row_key(r): r.content_id for r in db.query(TvContent).filter(TvContent.tv_id == tv_id)}
    return [on_tv[item.key] for item in effective_output(db, album).items if item.key in on_tv]


def next_content(deck: Deck, items: list, rng=random) -> str:
    """Next image: the one after the current one or, when shuffling, the next from a shuffled deck that does not
    repeat until exhausted and never restarts with the one on screen."""
    if not deck.shuffle:
        if deck.current in items:
            return items[(items.index(deck.current) + 1) % len(items)]
        return items[0]
    deck.pending = [c for c in deck.pending if c in items]
    if not deck.pending:
        deck.pending = list(items)
        rng.shuffle(deck.pending)
        if len(deck.pending) > 1 and deck.pending[0] == deck.current:
            deck.pending.append(deck.pending.pop(0))
    return deck.pending.pop(0)


def tick(db: Session, tv, now: datetime = None, client_factory=client_for, rng=random) -> bool:
    """Change the image if it is time. Returns True if it changed."""
    now = now or datetime.now()
    slots = db.query(ScheduleSlot).filter(ScheduleSlot.tv_id == tv.id).all()
    slot = active_slot(slots, now)
    album = db.get(Album, slot.album_id) if slot else None
    with _guard:
        if not album:
            _decks.pop(tv.id, None)
            return False
        deck = _decks.get(tv.id)
        if not deck or deck.album_id != album.id or deck.shuffle != album.shuffle:
            # New album in the slot: its first image is shown as soon as it is on the TV
            deck = _decks[tv.id] = Deck(album.id, album.shuffle, now - timedelta(minutes=album.interval))
    if now - deck.last_change < timedelta(minutes=album.interval):
        return False
    client = client_factory(tv)
    try:
        with client.session(wait=BUSY_WAIT):
            if client.state() != "art":
                return False  # screen turned off by the sensor, in use or off: retry next round
            items = playlist(db, tv.id, album)
            if not items:
                return False  # nothing uploaded yet: retry next round
            content_id = next_content(deck, items, rng)
            if content_id == deck.current:
                deck.last_change = now
                return False
            client.select(content_id)
    except TvError as exc:
        if exc.code != "tv_busy":
            tv.last_error = exc.code
            db.commit()
        return False
    deck.current, deck.last_change = content_id, now
    return True


def reset() -> None:
    with _guard:
        _decks.clear()
