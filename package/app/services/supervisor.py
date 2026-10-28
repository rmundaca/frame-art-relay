"""Decides what to do with each TV based on its state and the active slot (runs every minute)."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.schemas import Album, ScheduleSlot, Tv
from app.services.schedule import active_slot
from app.services.sync import sync_tv
from app.services.tv_client import NATIVE_MIN, TvError, client_for

logger = logging.getLogger("supervisor")


def rotation_signature(album: Album) -> str:
    return f"{album.id}:{album.interval}:{int(album.shuffle)}"


def native_minutes(album: Album) -> int:
    """Native slideshow interval; 0 (off) when the app does the rotation."""
    return album.interval if album.interval >= NATIVE_MIN else 0


def tick(db: Session, tv: Tv, now: datetime = None, client_factory=client_for) -> None:
    client = client_factory(tv)
    try:
        with client.session(wait=5):
            state = client.state()
            tv.last_state = state
            if state != "offline":
                tv.last_seen = datetime.utcnow()
            else:
                # When it comes back on, the rotation is re-applied
                tv.applied = None

            slots = db.query(ScheduleSlot).filter(ScheduleSlot.tv_id == tv.id).all()
            slot = active_slot(slots, now or datetime.now())
            if slot:
                if state == "offline" and tv.mac:
                    client.wake(tv.mac)
                elif state == "art":
                    album = db.get(Album, slot.album_id)
                    result = sync_tv(db, tv, album, client)
                    sig = rotation_signature(album)
                    if result.on_tv and (result.changed or tv.applied != sig):
                        client.set_rotation(native_minutes(album), album.shuffle)
                        tv.applied = sig
                    if result.changed:
                        logger.info("TV %s: +%d -%d (pendientes %d)", tv.name, result.uploaded,
                                    result.deleted, result.pending)
            elif state == "art" and tv.applied != "off":
                # Outside the schedule: no rotation and art mode; the motion sensor turns the screen off
                client.set_rotation(0, False)
                tv.applied = "off"
        tv.last_error = None
    except TvError as exc:
        if exc.code != "tv_busy":
            tv.last_error = exc.code
    except Exception as exc:  # noqa: BLE001 - the supervisor must not crash because of one TV
        logger.exception("Supervisor TV %s", tv.name)
        tv.last_error = type(exc).__name__
    finally:
        db.commit()