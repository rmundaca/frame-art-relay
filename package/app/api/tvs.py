import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.schemas import Album, CompositionMember, CompositionPage, Image, ScheduleSlot, Tv, TvContent
from app.schedulers.tasks import compose_album, run_now, supervise_tv
from app.services.albums import thumb_path
from app.services.composition import page_thumb
from app.services.image_proc import make_thumbnail
from app.services.schedule import active_slot
from app.services.tv_client import TvError, client_for, token_path

router = APIRouter(prefix="/api/tvs", tags=["tvs"])

_HOST = re.compile(r"^[A-Za-z0-9.\-]{1,253}$")
_CONTENT_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class TvIn(BaseModel):
    name: str
    host: str


class TvPatch(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    enabled: Optional[bool] = None


class DeleteIn(BaseModel):
    content_ids: List[str]


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def tv_view(tv: Tv, db: Session) -> dict:
    slot = active_slot(db.query(ScheduleSlot).filter(ScheduleSlot.tv_id == tv.id).all(), datetime.now())
    album = db.get(Album, slot.album_id) if slot else None
    return {
        "id": tv.id, "name": tv.name, "host": tv.host, "mac": tv.mac, "model": tv.model,
        "paired": tv.paired, "enabled": tv.enabled, "state": tv.last_state, "last_seen": _iso(tv.last_seen),
        "last_error": tv.last_error,
        "uploaded": db.query(TvContent).filter(TvContent.tv_id == tv.id).count(),
        "active_album": {"id": album.id, "name": album.name} if album else None,
    }


def _get(db: Session, tv_id: int) -> Tv:
    tv = db.get(Tv, tv_id)
    if not tv:
        raise HTTPException(404, "not_found")
    return tv


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "invalid_name")
    return name[:60]


def _clean_host(host: str) -> str:
    host = (host or "").strip()
    if not _HOST.match(host):
        raise HTTPException(400, "invalid_host")
    return host


def _device_info(host: str) -> dict:
    try:
        resp = requests.get(f"http://{host}:8001/api/v2/", timeout=3)
        resp.raise_for_status()
        device = resp.json().get("device", {})
    except (requests.RequestException, ValueError):
        raise HTTPException(400, "tv_unreachable")
    if str(device.get("FrameTVSupport")).lower() != "true":
        raise HTTPException(400, "not_a_frame_tv")
    return device


def _tv_error(exc: TvError):
    return HTTPException(409, exc.code)


@router.get("")
def list_tvs(db: Session = Depends(get_db)):
    return [tv_view(tv, db) for tv in db.query(Tv).order_by(Tv.name).all()]


@router.post("")
def create_tv(req: TvIn, db: Session = Depends(get_db)):
    name, host = _clean_name(req.name), _clean_host(req.host)
    device = _device_info(host)
    tv = Tv(name=name, host=host, mac=device.get("wifiMac") or None, model=device.get("modelName"))
    db.add(tv)
    db.commit()
    db.refresh(tv)
    return tv_view(tv, db)


@router.patch("/{tv_id}")
def update_tv(tv_id: int, req: TvPatch, db: Session = Depends(get_db)):
    tv = _get(db, tv_id)
    if req.name is not None:
        tv.name = _clean_name(req.name)
    if req.host is not None and req.host.strip() != tv.host:
        host = _clean_host(req.host)
        device = _device_info(host)
        tv.host, tv.mac, tv.model = host, device.get("wifiMac") or tv.mac, device.get("modelName") or tv.model
    if req.enabled is not None:
        tv.enabled = req.enabled
    db.commit()
    return tv_view(tv, db)


@router.delete("/{tv_id}")
def delete_tv(tv_id: int, db: Session = Depends(get_db)):
    tv = _get(db, tv_id)
    token_path(tv.id).unlink(missing_ok=True)
    shutil.rmtree(_tv_thumb_path(tv.id, "x").parent, ignore_errors=True)
    db.delete(tv)
    db.commit()
    return {"ok": True}


@router.post("/{tv_id}/pair")
def pair_tv(tv_id: int, db: Session = Depends(get_db)):
    tv = _get(db, tv_id)
    try:
        ok = client_for(tv).pair()
    except TvError as exc:
        raise _tv_error(exc)
    if not ok:
        raise HTTPException(409, "pair_failed")
    tv.paired = True
    tv.last_error = None
    db.commit()
    return tv_view(tv, db)


@router.get("/{tv_id}/status")
def tv_status(tv_id: int, db: Session = Depends(get_db)):
    tv = _get(db, tv_id)
    try:
        tv.last_state = client_for(tv).state()
        if tv.last_state != "offline":
            tv.last_seen = datetime.utcnow()
        db.commit()
    except TvError:
        pass  # ocupado: se devuelve el último estado conocido
    return tv_view(tv, db)


@router.post("/{tv_id}/sync")
def sync_now(tv_id: int, db: Session = Depends(get_db)):
    _get(db, tv_id)
    run_now(supervise_tv, tv_id)
    return {"queued": True}


