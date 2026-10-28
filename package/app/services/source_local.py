"""NAS folders as an image source, limited to the configured roots."""
import os
from pathlib import Path

from app.core.config import settings
from app.services.image_proc import IMAGE_EXTENSIONS

# ADM internal folders (thumbnails, recycle bin) and hidden ones
_SKIP_PREFIXES = (".", "@", "#")


def roots() -> list:
    return [os.path.realpath(r) for r in settings.get("media", {}).get("roots", [])]


def _within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def resolve(path: str) -> str:
    """Real path inside one of the roots, or ValueError; realpath resolves '..' and symlinks."""
    if not path or "\x00" in path:
        raise ValueError("invalid_path")
    real = os.path.realpath(path)
    if not any(_within(real, root) for root in roots()):
        raise ValueError("path_not_allowed")
    if not os.path.isdir(real):
        raise ValueError("invalid_path")
    return real


def _visible(name: str) -> bool:
    return not name.startswith(_SKIP_PREFIXES)


def _is_image(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def browse(path: str = "") -> dict:
    if not path:
        return {"path": "", "parent": None,
                "dirs": [{"name": r, "path": r} for r in roots() if os.path.isdir(r)], "images": 0}
    real = resolve(path)
    dirs, images = [], 0
    with os.scandir(real) as it:
        for entry in it:
            if not _visible(entry.name):
                continue
            if entry.is_dir():
                dirs.append({"name": entry.name, "path": os.path.join(real, entry.name)})
            elif entry.is_file() and _is_image(entry.name):
                images += 1
    dirs.sort(key=lambda d: d["name"].lower())
    parent = os.path.dirname(real)
    if not any(_within(parent, root) for root in roots()):
        parent = ""
    return {"path": real, "parent": parent, "dirs": dirs, "images": images}


def scan(path: str, recursive: bool) -> list:
    """[(relative key, size, mtime)] of the images in the folder."""
    base = resolve(path)
    found = []
    for current, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if _visible(d)) if recursive else []
        for name in filenames:
            if _visible(name) and _is_image(name):
                full = os.path.join(current, name)
                st = os.stat(full)
                found.append((os.path.relpath(full, base).replace(os.sep, "/"), st.st_size, st.st_mtime))
    found.sort()
    return found


def file_path(source_path: str, key: str) -> Path:
    base = resolve(source_path)
    full = os.path.realpath(os.path.join(base, key))
    if not _within(full, base) or not os.path.isfile(full):
        raise ValueError("invalid_path")
    return Path(full)
