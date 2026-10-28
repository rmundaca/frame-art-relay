from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.schemas import Album, AlbumSource, CompositionPage, Image
from app.schedulers.tasks import compose_album, refresh_source, run_now
from app.services import composition, source_icloud, source_local, subject_ai
from app.services.albums import image_thumbnail, rescan_source, thumb_path
from app.services.tv_client import INTERVALS, MATTES

router = APIRouter(prefix="/api", tags=["albums"])


class AlbumIn(BaseModel):
    name: str
    matte: str = "none"
    shuffle: bool = True
    interval: int = 60
    composition_mode: str = "off"
    date_stamp: bool = True
    background: str = "paper"
    single_fit: str = "crop"
    subject_detection: bool = False


class AlbumPatch(BaseModel):
    name: Optional[str] = None
    matte: Optional[str] = None
    shuffle: Optional[bool] = None
    interval: Optional[int] = None
    composition_mode: Optional[str] = None
    date_stamp: Optional[bool] = None
    background: Optional[str] = None
    single_fit: Optional[str] = None
    subject_detection: Optional[bool] = None


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
    output = composition.effective_output(db, album)
    return {
        "id": album.id, "name": album.name, "matte": album.matte, "shuffle": album.shuffle,
        "interval": album.interval, "images": total, "included": int(included),
        "composition_mode": album.composition_mode, "date_stamp": album.date_stamp,
        "background": album.background, "single_fit": album.single_fit,
        "subject_detection": album.subject_detection, "subject_error": album.subject_error,
        # Original photos that go to the TV (capped) and final images after grouping
        "output": {"photos": output.photos, "total": output.total, "pending": output.pending,
                   "errors": output.errors, "error": output.error, "current": output.current},
        "sources": [source_view(s) for s in album.sources],
    }


def image_view(img: Image) -> dict:
    return {"id": img.id, "key": img.key, "excluded": img.excluded, "source_id": img.source_id}


def _get_album(db: Session, album_id: int) -> Album:
    album = db.get(Album, album_id)
    if not album:
        raise HTTPException(404, "not_found")
    return album


def page_view(page: CompositionPage, db: Session) -> dict:
    members = []
    for m in page.members:
        img = db.get(Image, m.image_id)
        members.append({"id": img.id, "key": img.key, "excluded": img.excluded})
    return {"id": page.id, "template": page.template, "revision": page.revision, "status": page.status,
            "last_error": page.last_error, "rendered_revision": page.rendered_revision,
            "members": members}


def _apply(album: Album, name=None, matte=None, shuffle=None, interval=None, composition_mode=None,
           date_stamp=None, background=None, single_fit=None, subject_detection=None):
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
    if composition_mode is not None:
        if composition_mode not in composition.MODES:
            raise HTTPException(400, "invalid_composition_mode")
        album.composition_mode = composition_mode
    if date_stamp is not None:
        album.date_stamp = date_stamp
    if background is not None:
        if background not in composition.BACKGROUNDS:
            raise HTTPException(400, "invalid_background")
        album.background = background
    if single_fit is not None:
        if single_fit not in composition.SINGLE_FITS:
            raise HTTPException(400, "invalid_single_fit")
        album.single_fit = single_fit
    if subject_detection is not None:
        if subject_detection and not album.subject_detection and not subject_ai.configured():
            raise HTTPException(400, "gemini_key_missing")
        if subject_detection != album.subject_detection:
            album.subject_error = None
        album.subject_detection = subject_detection


@router.get("/meta")
def meta():
    return {"mattes": MATTES, "intervals": INTERVALS, "roots": source_local.roots(), "ai": subject_ai.configured(),
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
    _apply(album, req.name, req.matte, req.shuffle, req.interval, req.composition_mode, req.date_stamp,
           req.background, req.single_fit, req.subject_detection)
    db.add(album)
    db.commit()
    db.refresh(album)
    return album_view(album, db)


@router.patch("/albums/{album_id}")
def update_album(album_id: int, req: AlbumPatch, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    before = (album.composition_mode, album.date_stamp, album.background, album.single_fit, album.subject_detection)
    _apply(album, req.name, req.matte, req.shuffle, req.interval, req.composition_mode, req.date_stamp,
           req.background, req.single_fit, req.subject_detection)
    db.commit()
    if (album.composition_mode, album.date_stamp, album.background, album.single_fit,
            album.subject_detection) != before:
        # Turning it on groups photos and turning it off retires the pages; date, background and subject change the
        # page signature and "fit" needs the dimensions. The TV switches once the new output is ready
        run_now(compose_album, album.id)
    return album_view(album, db)


@router.delete("/albums/{album_id}")
def delete_album(album_id: int, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    for (image_id,) in db.query(Image.id).filter(Image.album_id == album.id):
        thumb_path(image_id).unlink(missing_ok=True)
    for source in album.sources:
        if source.kind == "icloud":
            source_icloud.remove_cache(source.id)
    composition.remove_cache(album.id)
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
    run_now(compose_album, album.id)
    db.refresh(album)
    return album_view(album, db)


def _add_icloud_source(db: Session, album: Album, url: str) -> dict:
    try:
        url = source_icloud.canonical_url(url)
        # Quick validation (public album and name); the download continues in the background
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            name = source_icloud.album_name(client, url)
    except source_icloud.ICloudError as exc:
        raise HTTPException(400, str(exc))
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
    run_now(compose_album, album_id)
    return album_view(_get_album(db, album_id), db)


@router.post("/albums/{album_id}/rescan")
def rescan(album_id: int, db: Session = Depends(get_db)):
    album = _get_album(db, album_id)
    for source in album.sources:
        if source.kind == "icloud":
            run_now(refresh_source, source.id)
        else:
            rescan_source(db, source)
    # iCloud sources regroup when their download finishes; this groups whatever is already there
    run_now(compose_album, album.id)
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
    run_now(compose_album, img.album_id)
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


@router.get("/albums/{album_id}/pages")
def list_pages(album_id: int, db: Session = Depends(get_db)):
    _get_album(db, album_id)
    return [page_view(p, db) for p in composition.active_pages(db, album_id)]


@router.post("/albums/{album_id}/compose")
def compose(album_id: int, db: Session = Depends(get_db)):
    """Regroup and render whatever is pending, including pages with errors."""
    album = _get_album(db, album_id)
    if album.composition_mode != "auto":
        raise HTTPException(400, "invalid_composition_mode")
    for page in composition.active_pages(db, album.id):
        if page.status == "error":
            page.status, page.last_error = "pending", None
    db.commit()
    run_now(compose_album, album.id)
    return album_view(album, db)


def _page_asset(db: Session, page_id: int, rev: Optional[int], thumb: bool):
    page = db.get(CompositionPage, page_id)
    if not page:
        raise HTTPException(404, "not_found")
    revision = rev or page.rendered_revision
    if not revision:
        raise HTTPException(404, "not_found")
    path = (composition.page_thumb if thumb else composition.page_file)(page.album_id, page.id, revision)
    if not path.exists():
        raise HTTPException(404, "not_found")
    # Each revision has its own file and never changes
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})


@router.get("/pages/{page_id}/thumb")
def page_thumb(page_id: int, rev: Optional[int] = None, db: Session = Depends(get_db)):
    return _page_asset(db, page_id, rev, thumb=True)


@router.get("/pages/{page_id}/image")
def page_image(page_id: int, rev: Optional[int] = None, db: Session = Depends(get_db)):
    """Generated JPEG exactly as it is uploaded to the TV."""
    return _page_asset(db, page_id, rev, thumb=False)
