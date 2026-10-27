"""Rotación por la app para intervalos menores que el mínimo del TV (fase 11.2).

El slideshow nativo no baja de 10 minutos. Para 1-5 minutos el supervisor lo desactiva y esta tarea muestra la
siguiente imagen con select_image. Cambiar de imagen, e incluso conectarse al canal de arte, enciende la pantalla
aunque el sensor de movimiento la haya apagado. Por eso solo se rota con el TV en estado "art": state() consulta
primero REST, que no responde con la pantalla apagada, y en ese caso no toca el canal de arte.

El orden vive en memoria por TV: un reinicio empieza un mazo nuevo.
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
from app.services.tv_client import NATIVE_MIN, TvError, client_for

logger = logging.getLogger("rotation")

# Espera máxima por el canal de arte: si el supervisor está subiendo fotos, se prueba en la vuelta siguiente
BUSY_WAIT = 2


def app_driven(album: Album) -> bool:
    return album.interval < NATIVE_MIN


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
    """content_id en el TV de la salida actual del álbum, en su orden. No incluye fotos ajenas ni retiradas."""
    on_tv = {row_key(r): r.content_id for r in db.query(TvContent).filter(TvContent.tv_id == tv_id)}
    return [on_tv[item.key] for item in effective_output(db, album).items if item.key in on_tv]


def next_content(deck: Deck, items: list, rng=random) -> str:
    """Siguiente imagen: la que sigue a la actual o, en aleatorio, la siguiente de un mazo barajado que no se
    repite hasta agotarse ni vuelve a empezar por la que se está viendo."""
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
    """Cambia la imagen si toca. Devuelve True si la cambió."""
    now = now or datetime.now()
    slots = db.query(ScheduleSlot).filter(ScheduleSlot.tv_id == tv.id).all()
    slot = active_slot(slots, now)
    album = db.get(Album, slot.album_id) if slot else None
    with _guard:
        if not album or not app_driven(album):
            _decks.pop(tv.id, None)
            return False
        deck = _decks.get(tv.id)
        if not deck or deck.album_id != album.id or deck.shuffle != album.shuffle:
            # Álbum nuevo en la franja: el primer cambio llega tras un intervalo completo
            _decks[tv.id] = Deck(album.id, album.shuffle, now)
            return False
    if now - deck.last_change < timedelta(minutes=album.interval):
        return False
    client = client_factory(tv)
    try:
        with client.session(wait=BUSY_WAIT):
            if client.state() != "art":
                return False  # pantalla apagada por el sensor, en uso o apagado: se reintenta en la vuelta siguiente
            items = playlist(db, tv.id, album)
            if len(items) < 2:
                deck.last_change = now
                return False
            content_id = next_content(deck, items, rng)
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
