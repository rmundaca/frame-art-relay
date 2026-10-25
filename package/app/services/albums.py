"""Escaneo de fuentes y miniaturas de las imágenes de los álbumes."""
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.schemas import AlbumSource, Image
from app.services import source_icloud, source_local
from app.services.image_proc import make_thumbnail

logger = logging.getLogger("albums")


def thumb_path(image_id: int) -> Path:
    return Path(settings["data_dir"]) / "thumbs" / f"{image_id}.jpg"


def image_file(db: Session, image: Image) -> Path:
    source = db.get(AlbumSource, image.source_id)
    if source.kind == "icloud":
        return source_icloud.file_path(source.id, image.key)
    return source_local.file_path(source.path, image.key)


def image_thumbnail(db: Session, image: Image) -> Path:
    path = thumb_path(image.id)
    if not path.exists():
        make_thumbnail(image_file(db, image), path)
    return path


def _scan(source: AlbumSource) -> list:
    if source.kind == "icloud":
        name, found = source_icloud.refresh(source.id, source.path)
        source.label = name or source.label
        return found
    return source_local.scan(source.path, source.recursive)


def rescan_source(db: Session, source: AlbumSource) -> None:
    """Sincroniza las filas Image con los archivos; conserva el estado "excluida" de las que siguen."""
    try:
        found = {key: (size, mtime) for key, size, mtime in _scan(source)}
        source.last_error = None
    except (ValueError, OSError, source_icloud.ICloudError) as exc:
        logger.warning("No se pudo escanear %s: %s", source.path, exc)
        source.last_error = str(exc) if isinstance(exc, (ValueError, source_icloud.ICloudError)) else "invalid_path"
        source.last_scan = datetime.utcnow()
        db.commit()
        return
    existing = {img.key: img for img in db.query(Image).filter(Image.source_id == source.id)}
    for key, img in existing.items():
        if key not in found:
            thumb_path(img.id).unlink(missing_ok=True)
            db.delete(img)
        elif (img.size, img.mtime) != found[key]:
            img.size, img.mtime = found[key]
            thumb_path(img.id).unlink(missing_ok=True)
    for key, (size, mtime) in found.items():
        if key not in existing:
            db.add(Image(album_id=source.album_id, source_id=source.id, key=key, size=size, mtime=mtime))
    source.last_scan = datetime.utcnow()
    db.commit()


def rescan_all(db: Session) -> None:
    for source in db.query(AlbumSource).all():
        rescan_source(db, source)
