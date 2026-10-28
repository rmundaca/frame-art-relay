"""Public iCloud albums: read without credentials via Shared Streams or CloudKit.

Flow: POST <base>/webstream (photo list and derivatives) -> POST <base>/webasseturls (download URLs).
If the album lives on another partition, Apple answers 330 with the right host in "X-Apple-MMe-Host".
"""
import hashlib
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
# Only talk to Apple: stops a tampered response from pointing downloads at another host (SSRF)
_ALLOWED_SUFFIXES = (".icloud.com", ".icloud-content.com")
_HEADERS = {"Content-Type": "text/plain", "Origin": "https://www.icloud.com"}
_URL_BATCH = 25
_CLOUD_PATH = "/database/1/com.apple.photos.cloud/production/"
_CLOUD_ALBUM = re.compile(r"/shared/album/([A-Za-z0-9_-]{10,64})/?")
_CLOUD_PRIVATE_ERRORS = ("NOT_FOUND", "ACCESS_DENIED", "AUTHENTICATION_REQUIRED", "PERMISSION_DENIED")


class ICloudError(Exception):
    """Stable code: invalid_icloud_url, icloud_album_not_public, icloud_unreachable."""


def parse_token(url: str) -> str:
    url = (url or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        raise ICloudError("invalid_icloud_url") from None
    if parts.scheme == "https" and parts.hostname == "photos.icloud.com":
        match = _CLOUD_ALBUM.fullmatch(parts.path)
        if match:
            return match.group(1)
        raise ICloudError("invalid_icloud_url")
    if parts.scheme != "https" or parts.hostname not in ("www.icloud.com", "icloud.com") \
            or not parts.path.startswith("/sharedalbum"):
        raise ICloudError("invalid_icloud_url")
    m = _TOKEN.search(url)
    if not m:
        raise ICloudError("invalid_icloud_url")
    return m.group(1)


def canonical_url(url: str) -> str:
    token = parse_token(url)
    if urlsplit(url.strip()).hostname == "photos.icloud.com":
        return f"https://photos.icloud.com/shared/album/{token}"
    return f"https://www.icloud.com/sharedalbum/#{token}"


def _cloud_post(client: httpx.Client, url: str, body: dict, params: dict) -> dict:
    try:
        resp = client.post(_check_host(url), json=body, params=params)
    except httpx.HTTPError as exc:
        logger.warning("iCloud CloudKit: %s", type(exc).__name__)
        raise ICloudError("icloud_unreachable") from None
    if resp.status_code in (401, 403, 404):
        raise ICloudError("icloud_album_not_public")
    if resp.status_code != 200:
        raise ICloudError("icloud_unreachable")
    try:
        data = resp.json()
    except ValueError:
        logger.warning("Invalid CloudKit JSON response")
        raise ICloudError("icloud_unreachable") from None
    if isinstance(data, dict) and data.get("serverErrorCode") in _CLOUD_PRIVATE_ERRORS:
        raise ICloudError("icloud_album_not_public")
    if not isinstance(data, dict) or data.get("serverErrorCode"):
        logger.warning("Invalid CloudKit response")
        raise ICloudError("icloud_unreachable")
    return data


def _resolve_cloud(client: httpx.Client, token: str) -> tuple:
    data = _cloud_post(client, "https://ckdatabasews.icloud.com" + _CLOUD_PATH + "public/records/resolve",
                       {"shortGUIDs": [{"value": token}]}, {"sharing_url_key": token})
    try:
        result = data["results"][0]
        access = result.get("anonymousPublicAccess")
        if result.get("serverErrorCode") in _CLOUD_PRIVATE_ERRORS:
            raise ICloudError("icloud_album_not_public")
        if result.get("serverErrorCode"):
            raise ICloudError("icloud_unreachable")
        if result.get("requireAppleLogin") or not access:
            raise ICloudError("icloud_album_not_public")
        partition = access["databasePartition"]
        parts = urlsplit(partition)
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError("invalid_partition")
        base = _check_host(partition.rstrip("/")) + _CLOUD_PATH + "shared/records/query"
        params = {"sharing_url_key": token, "publicAccessAuthToken": access["token"],
                  "remapEnums": "true", "getCurrentSyncToken": "true"}
        zone = result["zoneID"]
        name = result["share"]["fields"].get("cloudkit.title", {}).get("value") or ""
        return name, base, params, zone
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        logger.warning("Invalid CloudKit album metadata")
        raise ICloudError("icloud_unreachable") from None


def album_name(client: httpx.Client, url: str) -> str:
    url = canonical_url(url)
    token = parse_token(url)
    if urlsplit(url).hostname == "photos.icloud.com":
        return _resolve_cloud(client, token)[0]
    return fetch_stream(client, token)[1]


def _cloud_photos(client: httpx.Client, token: str, limit: int) -> tuple:
    name, base, params, zone = _resolve_cloud(client, token)
    data = _cloud_post(client, base, {
        "query": {"recordType": "HyperionIndexCountLookup", "filterBy": [
            {"fieldName": "indexCountID", "comparator": "IN",
             "fieldValue": {"value": ["CPLAssetByAddedDate"], "type": "STRING_LIST"}}]},
        "zoneID": zone,
    }, params)
    try:
        total = int(data["records"][0]["fields"]["itemCount"]["value"])
        if total < 0:
            raise ValueError("invalid_count")
        wanted = {}
        rank = 0
        while rank < total and len(wanted) < limit:
            data = _cloud_post(client, base, {
                "query": {"recordType": "CPLAssetAndMasterByAddedDate", "filterBy": [
                    {"fieldName": "direction", "comparator": "EQUALS",
                     "fieldValue": {"value": "ASCENDING", "type": "STRING"}},
                    {"fieldName": "startRank", "comparator": "EQUALS",
                     "fieldValue": {"value": rank, "type": "INT64"}}]},
                "zoneID": zone, "resultsLimit": min(100, 2 * (limit - len(wanted))),
            }, params)
            records = data["records"]
            masters = {r["recordName"]: r for r in records if r["recordType"] == "CPLMaster"}
            assets = [r for r in records if r["recordType"] == "CPLAsset"]
            if not assets:
                raise ValueError("incomplete_page")
            rank += len(assets)
            for asset in assets:
                fields = asset["fields"]
                if fields.get("isHidden", {}).get("value") or fields.get("trashReason", {}).get("value"):
                    continue
                master = masters[fields["masterRef"]["value"]["recordName"]]
                if master["fields"].get("dataClassType", {}).get("value") != 1:
                    continue
                candidates = []
                for source in (master["fields"], fields):
                    for field, value in source.items():
                        if not field.startswith("res") or not field.endswith("Res"):
                            continue
                        prefix = field[:-3]
                        if source.get(prefix + "FileType", {}).get("value") != "public.jpeg":
                            continue
                        resource = value["value"]
                        if resource.get("downloadURL"):
                            area = int(source.get(prefix + "Width", {}).get("value") or 0) * \
                                int(source.get(prefix + "Height", {}).get("value") or 0)
                            candidates.append((area, _check_host(resource["downloadURL"])))
                if not candidates:
                    raise ValueError("missing_jpeg")
                key = hashlib.sha256(asset["recordName"].encode("utf-8")).hexdigest()[:60] + ".jpg"
                wanted[key] = max(candidates)[1]
                if len(wanted) >= limit:
                    break
        return name, wanted
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        logger.warning("Invalid CloudKit photo list")
        raise ICloudError("icloud_unreachable") from None


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
    """(base, album name, photos) following at most one 330 redirect."""
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
    """checksum -> download URL."""
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
    """Download new photos, delete the ones that are gone and return (name, [(key, size, mtime)])."""
    url = canonical_url(url)
    token = parse_token(url)
    cloud = urlsplit(url).hostname == "photos.icloud.com"
    limit = int(settings.get("icloud", {}).get("max_photos", 300))
    own_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    try:
        if cloud:
            name, direct_urls = _cloud_photos(client, token, limit)
            wanted = {key: (key, key) for key in direct_urls}
        else:
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
            urls = direct_urls if cloud else fetch_urls(client, base, [guid for guid, _ in missing.values()])
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
