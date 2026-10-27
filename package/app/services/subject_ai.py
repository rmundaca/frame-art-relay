"""Detección del sujeto principal de una foto con Gemini, para orientar los recortes (fase 11.4).

- Opcional por álbum (Album.subject_detection). La clave y el modelo se guardan en data_dir/gemini.json.
- Se envía una copia reducida (lado mayor SEND_SIZE) recodificada sin EXIF, por tanto sin GPS.
- REST directo con httpx (el SDK google-genai exige Pydantic v2) y solo al host de la API.
- El resultado se guarda por versión de la foto: cada foto se consulta una sola vez.
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
DEFAULT_MODEL = "gemini-flash-latest"  # alias de Google al Flash vigente
DEFAULT_MAX_CALLS = 500  # consultas por día
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
    """Códigos: gemini_key_missing, gemini_key_invalid, gemini_unreachable, gemini_response_invalid,
    gemini_quota_exceeded. Solo gemini_response_invalid es propio de una foto; los demás detienen la tanda."""


# ------------------------------------------------------------------ configuración

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
        os.chmod(tmp, 0o600)  # la clave no debe ser legible por otros usuarios del NAS
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
    """Actualiza los campos indicados; api_key vacía borra la clave. ValueError con el código si no es válido."""
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
        # 400: la petición o la imagen no le gustan al modelo; propio de esta foto
        raise SubjectError("gemini_response_invalid")


def test_connection(client: Optional[httpx.Client] = None) -> None:
    """Comprueba la clave y el modelo sin enviar fotos (consulta los datos del modelo)."""
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
    """JPEG reducido y orientado, sin metadatos, en base64."""
    with heavy():
        img = open_reduced(path, (SEND_SIZE, SEND_SIZE))
        try:
            img.thumbnail((SEND_SIZE, SEND_SIZE), PILImage.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)  # sin exif=: no se copia ningún metadato
        finally:
            img.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")


def parse_boxes(data: dict) -> Optional[list]:
    """Unión de los recuadros como [x0, y0, x1, y1] en fracciones de la foto, o None si no hay sujeto.

    SubjectError("gemini_response_invalid") si la respuesta no tiene el formato pedido."""
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
    """Recuadro del sujeto principal de la foto ([x0, y0, x1, y1] en 0-1) o None si no tiene."""
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
