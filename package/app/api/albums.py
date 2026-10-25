from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.schemas import Album, AlbumSource, Image
from app.schedulers.tasks import refresh_source, run_now
from app.services import source_icloud, source_local
from app.services.albums import image_thumbnail, rescan_source, thumb_path
from app.services.tv_client import INTERVALS, MATTES

router = APIRouter(prefix="/api", tags=["albums"])


class AlbumIn(BaseModel):
    name: str
    matte: str = "none"
    shuffle: bool = True
    interval: int = 60


class AlbumPatch(BaseModel):
    name: Optional[str] = None
    matte: Optional[str] = None
    shuffle: Optional[bool] = None
    interval: Optional[int] = None


class SourceIn(BaseModel):
    kind: str = "local"
    path: str
    recursive: bool = False


class ImagePatch(BaseModel):
    excluded: bool


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def source_view(s: AlbumSource) -> dict:
    return {"id": s.id, "kind": s.kind, "path": s.path, "label": s.label, "recursive": s.recursive,
            "last_scan": _iso(s.last_scan), "last_error": s.last_error}


def album_view(album: Album, db: Session) -> dict:
    included_expr = func.coalesce(func.sum(case((Image.excluded.is_(False), 1), else_=0)), 0)
    total, included = db.query(func.count(Image.id), included_expr).filter(Image.album_id == album.id).one()
    return {
        "id": album.id, "name": album.name, "matte": album.matte, "shuffle": album.shuffle,
        "interval": album.interval, "images": total, "included": int(included),
        "sources": [source_view(s) for s in album.sources],
    }


def image_view(img: Image) -> dict:
    return {"id": img.id, "key": img.key, "excluded": img.excluded, "source_id": img.source_id}


def _get_album(db: Session, album_id: int) -> Album:
    album = db.get(Album, album_id)
    if not album:
        raise HTTPException(404, "not_found")
    return album


def _apply(album: Album, name=None, matte=None, shuffle=None, interval=None):
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(400, "invalid_name")
        album.name = name[:60]
    if matte is not None:
        if matte not in MATTES:
            raise HTTPException(400, "invalid_matte")
        album.matte = matte
    if shuffle is not None:
        album.shuffle = shuffle
    if interval is not None:
        if interval not in INTERVALS:
            raise HTTPException(400, "invalid_interval")
        album.interval = interval


@router.get("/meta")
def meta():
    return {"mattes": MATTES, "intervals": INTERVALS, "roots": source_local.roots(),
            "max_images": int(settings.get("frame", {}).get("max_images_per_album", 100))}


@router.get("/browse")
def browse(path: str = ""):
    try:
        return source_local.browse(path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except OSError:
        raise HTTPException(400, "invalid_path")


@router.get("/albums")
def list_albums(db: Session = Depends(get_db)):
    return [album_view(a, db) for a in db.query(Album).order_by(Album.name).all()]


@router.post("/albums")
def create_album(req: AlbumIn, db: Session = Depends(get_db)):
    album = Album()
    _apply(album, req.name, req.matte, req.shuffle, req.interval)
    db.add(album)
    db.commit()
    db.refresh(album)
    return album_view(album, db)


@router.patch("/albums/{album_id}")
def update_album(album_id: int, req: AlbumPatch, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    _apply(album, req.name, req.matte, req.shuffle, req.interval)
    db.commit()
    return album_view(album, db)


@router.delete("/albums/{album_id}")
def delete_album(album_id: int, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    for (image_id,) in db.query(Image.id).filter(Image.album_id == album.id):
        thumb_path(image_id).unlink(missing_ok=True)
    for source in album.sources:
        if source.kind == "icloud":
            source_icloud.remove_cache(source.id)
    db.delete(album)
    db.commit()
    return {"ok": True}


@router.post("/albums/{album_id}/sources")
def add_source(album_id: int, req: SourceIn, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    if req.kind == "icloud":
        return _add_icloud_source(db, album, req.path)
    if req.kind != "local":
        raise HTTPException(400, "invalid_path")
    try:
        path = source_local.resolve(req.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if any(s.path == path for s in album.sources):
        raise HTTPException(409, "source_exists")
    source = AlbumSource(album_id=album.id, kind="local", path=path, recursive=req.recursive)
    db.add(source)
    db.commit()
    rescan_source(db, source)
    db.refresh(album)
    return album_view(album, db)


def _add_icloud_source(db: Session, album: Album, url: str) -> dict:
    try:
        token = source_icloud.parse_token(url)
        # Validación rápida (álbum público y nombre); la descarga sigue en segundo plano
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            _, name, _ = source_icloud.fetch_stream(client, token)
    except source_icloud.ICloudError as exc:
        raise HTTPException(400, str(exc))
    url = f"https://www.icloud.com/sharedalbum/#{token}"
    if any(s.path == url for s in album.sources):
        raise HTTPException(409, "source_exists")
    source = AlbumSource(album_id=album.id, kind="icloud", path=url, label=name or None)
    db.add(source)
    db.commit()
    run_now(refresh_source, source.id)
    db.refresh(album)
    return album_view(album, db)


@router.delete("/albums/{album_id}/sources/{source_id}")
def delete_source(album_id: int, source_id: int, db: Session = Depends(get_db)):
    source = db.get(AlbumSource, source_id)
    if not source or source.album_id != album_id:
        raise HTTPException(404, "not_found")
    for (image_id,) in db.query(Image.id).filter(Image.source_id == source.id):
        thumb_path(image_id).unlink(missing_ok=True)
    if source.kind == "icloud":
        source_icloud.remove_cache(source.id)
    db.delete(source)
    db.commit()
    return album_view(_get_album(db, album_id), db)


@router.post("/albums/{album_id}/rescan")
def rescan(album_id: int, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    for source in album.sources:
        if source.kind == "icloud":
            run_now(refresh_source, source.id)
        else:
            rescan_source(db, source)
    db.refresh(album)
    return album_view(album, db)


@router.get("/albums/{album_id}/images")
def list_images(album_id: int, db: Session = Depends(get_db)):
    _get_album(db, album_id)
    return [image_view(i) for i in db.query(Image).filter(Image.album_id == album_id).order_by(Image.key)]


@router.patch("/images/{image_id}")
def update_image(image_id: int, req: ImagePatch, db: Session = Depends(get_db)):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(404, "not_found")
    img.excluded = req.excluded
    db.commit()
    return image_view(img)


@router.get("/images/{image_id}/thumb")
def image_thumb(image_id: int, db: Session = Depends(get_db)):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(404, "not_found")
    try:
        path = image_thumbnail(db, img)
    except (ValueError, OSError):
        raise HTTPException(404, "not_found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})
