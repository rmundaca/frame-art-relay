"""Source scanning and thumbnails for album images."""
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.schemas import Album, AlbumSource, Image
from app.services import source_icloud, source_local
from app.services.image_proc import image_meta, make_thumbnail

logger = logging.getLogger("albums")


def thumb_path(image_id: int) -> Path:
    return Path(settings["data_dir"]) / "thumbs" / f"{image_id}.jpg"


def album_images(db: Session, album: Album) -> list:
    """Included images that may go to the TV, capped per album, ordered by key."""
    limit = int(settings.get("frame", {}).get("max_images_per_album", 100))
    return (db.query(Image).filter(Image.album_id == album.id, Image.excluded.is_(False))
            .order_by(Image.key).limit(limit).all())


def image_file(db: Session, image: Image) -> Path:
    source = db.get(AlbumSource, image.source_id)
    if source.kind == "icloud":
        return source_icloud.file_path(source.id, image.key)
    return source_local.file_path(source.path, image.key)


def ensure_meta(db: Session, image: Image) -> bool:
    """Read the oriented dimensions and date taken from the header, once. False if it failed."""
    if image.width and image.height and image.taken_at is not None:
        return True
    try:
        image.width, image.height, image.taken_at = image_meta(image_file(db, image))
    except (ValueError, OSError) as exc:
        logger.info("No metadata for %s: %s", image.key, exc)
        # Unreadable: no date, so the output is not blocked; retried when the file changes
        image.taken_at = ""
        return False
    return True


def wants_date(db: Session, album: Album, image: Image) -> bool:
    """The date stamp only applies to iCloud photos in albums that have it turned on."""
    return bool(album.date_stamp) and db.get(AlbumSource, image.source_id).kind == "icloud"


def date_label(db: Session, album: Album, image: Image) -> str:
    """"YYYY-MM-DD" to draw on the photo, or "" if it has no date."""
    return (image.taken_at or "")[:10] if wants_date(db, album, image) else ""


def fill_meta(db: Session, album: Album) -> None:
    """Fill in pending metadata for the photos that go to the TV (after a rescan or a database migration)."""
    changed = False
    for image in album_images(db, album):
        if image.taken_at is None:
            ensure_meta(db, image)
            changed = True
    if changed:
        db.commit()


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
    """Sync Image rows with the files; keep the "excluded" flag of the ones that remain."""
    try:
        found = {key: (size, mtime) for key, size, mtime in _scan(source)}
        source.last_error = None
    except (ValueError, OSError, source_icloud.ICloudError) as exc:
        logger.warning("Could not scan %s: %s", source.path, exc)
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
            img.width = img.height = img.taken_at = None
            thumb_path(img.id).unlink(missing_ok=True)
    for key, (size, mtime) in found.items():
        if key not in existing:
            db.add(Image(album_id=source.album_id, source_id=source.id, key=key, size=size, mtime=mtime))
    source.last_scan = datetime.utcnow()
    db.commit()


def rescan_all(db: Session) -> None:
    for source in db.query(AlbumSource).all():
        rescan_source(db, source)
