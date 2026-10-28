"""Detects the main subject of a photo with Gemini, to steer the crops.

- Optional per album (Album.subject_detection). The key and model are stored in data_dir/gemini.json.
- Sends a reduced copy (long side SEND_SIZE) re-encoded without EXIF, hence without GPS.
- Plain REST with httpx (the google-genai SDK requires Pydantic v2) and only to the API host.
- The result is stored per photo version: each photo is queried only once.
"""
import base64
import io
import json
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image as PILImage

from app.core.config import settings
from app.services.image_proc import heavy, open_reduced

logger = logging.getLogger("subject_ai")

API_HOST = "generativelanguage.googleapis.com"
API_BASE = f"https://{API_HOST}/v1beta/models/"
DEFAULT_MODEL = "gemini-flash-latest"  # Google alias for the current Flash model
DEFAULT_MAX_CALLS = 500  # requests per day
SEND_SIZE = 768
TIMEOUT = 30
_MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,63}$")

PROMPT = (
    "Find the main subjects of this photo: the people, faces, animals or the central object a viewer would "
    "look at. Ignore background elements. Return at most 8 subjects. Each box_2d is "
    "[ymin, xmin, ymax, xmax] normalized to 0-1000. Return an empty list if there is no clear subject."
)
SCHEMA = {
    "type": "OBJECT",
    "properties": {"subjects": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {"label": {"type": "STRING"}, "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}}},
        "required": ["box_2d"],
    }}},
    "required": ["subjects"],
}


class SubjectError(Exception):
    """Codes: gemini_key_missing, gemini_key_invalid, gemini_unreachable, gemini_response_invalid,
    gemini_quota_exceeded. Only gemini_response_invalid is specific to one photo; the others stop the batch."""


# ------------------------------------------------------------------ settings

def _config_path() -> Path:
    return Path(settings["data_dir"]) / "gemini.json"


def _usage_path() -> Path:
    return Path(settings["data_dir"]) / "gemini_usage.json"


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)  # the key must not be readable by other NAS users
    except OSError:
        pass
    tmp.replace(path)


def config() -> dict:
    data = _read(_config_path())
    return {
        "api_key": str(data.get("api_key") or ""),
        "model": str(data.get("model") or DEFAULT_MODEL),
        "max_calls_per_day": int(data.get("max_calls_per_day") or DEFAULT_MAX_CALLS),
    }


def configured() -> bool:
    return bool(config()["api_key"])


def save_config(api_key: Optional[str] = None, model: Optional[str] = None,
                max_calls_per_day: Optional[int] = None) -> dict:
    """Update the given fields; an empty api_key clears the key. ValueError with the code if invalid."""
    data = config()
    if api_key is not None:
        api_key = api_key.strip()
        if api_key and not re.match(r"^[A-Za-z0-9_\-]{20,128}$", api_key):
            raise ValueError("gemini_key_invalid")
        data["api_key"] = api_key
    if model is not None:
        model = model.strip()
        if not _MODEL_RE.match(model):
            raise ValueError("invalid_gemini_model")
        data["model"] = model
    if max_calls_per_day is not None:
        if not 1 <= max_calls_per_day <= 100000:
            raise ValueError("invalid_gemini_limit")
        data["max_calls_per_day"] = max_calls_per_day
    _write(_config_path(), data)
    return data


def calls_today() -> int:
    usage = _read(_usage_path())
    return int(usage.get("calls") or 0) if usage.get("day") == date.today().isoformat() else 0


def _count_call() -> None:
    _write(_usage_path(), {"day": date.today().isoformat(), "calls": calls_today() + 1})


def public_view() -> dict:
    cfg = config()
    key = cfg["api_key"]
    return {"configured": bool(key), "key_hint": key[-4:] if key else "", "model": cfg["model"],
            "max_calls_per_day": cfg["max_calls_per_day"], "calls_today": calls_today()}


# --------------------------------------------------------------------- consulta

def _client(client: Optional[httpx.Client]) -> httpx.Client:
    return client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)


def _check_status(resp: httpx.Response) -> None:
    if resp.status_code in (401, 403):
        raise SubjectError("gemini_key_invalid")
    if resp.status_code == 429:
        raise SubjectError("gemini_quota_exceeded")
    if resp.status_code == 404:
        raise SubjectError("invalid_gemini_model")
    if resp.status_code >= 500 or resp.status_code in (408, 409):
        raise SubjectError("gemini_unreachable")
    if resp.status_code != 200:
        # 400: the model rejects the request or the image; specific to this photo
        raise SubjectError("gemini_response_invalid")


def test_connection(client: Optional[httpx.Client] = None) -> None:
    """Check the key and model without sending photos (queries the model metadata)."""
    cfg = config()
    if not cfg["api_key"]:
        raise SubjectError("gemini_key_missing")
    own = client is None
    client = _client(client)
    try:
        resp = client.get(API_BASE + cfg["model"], headers={"x-goog-api-key": cfg["api_key"]})
    except httpx.HTTPError:
        raise SubjectError("gemini_unreachable") from None
    finally:
        if own:
            client.close()
    _check_status(resp)


def _payload(path: Path) -> str:
    """Reduced, oriented JPEG without metadata, in base64."""
    with heavy():
        img = open_reduced(path, (SEND_SIZE, SEND_SIZE))
        try:
            img.thumbnail((SEND_SIZE, SEND_SIZE), PILImage.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)  # no exif=: no metadata is copied
        finally:
            img.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")


def parse_boxes(data: dict) -> Optional[list]:
    """Union of the boxes as [x0, y0, x1, y1] in fractions of the photo, or None if there is no subject.

    SubjectError("gemini_response_invalid") if the response does not have the requested format."""
    try:
        text = "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
        subjects = json.loads(text)["subjects"]
        if not isinstance(subjects, list):
            raise ValueError
        boxes = []
        for subject in subjects[:20]:
            ymin, xmin, ymax, xmax = (int(v) for v in subject["box_2d"])
            if not (0 <= xmin < xmax <= 1000 and 0 <= ymin < ymax <= 1000):
                continue
            boxes.append((xmin, ymin, xmax, ymax))
    except (KeyError, IndexError, TypeError, ValueError):
        raise SubjectError("gemini_response_invalid") from None
    if not boxes:
        return None
    return [round(min(b[0] for b in boxes) / 1000, 3), round(min(b[1] for b in boxes) / 1000, 3),
            round(max(b[2] for b in boxes) / 1000, 3), round(max(b[3] for b in boxes) / 1000, 3)]


def detect(path: Path, client: Optional[httpx.Client] = None) -> Optional[list]:
    """Box of the photo's main subject ([x0, y0, x1, y1] in 0-1) or None if there is none."""
    cfg = config()
    if not cfg["api_key"]:
        raise SubjectError("gemini_key_missing")
    if calls_today() >= cfg["max_calls_per_day"]:
        raise SubjectError("gemini_quota_exceeded")
    body = {
        "contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": _payload(path)}},
                                {"text": PROMPT}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    own = client is None
    client = _client(client)
    try:
        _count_call()
        resp = client.post(API_BASE + cfg["model"] + ":generateContent", json=body,
                           headers={"x-goog-api-key": cfg["api_key"]})
    except httpx.HTTPError as exc:
        logger.warning("Gemini: %s", type(exc).__name__)
        raise SubjectError("gemini_unreachable") from None
    finally:
        if own:
            client.close()
    _check_status(resp)
    try:
        data = resp.json()
    except ValueError:
        raise SubjectError("gemini_response_invalid") from None
    return parse_boxes(data)
