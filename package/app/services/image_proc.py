"""Preparación de imágenes con Pillow. Se procesa una imagen a la vez: el NAS tiene 1 GB de RAM."""
import io
import threading
from pathlib import Path

from PIL import Image, ImageOps

FRAME_SIZE = (3840, 2160)
THUMB_WIDTH = 400
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Limita la decodificación simultánea (miniaturas pedidas en paralelo por el navegador)
_decode_lock = threading.BoundedSemaphore(2)


def _open(source, target_size):
    img = Image.open(source)
    # draft() decodifica el JPEG directamente a una escala reducida: 48 MP pasan de ~200 MB a ~50 MB
    img.draft("RGB", target_size)
    return ImageOps.exif_transpose(img).convert("RGB")


def prepare_for_frame(path: Path) -> bytes:
    """JPEG 3840x2160 recortado al centro."""
    with _decode_lock:
        img = _open(path, FRAME_SIZE)
        img = ImageOps.fit(img, FRAME_SIZE, Image.LANCZOS, centering=(0.5, 0.5))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90, optimize=True)
        return buf.getvalue()


def make_thumbnail(source, dest: Path) -> None:
    """Miniatura 16:9 de THUMB_WIDTH px; source puede ser una ruta o bytes."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    size = (THUMB_WIDTH, THUMB_WIDTH * 9 // 16)
    with _decode_lock:
        img = _open(source, size)
        img = ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.5))
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        img.save(tmp, "JPEG", quality=80)
        tmp.replace(dest)
