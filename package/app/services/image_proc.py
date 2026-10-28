"""Image preparation with Pillow. One image is processed at a time: the NAS has 1 GB of RAM."""
import io
import threading
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FRAME_SIZE = (3840, 2160)
THUMB_WIDTH = 400
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
# Limits checked before decoding an original (a 48 MP photo has 48 M pixels)
MAX_SOURCE_PIXELS = 100_000_000
MAX_SOURCE_BYTES = 80 * 1024 * 1024
_EXIF_ORIENTATION = 274
_EXIF_IFD = 0x8769
# DateTimeOriginal and DateTimeDigitized (Exif IFD), and DateTime (main IFD) as a last resort
_EXIF_DATES = (36867, 36868)
_EXIF_DATETIME = 306

# Date stamp: Inter Medium (OFL) subset to digits and hyphen. Sizes in pixels of the 3840x2160 canvas
DATE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "date-digits.ttf"
DATE_FONT_SIZE = 40  # about 29 px digit height
DATE_MARGIN = 32  # distance from the text to the bottom and right edges of the photo
DATE_COLOR = (255, 255, 255, 190)
DATE_SHADOW = (0, 0, 0, 120)  # soft shadow so it stays readable on light backgrounds

# Limits concurrent decoding (thumbnails requested in parallel by the browser)
_decode_lock = threading.BoundedSemaphore(2)


@contextmanager
def heavy():
    """Take one of the two decoding slots (thumbnails, uploads and layouts)."""
    with _decode_lock:
        yield


def _taken_at(exif) -> str:
    """Date taken as "YYYY-MM-DDTHH:MM:SS" (camera local time), or "" if there is no valid one."""
    try:
        sub = exif.get_ifd(_EXIF_IFD)
    except Exception:  # noqa: BLE001 - corrupt EXIF
        sub = {}
    for value in [sub.get(tag) for tag in _EXIF_DATES] + [exif.get(_EXIF_DATETIME)]:
        if isinstance(value, bytes):
            value = value.decode("ascii", "ignore")
        if not isinstance(value, str):
            continue
        try:
            # Some cameras add fractional seconds: "2019:01:26 18:33:25.002"
            taken = datetime.strptime(value.strip().rstrip("\x00")[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
        if taken.year >= 1900:
            return taken.strftime("%Y-%m-%dT%H:%M:%S")
    return ""


def image_meta(path: Path) -> tuple:
    """(width, height, date taken) after applying EXIF orientation, reading only the header.

    ValueError if it exceeds the limits."""
    if Path(path).stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("image_too_large")
    with Image.open(path) as img:
        width, height = img.size
        try:
            exif = img.getexif()
            orientation = exif.get(_EXIF_ORIENTATION, 1)
            taken = _taken_at(exif)
        except Exception:  # noqa: BLE001 - corrupt EXIF: use the header orientation
            orientation, taken = 1, ""
    if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
        raise ValueError("image_too_large")
    # 5 to 8: the photo is rotated 90 degrees
    if orientation in (5, 6, 7, 8):
        width, height = height, width
    return width, height, taken


def oriented_size(path: Path) -> tuple:
    """(width, height) after applying EXIF orientation, reading only the header. ValueError if it exceeds the limits."""
    return image_meta(path)[:2]


@lru_cache(maxsize=1)
def _date_font():
    return ImageFont.truetype(str(DATE_FONT), DATE_FONT_SIZE)


def draw_date(canvas, box: tuple, text: str) -> None:
    """Draw text at the bottom right of rectangle box (x, y, width, height) on an RGB canvas.

    Only the text area is composited, not the whole canvas. If the photo is too small, nothing is drawn."""
    font = _date_font()
    left, top, right, bottom = font.getbbox(text)
    ink_w, ink_h = right - left, bottom - top
    x, y, w, h = box
    if ink_w + 2 * DATE_MARGIN > w or ink_h + 2 * DATE_MARGIN > h:
        return
    pad = 8  # room for the shadow blur
    size = (ink_w + 2 * pad, ink_h + 2 * pad)
    origin = (x + w - DATE_MARGIN - ink_w - pad, y + h - DATE_MARGIN - ink_h - pad)
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((pad - left + 1, pad - top + 2), text, font=font, fill=DATE_SHADOW)
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    ImageDraw.Draw(shadow).text((pad - left, pad - top), text, font=font, fill=DATE_COLOR)
    region = canvas.crop((*origin, origin[0] + size[0], origin[1] + size[1])).convert("RGBA")
    region.alpha_composite(shadow)
    canvas.paste(region.convert("RGB"), origin)


def open_reduced(source, target_size):
    """Oriented RGB image, decoded at the smallest scale that covers target_size."""
    img = Image.open(source)
    # draft() decodes the JPEG straight to a reduced scale: 48 MP goes from ~200 MB to ~50 MB
    img.draft("RGB", target_size)
    return ImageOps.exif_transpose(img).convert("RGB")


def prepare_for_frame(path: Path, date: str = "", centering: tuple = (0.5, 0.5)) -> bytes:
    """3840x2160 JPEG cropped (centred or where centering says), with the date at the bottom right."""
    with _decode_lock:
        img = open_reduced(path, FRAME_SIZE)
        img = ImageOps.fit(img, FRAME_SIZE, Image.LANCZOS, centering=centering)
        if date:
            draw_date(img, (0, 0, *FRAME_SIZE), date)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90, optimize=True)
        return buf.getvalue()


def make_thumbnail(source, dest: Path) -> None:
    """16:9 thumbnail THUMB_WIDTH px wide; source can be a path or bytes."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    size = (THUMB_WIDTH, THUMB_WIDTH * 9 // 16)
    with _decode_lock:
        img = open_reduced(source, size)
        img = ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.5))
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        img.save(tmp, "JPEG", quality=80)
        tmp.replace(dest)
