"""Álbumes compartidos de iCloud con "Sitio web público": lectura sin credenciales vía sharedstreams.

Flujo: POST <base>/webstream (lista de fotos y derivados) -> POST <base>/webasseturls (URLs de descarga).
Si el álbum vive en otra partición, Apple responde 330 con el host correcto en "X-Apple-MMe-Host".
"""
import json
import logging
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.core.config import settings

logger = logging.getLogger("icloud")

_TOKEN = re.compile(r"#([A-Za-z0-9]{10,40})")
_KEY = re.compile(r"^[A-Za-z0-9\-]{1,64}\.jpg$")
_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
# Solo se habla con Apple: evita que una respuesta manipulada lleve las descargas a otro host (SSRF)
_ALLOWED_SUFFIXES = (".icloud.com", ".icloud-content.com")
_HEADERS = {"Content-Type": "text/plain", "Origin": "https://www.icloud.com"}
_URL_BATCH = 25


class ICloudError(Exception):
    """Código estable: invalid_icloud_url, icloud_album_not_public, icloud_unreachable."""


def parse_token(url: str) -> str:
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ("www.icloud.com", "icloud.com") \
            or not parts.path.startswith("/sharedalbum"):
        raise ICloudError("invalid_icloud_url")
    m = _TOKEN.search(url)
    if not m:
        raise ICloudError("invalid_icloud_url")
    return m.group(1)


def _base62(value: str) -> int:
    n = 0
    for ch in value:
        n = n * 62 + _BASE62.index(ch)
    return n


def base_url(token: str, host: str = None) -> str:
    if not host:
        partition = _base62(token[1]) if token[0] == "A" else _base62(token[1:3])
        host = f"p{partition:02d}-sharedstreams.icloud.com"
    return f"https://{host}/{token}/sharedstreams/"


def _check_host(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not host.endswith(_ALLOWED_SUFFIXES):
        raise ICloudError("icloud_unreachable")
    return url


def _post(client: httpx.Client, url: str, body: dict) -> httpx.Response:
    try:
        return client.post(_check_host(url), content=json.dumps(body), headers=_HEADERS)
    except httpx.HTTPError as exc:
        logger.warning("iCloud %s: %s", url, exc)
        raise ICloudError("icloud_unreachable") from None


def fetch_stream(client: httpx.Client, token: str) -> tuple:
    """(base, nombre del álbum, fotos) siguiendo como máximo una redirección 330."""
    base = base_url(token)
    for _ in range(2):
        resp = _post(client, base + "webstream", {"streamCtag": None})
        if resp.status_code == 330:
            host = (resp.json() or {}).get("X-Apple-MMe-Host")
            if not host:
                raise ICloudError("icloud_unreachable")
            base = base_url(token, host)
            continue
        if resp.status_code in (401, 403, 404):
            raise ICloudError("icloud_album_not_public")
        if resp.status_code != 200:
            raise ICloudError("icloud_unreachable")
        data = resp.json()
        return base, data.get("streamName") or "", data.get("photos") or []
    raise ICloudError("icloud_unreachable")


def best_derivative(photo: dict):
    if photo.get("mediaAssetType") == "video":
        return None
    derivatives = [d for d in (photo.get("derivatives") or {}).values() if d.get("checksum")]
    if not derivatives:
        return None
    return max(derivatives, key=lambda d: int(d.get("width") or 0) * int(d.get("height") or 0))


def fetch_urls(client: httpx.Client, base: str, guids: list) -> dict:
    """checksum -> URL de descarga."""
    urls = {}
    for i in range(0, len(guids), _URL_BATCH):
        resp = _post(client, base + "webasseturls", {"photoGuids": guids[i:i + _URL_BATCH]})
        if resp.status_code != 200:
            raise ICloudError("icloud_unreachable")
        for checksum, item in (resp.json().get("items") or {}).items():
            if item.get("url_location") and item.get("url_path"):
                urls[checksum] = f"https://{item['url_location']}{item['url_path']}"
    return urls


def cache_dir(source_id: int) -> Path:
    return Path(settings["data_dir"]) / "cache" / "icloud" / str(source_id)


def file_path(source_id: int, key: str) -> Path:
    if not _KEY.match(key):
        raise ValueError("invalid_path")
    path = cache_dir(source_id) / key
    if not path.is_file():
        raise ValueError("invalid_path")
    return path


def remove_cache(source_id: int) -> None:
    shutil.rmtree(cache_dir(source_id), ignore_errors=True)


def _download(client: httpx.Client, url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".part")
    try:
        with client.stream("GET", _check_host(url)) as resp:
            if resp.status_code != 200:
                raise ICloudError("icloud_unreachable")
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(65536):
                    f.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        logger.warning("Descarga iCloud fallida: %s", exc)
        raise ICloudError("icloud_unreachable") from None
    tmp.replace(dest)


def refresh(source_id: int, url: str, client: httpx.Client = None) -> tuple:
    """Descarga las fotos nuevas, borra las que ya no están y devuelve (nombre, [(clave, tamaño, mtime)])."""
    token = parse_token(url)
    limit = int(settings.get("icloud", {}).get("max_photos", 300))
    own_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    try:
        base, name, photos = fetch_stream(client, token)
        wanted = {}
        for photo in photos:
            guid, deriv = photo.get("photoGuid"), best_derivative(photo)
            if guid and deriv and re.match(r"^[A-Za-z0-9\-]{1,60}$", guid):
                wanted[f"{guid}.jpg"] = (guid, deriv["checksum"])
            if len(wanted) >= limit:
                break

        folder = cache_dir(source_id)
        folder.mkdir(parents=True, exist_ok=True)
        for existing in folder.iterdir():
            if existing.name not in wanted:
                existing.unlink(missing_ok=True)

        missing = {key: v for key, v in wanted.items() if not (folder / key).exists()}
        if missing:
            urls = fetch_urls(client, base, [guid for guid, _ in missing.values()])
            for key, (_, checksum) in missing.items():
                if checksum in urls:
                    _download(client, urls[checksum], folder / key)
    finally:
        if own_client:
            client.close()

    found = []
    for key in sorted(wanted):
        path = folder / key
        if path.exists():
            st = path.stat()
            found.append((key, st.st_size, st.st_mtime))
    return name, found
