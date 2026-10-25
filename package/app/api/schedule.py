from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.schemas import Album, ScheduleSlot, Tv
from app.services.schedule import parse_hhmm, slots_overlap

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class SlotIn(BaseModel):
    tv_id: int
    album_id: int
    days: int = 127
    start: str
    end: str
    enabled: bool = True


class SlotPatch(BaseModel):
    tv_id: Optional[int] = None
    album_id: Optional[int] = None
    days: Optional[int] = None
    start: Optional[str] = None
    end: Optional[str] = None
    enabled: Optional[bool] = None


def slot_view(s: ScheduleSlot) -> dict:
    return {"id": s.id, "tv_id": s.tv_id, "album_id": s.album_id, "days": s.days,
            "start": s.start, "end": s.end, "enabled": s.enabled}


def _validate(db: Session, slot: ScheduleSlot) -> None:
    if not db.get(Tv, slot.tv_id) or not db.get(Album, slot.album_id):
        raise HTTPException(400, "not_found")
    if not 1 <= slot.days <= 127:
        raise HTTPException(400, "invalid_days")
    try:
        start, end = parse_hhmm(slot.start), parse_hhmm(slot.end)
    except ValueError:
        raise HTTPException(400, "invalid_time")
    if start == end:
        raise HTTPException(400, "invalid_time_range")
    others = db.query(ScheduleSlot).filter(ScheduleSlot.tv_id == slot.tv_id, ScheduleSlot.id != (slot.id or 0))
    if slot.enabled:
        for other in others.filter(ScheduleSlot.enabled.is_(True)):
            if slots_overlap((slot.days, slot.start, slot.end), (other.days, other.start, other.end)):
                raise HTTPException(409, "slot_overlap")


@router.get("")
def list_slots(db: Session = Depends(get_db)):
    return [slot_view(s) for s in db.query(ScheduleSlot).order_by(ScheduleSlot.tv_id, ScheduleSlot.start)]


@router.post("")
def create_slot(req: SlotIn, db: Session = Depends(get_db)):
    slot = ScheduleSlot(**req.dict())
    _validate(db, slot)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot_view(slot)


@router.patch("/{slot_id}")
def update_slot(slot_id: int, req: SlotPatch, db: Session = Depends(get_db)):
    slot = db.get(ScheduleSlot, slot_id)
    if not slot:
        raise HTTPException(404, "not_found")
    for key, value in req.dict(exclude_none=True).items():
        setattr(slot, key, value)
    try:
        _validate(db, slot)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return slot_view(slot)


@router.delete("/{slot_id}")
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.get(ScheduleSlot, slot_id)
    if not slot:
        raise HTTPException(404, "not_found")
    db.delete(slot)
    db.commit()
    return {"ok": True}
