from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.schemas import Album
from app.schedulers.tasks import compose_album, run_now
from app.services import subject_ai

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AiSettingsIn(BaseModel):
    api_key: Optional[str] = None  # "" clears the key; None leaves it unchanged
    model: Optional[str] = None
    max_calls_per_day: Optional[int] = None


@router.get("/ai")
def get_ai():
    # The key is never returned: only whether it is set and its last four characters
    return subject_ai.public_view()


@router.put("/ai")
def put_ai(req: AiSettingsIn, db: Session = Depends(get_db)):
    try:
        subject_ai.save_config(req.api_key, req.model, req.max_calls_per_day)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    # Albums waiting on a Gemini error retry right away with the new settings
    for (album_id,) in db.query(Album.id).filter(Album.subject_detection.is_(True)):
        run_now(compose_album, album_id)
    return subject_ai.public_view()


@router.post("/ai/test")
def test_ai():
    try:
        subject_ai.test_connection()
    except subject_ai.SubjectError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}
