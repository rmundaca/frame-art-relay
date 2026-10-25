"""Sincroniza "Mis fotos" de un TV con el álbum de la franja activa."""
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.schemas import Album, Image, TvContent
from app.services.albums import image_file
from app.services.image_proc import prepare_for_frame

logger = logging.getLogger("sync")


@dataclass
class SyncResult:
    uploaded: int = 0
    deleted: int = 0
    pending: int = 0
    on_tv: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.uploaded or self.deleted)


def album_images(db: Session, album: Album) -> list:
    limit = int(settings.get("frame", {}).get("max_images_per_album", 100))
    return (db.query(Image).filter(Image.album_id == album.id, Image.excluded.is_(False))
            .order_by(Image.key).limit(limit).all())


def reconcile(db: Session, tv_id: int, on_tv: set) -> list:
    """Olvida las subidas que ya no están en el TV (borradas a mano) y devuelve las que siguen."""
    rows = db.query(TvContent).filter(TvContent.tv_id == tv_id).all()
    alive = []
    for row in rows:
        if row.content_id in on_tv:
            alive.append(row)
        else:
            db.delete(row)
    db.commit()
    return alive


def sync_tv(db: Session, tv, album: Album, client) -> SyncResult:
    """Borra del TV lo que subió la app y ya no pertenece al álbum, y sube lo que falta (por tandas)."""
    result = SyncResult()
    rows = reconcile(db, tv.id, {p["content_id"] for p in client.my_photos()})

    desired = album_images(db, album)
    desired_ids = {img.id for img in desired}
    stale = [r for r in rows if r.image_id not in desired_ids]
    if stale:
        client.delete([r.content_id for r in stale])
        on_tv = {p["content_id"] for p in client.my_photos()}
        result.deleted = sum(1 for r in stale if r.content_id not in on_tv)
        rows = reconcile(db, tv.id, on_tv)

    have = {r.image_id for r in rows}
    missing = [img for img in desired if img.id not in have]
    batch = int(settings.get("frame", {}).get("uploads_per_tick", 10))
    for img in missing[:batch]:
        try:
            data = prepare_for_frame(image_file(db, img))
        except (ValueError, OSError) as exc:
            logger.warning("Imagen %s omitida: %s", img.key, exc)
            continue
        content_id = client.upload(data, album.matte)
        db.add(TvContent(tv_id=tv.id, image_id=img.id, content_id=content_id))
        db.commit()
        result.uploaded += 1
    result.pending = max(0, len(missing) - batch)
    result.on_tv = len(rows) + result.uploaded
    return result
