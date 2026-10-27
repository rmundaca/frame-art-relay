"""Preparación de imágenes con Pillow. Se procesa una imagen a la vez: el NAS tiene 1 GB de RAM."""
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
# Límites comprobados antes de decodificar un original (una foto de 48 MP ocupa 48 M píxeles)
MAX_SOURCE_PIXELS = 100_000_000
MAX_SOURCE_BYTES = 80 * 1024 * 1024
_EXIF_ORIENTATION = 274
_EXIF_IFD = 0x8769
# DateTimeOriginal y DateTimeDigitized (IFD Exif), y DateTime (IFD principal) como último recurso
_EXIF_DATES = (36867, 36868)
_EXIF_DATETIME = 306

# Marca de fecha: Inter Medium (OFL) reducida a dígitos y guion. Medidas en píxeles del lienzo 3840x2160
DATE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "date-digits.ttf"
DATE_FONT_SIZE = 40  # unos 29 px de alto de dígito
DATE_MARGIN = 32  # distancia del texto al borde inferior y derecho de la foto
DATE_COLOR = (255, 255, 255, 190)
DATE_SHADOW = (0, 0, 0, 120)  # sombra difusa para que se lea también sobre fondos claros

# Limita la decodificación simultánea (miniaturas pedidas en paralelo por el navegador)
_decode_lock = threading.BoundedSemaphore(2)


@contextmanager
def heavy():
    """Reserva una de las dos plazas de decodificación (miniaturas, subidas y composiciones)."""
    with _decode_lock:
        yield


def _taken_at(exif) -> str:
    """Fecha de la toma como "YYYY-MM-DDTHH:MM:SS" (hora local de la cámara), o "" si no hay una válida."""
    try:
        sub = exif.get_ifd(_EXIF_IFD)
    except Exception:  # noqa: BLE001 - EXIF dañado
        sub = {}
    for value in [sub.get(tag) for tag in _EXIF_DATES] + [exif.get(_EXIF_DATETIME)]:
        if isinstance(value, bytes):
            value = value.decode("ascii", "ignore")
        if not isinstance(value, str):
            continue
        try:
            # Algunas cámaras añaden fracciones de segundo: "2019:01:26 18:33:25.002"
            taken = datetime.strptime(value.strip().rstrip("\x00")[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
        if taken.year >= 1900:
            return taken.strftime("%Y-%m-%dT%H:%M:%S")
    return ""


def image_meta(path: Path) -> tuple:
    """(ancho, alto, fecha de la toma) tras aplicar la orientación EXIF, leyendo solo la cabecera.

    ValueError si excede los límites."""
    if Path(path).stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("image_too_large")
    with Image.open(path) as img:
        width, height = img.size
        try:
            exif = img.getexif()
            orientation = exif.get(_EXIF_ORIENTATION, 1)
            taken = _taken_at(exif)
        except Exception:  # noqa: BLE001 - EXIF dañado: se usa la orientación de la cabecera
            orientation, taken = 1, ""
    if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
        raise ValueError("image_too_large")
    # 5 a 8: la foto está girada 90 grados
    if orientation in (5, 6, 7, 8):
        width, height = height, width
    return width, height, taken


def oriented_size(path: Path) -> tuple:
    """(ancho, alto) tras aplicar la orientación EXIF, leyendo solo la cabecera. ValueError si excede los límites."""
    return image_meta(path)[:2]


@lru_cache(maxsize=1)
def _date_font():
    return ImageFont.truetype(str(DATE_FONT), DATE_FONT_SIZE)


def draw_date(canvas, box: tuple, text: str) -> None:
    """Dibuja text abajo a la derecha del rectángulo box (x, y, ancho, alto) de un lienzo RGB.

    Solo se compone la zona del texto, no el lienzo entero. Si la foto es demasiado pequeña, no se dibuja."""
    font = _date_font()
    left, top, right, bottom = font.getbbox(text)
    ink_w, ink_h = right - left, bottom - top
    x, y, w, h = box
    if ink_w + 2 * DATE_MARGIN > w or ink_h + 2 * DATE_MARGIN > h:
        return
    pad = 8  # espacio para el desenfoque de la sombra
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
    """Imagen RGB orientada, decodificada a la escala más pequeña que cubra target_size."""
    img = Image.open(source)
    # draft() decodifica el JPEG directamente a una escala reducida: 48 MP pasan de ~200 MB a ~50 MB
    img.draft("RGB", target_size)
    return ImageOps.exif_transpose(img).convert("RGB")


def prepare_for_frame(path: Path, date: str = "", centering: tuple = (0.5, 0.5)) -> bytes:
    """JPEG 3840x2160 recortado (al centro o donde indique centering), con la fecha abajo a la derecha."""
    with _decode_lock:
        img = open_reduced(path, FRAME_SIZE)
        img = ImageOps.fit(img, FRAME_SIZE, Image.LANCZOS, centering=centering)
        if date:
            draw_date(img, (0, 0, *FRAME_SIZE), date)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90, optimize=True)
        return buf.getvalue()


def make_thumbnail(source, dest: Path) -> None:
    """Miniatura 16:9 de THUMB_WIDTH px; source puede ser una ruta o bytes."""
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