@router.get("/{tv_id}/gallery")
def gallery(tv_id: int, db: Session = Depends(get_db)):
    tv = _get(db, tv_id)
    try:
        photos = client_for(tv).my_photos()
    except TvError as exc:
        raise _tv_error(exc)
    managed = {r.content_id: r for r in db.query(TvContent).filter(TvContent.tv_id == tv.id)}
    names, pages = {}, {}
    image_ids = [r.image_id for r in managed.values() if r.image_id]
    if image_ids:
        rows = (db.query(Image.id, Image.key, Album.name).join(Album, Album.id == Image.album_id)
                .filter(Image.id.in_(image_ids)))
        names = {img_id: (key, album) for img_id, key, album in rows}
    page_ids = [r.page_id for r in managed.values() if r.page_id]
    if page_ids:
        rows = (db.query(CompositionPage.id, Album.name).join(Album, Album.id == CompositionPage.album_id)
                .filter(CompositionPage.id.in_(page_ids)))
        pages = dict(rows)
    items = []
    for p in photos:
        cid = p["content_id"]
        row = managed.get(cid)
        item = {"content_id": cid, "managed": row is not None, "image_id": None, "page_id": None,
                "page_revision": None, "members": 0, "name": None, "album": None, "date": p.get("image_date")}
        if row and row.page_id:
            item.update(page_id=row.page_id, page_revision=row.page_revision, album=pages.get(row.page_id),
                        members=db.query(CompositionMember).filter(CompositionMember.page_id == row.page_id).count())
        elif row:
            key, album = names.get(row.image_id, (None, None))
            item.update(image_id=row.image_id, name=key, album=album)
        items.append(item)
    return items


def _tv_thumb_path(tv_id: int, content_id: str) -> Path:
    return Path(settings["data_dir"]) / "tvthumbs" / str(tv_id) / f"{content_id}.jpg"


@router.get("/{tv_id}/gallery/{content_id}/thumb")
def gallery_thumb(tv_id: int, content_id: str, db: Session = Depends(get_db)):
    if not _CONTENT_ID.match(content_id):
        raise HTTPException(400, "invalid_content_ids")
    tv = _get(db, tv_id)
    row = db.query(TvContent).filter(TvContent.tv_id == tv.id, TvContent.content_id == content_id).first()
    if row and row.image_id and thumb_path(row.image_id).exists():
        return FileResponse(thumb_path(row.image_id), media_type="image/jpeg")
    if row and row.page_id:
        page = db.get(CompositionPage, row.page_id)
        if page and page_thumb(page.album_id, page.id, row.page_revision).exists():
            return FileResponse(page_thumb(page.album_id, page.id, row.page_revision), media_type="image/jpeg")
    path = _tv_thumb_path(tv.id, content_id)
    if not path.exists():
        try:
            # Con la API 0.97 la "miniatura" es la imagen casi completa: se reduce y se guarda
            make_thumbnail(client_for(tv).thumbnail(content_id), path)
        except TvError as exc:
            raise _tv_error(exc)
        except OSError:
            raise HTTPException(409, "thumbnail_failed")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@router.post("/{tv_id}/gallery/delete")
def gallery_delete(tv_id: int, req: DeleteIn, db: Session = Depends(get_db)):
    tv = _get(db, tv_id)
    ids = list(dict.fromkeys(req.content_ids))
    if not ids or len(ids) > 500 or not all(_CONTENT_ID.match(c) for c in ids):
        raise HTTPException(400, "invalid_content_ids")
    client = client_for(tv)
    try:
        with client.session():
            client.delete(ids)
            remaining = {p["content_id"] for p in client.my_photos()}
    except TvError as exc:
        raise _tv_error(exc)
    deleted = [c for c in ids if c not in remaining]
    if deleted:
        rows = db.query(TvContent).filter(TvContent.tv_id == tv.id, TvContent.content_id.in_(deleted)).all()
        image_ids = [r.image_id for r in rows if r.image_id]
        page_ids = [r.page_id for r in rows if r.page_id]
        if page_ids:
            # Borrar una composición excluye sus fotos; los archivos originales no se tocan
            image_ids += [i for (i,) in db.query(CompositionMember.image_id)
                          .filter(CompositionMember.page_id.in_(page_ids))]
        albums = set()
        if image_ids:
            # Se excluyen del álbum para que el supervisor no las vuelva a subir
            albums = {a for (a,) in db.query(Image.album_id).filter(Image.id.in_(image_ids)).distinct()}
            db.query(Image).filter(Image.id.in_(image_ids)).update({Image.excluded: True},
                                                                  synchronize_session=False)
        for row in rows:
            db.delete(row)
        db.commit()
        for album_id in albums:
            run_now(compose_album, album_id)
    for cid in deleted:
        _tv_thumb_path(tv.id, cid).unlink(missing_ok=True)
    tv.applied = None
    db.commit()
    return {"deleted": deleted, "failed": [c for c in ids if c in remaining]}
