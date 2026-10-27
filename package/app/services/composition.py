"""Composiciones automáticas: agrupa varias fotos de un álbum en una página 3840x2160, como una hoja de álbum.

- La agrupación es determinista y estable: las páginas válidas se conservan entre reescaneos y las fotos
  nuevas aprovechan páginas incompletas o forman páginas nuevas.
- Cada foto se recorta como mucho MAX_CROP por eje para que el grupo llene el lienzo; nunca se deforma. El
  espacio que sobra queda como fondo (papel o las propias fotos desenfocadas) alrededor del grupo.
- Las fotos que van solas pueden mostrarse completas sobre ese mismo fondo (Album.single_fit = "fit").
- Se renderiza fuera de las peticiones HTTP, una página y una foto por vez, bajo el candado global de
  decodificación de image_proc.
"""
import hashlib
import io
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from functools import lru_cache

from PIL import Image as PILImage
from PIL import ImageEnhance, ImageFilter, ImageOps
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.schemas import Album, CompositionMember, CompositionPage, Image, TvContent
from app.services import subject_ai
from app.services.albums import album_images, date_label, ensure_meta, fill_meta, image_file, wants_date
from app.services.image_proc import (FRAME_SIZE, THUMB_WIDTH, draw_date, heavy, open_reduced, oriented_size,
                                     prepare_for_frame)

logger = logging.getLogger("composition")

MODES = ("off", "auto")
BACKGROUNDS = ("paper", "blur")
SINGLE_FITS = ("crop", "fit")
RENDERER_VERSION = 2  # 2: recorte limitado de las celdas y fondo desenfocado

# Diseño fijo de la página, en píxeles del lienzo de 3840x2160
MARGIN = 96  # borde mínimo alrededor del grupo de fotos
GAP = 48  # separación entre fotos
BACKGROUND = (236, 234, 230)  # gris cálido neutro, como el papel de un álbum
JPEG_QUALITY = 90
# Recorte máximo de cada foto por eje (0,15 = hasta un 15 % del ancho o del alto) para que el grupo llene el
# lienzo. Con fotos 3:4 y 4:3, trio_v2h pasa de 518 a unos 276 px de fondo por lado
MAX_CROP = 0.15
# Una foto sola que pierde como mucho esta fracción de superficie al recortarse a 16:9 llena la pantalla
# (4:3, 3:2, 16:9); con más pérdida (verticales, panorámicas) se agrupa o, con "fit", se muestra completa
SINGLE_MAX_CROP = 0.25
SCREEN_RATIO = FRAME_SIZE[0] / FRAME_SIZE[1]
# Fondo desenfocado: las fotos se reducen a este lienzo, se desenfocan, se oscurecen y se amplían
BLUR_SIZE = (240, 135)
BLUR_RADIUS = 8
BLUR_BRIGHTNESS = 0.75
# Una plantilla solo se acepta si las fotos cubren al menos MIN_FILL del lienzo y ninguna queda con el
# lado corto por debajo de MIN_SIDE. Así dos horizontales 3:2 apiladas (36 %) siguen como individuales,
# que en 16:9 apenas pierden imagen, y las verticales, que sí perderían mucho al recortarse, se agrupan.
MIN_FILL = 0.40
MIN_SIDE = 640
# Hasta esta proporción (ancho / alto) la foto ocupa una celda vertical: incluye las cuadradas
VERTICAL_MAX_RATIO = 1.1
# Compañeros que se prueban para cada foto, los más cercanos en el orden del álbum
LOOKAHEAD = 8

# Árbol de cada plantilla: ("row" | "col", hijos); las hojas son la posición de la foto en la página
TEMPLATES = {
    "pair_v": ("row", [0, 1]),  # dos verticales lado a lado
    "pair_h": ("col", [0, 1]),  # dos horizontales apiladas
    "trio_v2h": ("row", [0, ("col", [1, 2])]),  # una vertical junto a dos horizontales apiladas
    "duo_vh": ("row", [0, 1]),  # una vertical y una horizontal, asimétricas
    "trio_v": ("row", [0, 1, 2]),  # tres verticales en fila: recoge la vertical sobrante de un número impar
    "single": ("row", [0]),  # una foto sola mostrada completa (single_fit = "fit"); no se usa al agrupar
}
# Orientación que exige cada posición: v vertical o cuadrada, h horizontal o panorámica
SLOTS = {"pair_v": "vv", "pair_h": "hh", "trio_v2h": "vhh", "duo_vh": "vh", "trio_v": "vvv"}

# Serializa planificación, renderizado y limpieza de todos los álbumes: solo un lienzo 4K a la vez
_job_lock = threading.Lock()


class CompositionError(Exception):
    """Código estable: composition_source_unavailable, composition_render_failed."""


# ------------------------------------------------------------------ maquetación

def _orientation(ratio: float) -> str:
    return "v" if ratio <= VERTICAL_MAX_RATIO else "h"


def _linear(node, ratios) -> tuple:
    """(a, b) tales que el ancho del nodo es a * alto + b."""
    if isinstance(node, int):
        return ratios[node], 0.0
    kind, children = node
    parts = [_linear(c, ratios) for c in children]
    gaps = GAP * (len(children) - 1)
    if kind == "row":
        return sum(a for a, _ in parts), sum(b for _, b in parts) + gaps
    # Columna de ancho común w: alto = w * sum(1/a) - sum(b/a) + huecos; se despeja w
    inv = sum(1 / a for a, _ in parts)
    off = sum(b / a for a, b in parts)
    return 1 / inv, (off - gaps) / inv


def _place(node, ratios, x, y, w, h, out) -> None:
    if isinstance(node, int):
        out[node] = (x, y, w, h)
        return
    kind, children = node
    for child in children:
        a, b = _linear(child, ratios)
        if kind == "row":
            cw = a * h + b
            _place(child, ratios, x, y, cw, h, out)
            x += cw + GAP
        else:
            ch = (w - b) / a
            _place(child, ratios, x, y, w, ch, out)
            y += ch + GAP


def single_loss(ratio: float) -> float:
    """Fracción de la foto que se pierde al recortarla a la proporción de la pantalla."""
    return 1 - min(ratio / SCREEN_RATIO, SCREEN_RATIO / ratio)


def crop_factor(template: str, ratios) -> float:
    """Factor común de las proporciones de las celdas (proporción de la foto * f) que ajusta el grupo al
    recuadro útil del lienzo, limitado a MAX_CROP por eje: f < 1 recorta los lados y f > 1 arriba y abajo."""
    box_w, box_h = FRAME_SIZE[0] - 2 * MARGIN, FRAME_SIZE[1] - 2 * MARGIN
    lo, hi = 1 - MAX_CROP, 1 / (1 - MAX_CROP)

    def too_wide(f):
        a, b = _linear(TEMPLATES[template], [r * f for r in ratios])
        return a * box_h + b > box_w

    # Ensanchar las celdas siempre ensancha el grupo: se busca el punto en que llena ancho y alto a la vez
    if too_wide(lo):
        return lo
    if not too_wide(hi):
        return hi
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if too_wide(mid) else (mid, hi)
    return lo


def layout(template: str, ratios: list) -> list:
    """Rectángulos (x, y, ancho, alto) de cada posición, centrados en el lienzo, con el recorte de crop_factor."""
    return list(_layout(template, tuple(round(r, 6) for r in ratios)))


@lru_cache(maxsize=4096)
def _layout(template: str, ratios: tuple) -> tuple:
    width, height = FRAME_SIZE
    f = crop_factor(template, ratios)
    ratios = [r * f for r in ratios]
    a, b = _linear(TEMPLATES[template], ratios)
    box_w, box_h = width - 2 * MARGIN, height - 2 * MARGIN
    h = box_h
    w = a * h + b
    if w > box_w:
        w = box_w
        h = (box_w - b) / a
    out = {}
    _place(TEMPLATES[template], ratios, (width - w) / 2, (height - h) / 2, w, h, out)
    boxes = []
    for i in range(len(ratios)):
        x, y, cw, ch = out[i]
        left, top = round(x), round(y)
        boxes.append((left, top, round(x + cw) - left, round(y + ch) - top))
    return tuple(boxes)


def fill_score(template: str, ratios: list) -> Optional[float]:
    """Fracción del lienzo cubierta por las fotos, o None si la plantilla no es adecuada."""
    slots = SLOTS[template]
    if len(ratios) != len(slots) or any(_orientation(r) != s for r, s in zip(ratios, slots)):
        return None
    # Dos horizontales que ya llenan la pantalla solas (4:3, 3:2, 16:9) no se apilan: se verían más pequeñas
    if template == "pair_h" and any(single_loss(r) <= SINGLE_MAX_CROP for r in ratios):
        return None
    boxes = layout(template, ratios)
    if min(min(w, h) for _, _, w, h in boxes) < MIN_SIDE:
        return None
    fill = sum(w * h for _, _, w, h in boxes) / (FRAME_SIZE[0] * FRAME_SIZE[1])
    return fill if fill >= MIN_FILL else None


# -------------------------------------------------------------------- agrupación

def _ordered(template: str, ids: list, ratio: dict, pos: dict) -> list:
    """Integrantes en el orden de las posiciones de la plantilla; a igual orientación, el del álbum."""
    return sorted(ids, key=lambda i: (SLOTS[template].index(_orientation(ratio[i])), pos[i]))


def group(candidates: list, existing: dict = None) -> tuple:
    """Agrupa fotos en páginas.

    candidates: [(image_id, proporción o None)] en el orden del álbum; None significa que no se pudo medir.
    existing: {page_id: (plantilla, [image_id])} de la agrupación anterior.
    Devuelve (keep, new): keep = {page_id: (plantilla, [image_id])} para las páginas que siguen (quizá
    ampliadas), new = [(plantilla, [image_id])]. Las demás fotos quedan individuales.
    """
    ratio = {i: r for i, r in candidates if r}
    pos = {i: n for n, (i, _) in enumerate(candidates)}
    used, keep = set(), {}

    for page_id in sorted(existing or {}):
        template, ids = existing[page_id]
        if template not in TEMPLATES or any(i not in ratio or i in used for i in ids) \
                or len(set(ids)) != len(ids):
            continue
        ids = _ordered(template, ids, ratio, pos)
        if fill_score(template, [ratio[i] for i in ids]) is not None:
            keep[page_id] = (template, ids)
            used.update(ids)

    def free(kind):
        return [i for i, _ in candidates if i in ratio and i not in used and _orientation(ratio[i]) == kind]

    def nearest(anchor, pool):
        return sorted((i for i in pool if i != anchor), key=lambda i: (abs(pos[i] - pos[anchor]), pos[i]))[:LOOKAHEAD]

    def fits(template, ids):
        return fill_score(template, [ratio[i] for i in _ordered(template, ids, ratio, pos)]) is not None

    # Páginas incompletas: una vertical con una horizontal admite una segunda horizontal
    for page_id in sorted(keep):
        template, ids = keep[page_id]
        if template != "duo_vh":
            continue
        for h in nearest(min(ids, key=pos.get), free("h")):
            if fits("trio_v2h", ids + [h]):
                keep[page_id] = ("trio_v2h", _ordered("trio_v2h", ids + [h], ratio, pos))
                used.add(h)
                break

    new = []

    def take(template, ids):
        ids = _ordered(template, ids, ratio, pos)
        new.append((template, ids))
        used.update(ids)

    # Las verticales son las que más pierden al recortarse a 16:9: eligen compañero primero
    for v in free("v"):
        if v in used:
            continue
        mate = next((o for o in nearest(v, free("v")) if fits("pair_v", [v, o])), None)
        if mate is not None:
            take("pair_v", [v, mate])
            continue
        hs = nearest(v, free("h"))
        pairs = sorted(((a, b) for n, a in enumerate(hs) for b in hs[n + 1:]),
                       key=lambda p: (abs(pos[p[0]] - pos[v]) + abs(pos[p[1]] - pos[v]), pos[p[0]], pos[p[1]]))
        trio = next((p for p in pairs if fits("trio_v2h", [v, *p])), None)
        if trio:
            take("trio_v2h", [v, *trio])
            continue
        mate = next((h for h in hs if fits("duo_vh", [v, h])), None)
        if mate is not None:
            take("duo_vh", [v, mate])

    for h in free("h"):
        if h in used:
            continue
        mate = next((o for o in nearest(h, free("h")) if fits("pair_h", [h, o])), None)
        if mate is not None:
            take("pair_h", [h, mate])

    # Una vertical sobrante (número impar) se suma a la pareja de verticales más cercana, nueva o existente
    for v in free("v"):
        pairs = [("new", n, ids) for n, (t, ids) in enumerate(new) if t == "pair_v"]
        pairs += [("keep", pid, ids) for pid, (t, ids) in sorted(keep.items()) if t == "pair_v"]
        pairs.sort(key=lambda p: (min(abs(pos[i] - pos[v]) for i in p[2]), min(pos[i] for i in p[2])))
        for kind, ref, ids in pairs[:LOOKAHEAD]:
            if fits("trio_v", ids + [v]):
                trio = ("trio_v", _ordered("trio_v", ids + [v], ratio, pos))
                if kind == "new":
                    new[ref] = trio
                else:
                    keep[ref] = trio
                used.add(v)
                break

    new.sort(key=lambda g: min(pos[i] for i in g[1]))
    return keep, new


# ------------------------------------------------------------------- persistencia

def _version(img: Image) -> str:
    return f"{img.id}:{img.size}:{img.mtime}"


# --------------------------------------------------------------------- sujeto

# Margen alrededor del sujeto que se intenta conservar, en fracción de la foto
SUBJECT_PAD = 0.025


def subject_box(album: Album, img: Image) -> Optional[list]:
    """Recuadro del sujeto vigente ([x0, y0, x1, y1] en 0-1) si el álbum usa la detección, o None."""
    if not album.subject_detection or not img.subject_box or img.subject_sig != _version(img):
        return None
    try:
        box = json.loads(img.subject_box)
        return [float(v) for v in box] if len(box) == 4 else None
    except (ValueError, TypeError):
        return None


def subjects_pending(album: Album, images: list) -> bool:
    """Hay fotos sin analizar y la detección funciona: la salida espera para no subir dos versiones."""
    return bool(album.subject_detection and not album.subject_error
                and any(img.subject_sig != _version(img) for img in images))


def detect_subjects(db: Session, album: Album, client=None) -> None:
    """Analiza con Gemini las fotos del álbum que van al TV y aún no tienen resultado para su versión.

    Un fallo propio de una foto la deja sin sujeto (recorte al centro); uno general (red, clave, cupo) detiene
    la tanda y queda en album.subject_error: la salida sigue con recortes al centro y se reintenta más tarde."""
    if not album.subject_detection:
        return
    error = None
    for img in album_images(db, album):
        version = _version(img)
        if img.subject_sig == version:
            continue
        try:
            box = subject_ai.detect(image_file(db, img), client)
        except subject_ai.SubjectError as exc:
            if str(exc) != "gemini_response_invalid":
                error = str(exc)
                break
            box = None
        except (ValueError, OSError):
            box = None  # foto ilegible: sin sujeto
        img.subject_box, img.subject_sig = (json.dumps(box) if box else ""), version
        db.commit()
    album.subject_error = error
    db.commit()


def _window(lo: float, hi: float, visible: float, keep_start: bool) -> float:
    """Posición (0-1, como centering de ImageOps.fit) de una ventana de tamaño visible sobre [0, 1] que contiene
    [lo, hi] si cabe; si no cabe, centrada en el sujeto o, con keep_start, pegada a su inicio (las cabezas)."""
    if visible >= 1:
        return 0.5
    lo, hi = max(0.0, lo - SUBJECT_PAD), min(1.0, hi + SUBJECT_PAD)
    if hi - lo <= visible:
        start = min(max((lo + hi - visible) / 2, hi - visible), lo)
    else:
        start = lo if keep_start else (lo + hi - visible) / 2
    start = min(max(start, 0.0), 1 - visible)
    return start / (1 - visible)


def centering(box: Optional[list], photo_ratio: float, cell_ratio: float) -> tuple:
    """centering de ImageOps.fit que conserva el sujeto al recortar la foto a la proporción de la celda."""
    if not box:
        return 0.5, 0.5
    x0, y0, x1, y1 = box
    if cell_ratio < photo_ratio:  # se recortan los lados
        return _window(x0, x1, cell_ratio / photo_ratio, False), 0.5
    return 0.5, _window(y0, y1, photo_ratio / cell_ratio, True)


def page_signature(template: str, images: list, dates: list = (), background: str = "paper",
                   subjects: list = ()) -> str:
    parts = [f"r{RENDERER_VERSION}", template, f"{MARGIN},{GAP},{BACKGROUND},{JPEG_QUALITY},{MAX_CROP}",
             background, *(_version(img) for img in images)]
    if any(dates):
        # Solo si alguna foto lleva fecha: las páginas sin fecha conservan su firma anterior
        parts.append("dates:" + ",".join(dates))
    if any(subjects):
        parts.append("subjects:" + json.dumps(list(subjects)))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def single_sig(date: str, fitted: bool = False, background: str = "paper", subject: Optional[list] = None) -> str:
    """Variante de una imagen individual en el TV (TvContent.render_sig); "" es el recorte a 16:9 sin fecha."""
    parts = [f"fit{RENDERER_VERSION}:{MAX_CROP}:{background}"] if fitted else []
    if date:
        parts.append(f"date={date}")
    if subject:
        parts.append("subj=" + ",".join(f"{v:.3f}" for v in subject))
    return ";".join(parts)


def fits_single(album: Album, img: Image) -> bool:
    """La foto sola se muestra completa sobre el fondo: el álbum lo pide y recortarla a 16:9 perdería mucho."""
    return (album.single_fit == "fit" and bool(img.width and img.height)
            and single_loss(img.width / img.height) > SINGLE_MAX_CROP)


def candidates_signature(images: list) -> str:
    return hashlib.sha1(";".join(_version(img) for img in images).encode()).hexdigest()


def cache_dir(album_id: int) -> Path:
    return Path(settings["data_dir"]) / "cache" / "compositions" / str(album_id)


def page_file(album_id: int, page_id: int, revision: int) -> Path:
    return cache_dir(album_id) / f"{page_id}-{revision}.jpg"


def page_thumb(album_id: int, page_id: int, revision: int) -> Path:
    return cache_dir(album_id) / f"{page_id}-{revision}.thumb.jpg"


def active_pages(db: Session, album_id: int) -> list:
    return (db.query(CompositionPage)
            .filter(CompositionPage.album_id == album_id, CompositionPage.status != "retired")
            .order_by(CompositionPage.id).all())


def _measure(db: Session, img: Image) -> Optional[float]:
    return img.width / img.height if ensure_meta(db, img) else None


def _retire(page: CompositionPage) -> None:
    page.status = "retired"
    page.updated_at = datetime.utcnow()


def plan_album(db: Session, album: Album) -> None:
    """Recalcula la agrupación del álbum conservando las páginas que siguen siendo válidas."""
    pages = active_pages(db, album.id)
    if album.composition_mode != "auto":
        for page in pages:
            _retire(page)
        album.composition_plan = None
        db.commit()
        return
    images = album_images(db, album)
    by_id = {img.id: img for img in images}
    candidates = [(img.id, _measure(db, img)) for img in images]
    existing = {p.id: (p.template, [m.image_id for m in p.members]) for p in pages}
    keep, new = group(candidates, existing)

    for page in pages:
        if page.id not in keep:
            _retire(page)
            continue
        template, ids = keep[page.id]
        if [m.image_id for m in page.members] != ids:
            page.members.clear()
            db.flush()
            page.members.extend(CompositionMember(image_id=i, position=n) for n, i in enumerate(ids))
        page.template = template
        signature = page_signature(template, [by_id[i] for i in ids], [date_label(db, album, by_id[i]) for i in ids],
                                   album.background, [subject_box(album, by_id[i]) for i in ids])
        if signature != page.signature:
            page.signature = signature
            page.revision += 1
            page.status, page.last_error = "pending", None
            page.updated_at = datetime.utcnow()
    for template, ids in new:
        page = CompositionPage(album_id=album.id, template=template, revision=1, status="pending",
                               signature=page_signature(template, [by_id[i] for i in ids],
                                                        [date_label(db, album, by_id[i]) for i in ids],
                                                        album.background,
                                                        [subject_box(album, by_id[i]) for i in ids]))
        page.members = [CompositionMember(image_id=i, position=n) for n, i in enumerate(ids)]
        db.add(page)
    album.composition_plan = candidates_signature(images)
    db.commit()


# -------------------------------------------------------------------- renderizado

def _atomic_save(img, dest: Path, quality: int) -> None:
    tmp = dest.with_name(dest.name + ".tmp")
    img.save(tmp, "JPEG", quality=quality, optimize=True)
    tmp.replace(dest)


def _blurred_background(paths: list, boxes: list):
    """Fondo con las propias fotos: el grupo estirado a todo el lienzo, muy desenfocado y algo oscurecido.

    Se trabaja sobre un lienzo de BLUR_SIZE y cada foto se decodifica a escala mínima (draft)."""
    gx0, gy0 = min(x for x, _, _, _ in boxes), min(y for _, y, _, _ in boxes)
    gx1, gy1 = max(x + w for x, _, w, _ in boxes), max(y + h for _, y, _, h in boxes)
    sx, sy = BLUR_SIZE[0] / (gx1 - gx0), BLUR_SIZE[1] / (gy1 - gy0)
    small = PILImage.new("RGB", BLUR_SIZE, BACKGROUND)
    for path, (x, y, w, h) in zip(paths, boxes):
        left, top = round((x - gx0) * sx), round((y - gy0) * sy)
        size = (max(1, round((x + w - gx0) * sx) - left), max(1, round((y + h - gy0) * sy) - top))
        photo = open_reduced(path, size)
        try:
            tile = ImageOps.fit(photo, size, PILImage.BILINEAR)
        finally:
            photo.close()
        small.paste(tile, (left, top))
    small = ImageEnhance.Brightness(small.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))).enhance(BLUR_BRIGHTNESS)
    return small.resize(FRAME_SIZE, PILImage.BICUBIC)


def _compose(paths: list, boxes: list, dates: list, background: str, subjects: list = None):
    """Lienzo 3840x2160 con cada foto recortada a su celda (al centro o hacia su sujeto) y su fecha; una foto
    decodificada a la vez."""
    canvas = _blurred_background(paths, boxes) if background == "blur" else PILImage.new("RGB", FRAME_SIZE, BACKGROUND)
    try:
        for path, date, subject, (x, y, w, h) in zip(paths, dates, subjects or [None] * len(paths), boxes):
            photo = open_reduced(path, (w, h))
            try:
                where = centering(subject, photo.width / photo.height, w / h)
                cell = ImageOps.fit(photo, (w, h), PILImage.LANCZOS, centering=where)
            finally:
                photo.close()
            canvas.paste(cell, (x, y))
            cell.close()
            if date:
                draw_date(canvas, (x, y, w, h), date)
    except BaseException:
        canvas.close()
        raise
    return canvas


def render_single(path: Path, item) -> bytes:
    """JPEG de una foto individual: recortada a 16:9 o, si item.fitted, completa sobre el fondo del álbum."""
    img = item.image
    if not item.fitted:
        where = centering(item.subject, img.width / img.height, SCREEN_RATIO) if item.subject else (0.5, 0.5)
        return prepare_for_frame(path, item.date, where)
    with heavy():
        canvas = _compose([path], layout("single", [img.width / img.height]), [item.date], item.background,
                          [item.subject])
        try:
            buf = io.BytesIO()
            canvas.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
            return buf.getvalue()
        finally:
            canvas.close()


def render_page(db: Session, page: CompositionPage) -> None:
    """Genera el JPEG y la miniatura de la revisión actual; deja la página en ready o en error."""
    revision = page.revision
    try:
        images = [db.get(Image, m.image_id) for m in page.members]
        album = db.get(Album, page.album_id)
        dates = [date_label(db, album, img) for img in images]
        subjects = [subject_box(album, img) for img in images]
        try:
            paths = [image_file(db, img) for img in images]
        except (ValueError, OSError):
            raise CompositionError("composition_source_unavailable") from None
        try:
            # Cabecera y límites antes de decodificar; si el archivo cambió se espera al reescaneo
            if any(oriented_size(path) != (img.width, img.height) for img, path in zip(images, paths)):
                raise CompositionError("composition_source_unavailable")
        except FileNotFoundError:
            raise CompositionError("composition_source_unavailable") from None
        boxes = layout(page.template, [img.width / img.height for img in images])
        dest = page_file(page.album_id, page.id, revision)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with heavy():
            try:
                canvas = _compose(paths, boxes, dates, album.background, subjects)
            except FileNotFoundError:
                raise CompositionError("composition_source_unavailable") from None
            try:
                _atomic_save(canvas, dest, JPEG_QUALITY)
                thumb = canvas.resize((THUMB_WIDTH, THUMB_WIDTH * 9 // 16), PILImage.LANCZOS)
                _atomic_save(thumb, page_thumb(page.album_id, page.id, revision), 80)
                thumb.close()
            finally:
                canvas.close()
        with PILImage.open(dest) as check:
            if check.size != FRAME_SIZE:
                raise CompositionError("composition_render_failed")
    except CompositionError as exc:
        page.status, page.last_error = "error", str(exc)
    except (ValueError, OSError, PILImage.DecompressionBombError) as exc:
        logger.warning("Composición %s: %s", page.id, exc)
        page.status, page.last_error = "error", "composition_render_failed"
    else:
        page.status, page.last_error, page.rendered_revision = "ready", None, revision
    page.updated_at = datetime.utcnow()
    db.commit()


def render_pending(db: Session, album_id: int) -> int:
    rendered = 0
    for page in (db.query(CompositionPage)
                 .filter(CompositionPage.album_id == album_id, CompositionPage.status == "pending")
                 .order_by(CompositionPage.id)):
        render_page(db, page)
        rendered += 1
    return rendered


# ------------------------------------------------------------------------ limpieza

def cleanup(db: Session, album_id: int) -> None:
    """Borra páginas retiradas y revisiones que ya no usa ningún TV, y temporales de trabajos interrumpidos."""
    referenced = {}
    for page_id, revision in (db.query(TvContent.page_id, TvContent.page_revision)
                              .join(CompositionPage, CompositionPage.id == TvContent.page_id)
                              .filter(CompositionPage.album_id == album_id)):
        referenced.setdefault(page_id, set()).add(revision)
    needed = {}
    for page in db.query(CompositionPage).filter(CompositionPage.album_id == album_id):
        if page.status == "retired" and page.id not in referenced:
            db.delete(page)
            continue
        keepers = set(referenced.get(page.id, ()))
        if page.status != "retired":
            keepers.update({page.revision, page.rendered_revision})
        needed[page.id] = keepers
    db.commit()
    folder = cache_dir(album_id)
    if not folder.is_dir():
        return
    for entry in folder.iterdir():
        stem = entry.name.split(".", 1)[0]
        page_id, _, revision = stem.partition("-")
        try:
            keep = int(revision) in needed.get(int(page_id), ()) and not entry.name.endswith(".tmp")
        except ValueError:
            keep = False
        if not keep:
            entry.unlink(missing_ok=True)


def remove_cache(album_id: int) -> None:
    folder = cache_dir(album_id)
    if folder.is_dir():
        for entry in folder.iterdir():
            entry.unlink(missing_ok=True)
        os.rmdir(folder)


def process_album(db: Session, album_id: int) -> None:
    """Planifica, renderiza lo pendiente (también lo que quedó a medias tras un reinicio) y limpia."""
    with _job_lock:
        album = db.get(Album, album_id)
        if not album:
            return
        fill_meta(db, album)
        detect_subjects(db, album)
        plan_album(db, album)
        render_pending(db, album.id)
        cleanup(db, album.id)


# ---------------------------------------------------------------- salida efectiva

@dataclass
class OutputItem:
    key: tuple  # ("i", image_id, variante) o ("p", page_id, revisión)
    order: str
    image: Optional[Image] = None
    page: Optional[CompositionPage] = None
    date: str = ""  # fecha que se dibuja en una imagen individual
    fitted: bool = False  # imagen individual completa sobre el fondo, en lugar de recortada a 16:9
    background: str = "paper"
    subject: Optional[list] = None  # recuadro del sujeto hacia el que se orienta el recorte


@dataclass
class Output:
    items: list = field(default_factory=list)
    photos: int = 0  # fotos originales candidatas
    total: int = 0  # imágenes finales para el TV según la agrupación
    pending: int = 0
    errors: int = 0
    error: Optional[str] = None
    current: bool = True  # la agrupación corresponde a las fotos actuales

    @property
    def complete(self) -> bool:
        """Toda la salida está generada: se puede retirar la anterior."""
        return self.current and not self.pending and not self.errors


def row_key(row: TvContent) -> tuple:
    return ("p", row.page_id, row.page_revision) if row.page_id else ("i", row.image_id, row.render_sig or "")


def _single(db: Session, album: Album, img: Image) -> OutputItem:
    date, fitted = date_label(db, album, img), fits_single(album, img)
    subject = subject_box(album, img) if img.width and img.height else None
    return OutputItem(("i", img.id, single_sig(date, fitted, album.background, subject)), img.key, image=img,
                      date=date, fitted=fitted, background=album.background, subject=subject)


def effective_output(db: Session, album: Album) -> Output:
    """Lo que debe estar en el TV: composiciones generadas e imágenes no agrupadas, en el orden del álbum."""
    images = album_images(db, album)
    out = Output(photos=len(images))
    # Sin la fecha leída todavía no se sabe qué variante subir: se espera a la tarea de composición
    out.current = not any(img.taken_at is None and (album.single_fit == "fit" or wants_date(db, album, img))
                          for img in images) and not subjects_pending(album, images)
    if album.composition_mode != "auto":
        out.items = [_single(db, album, img) for img in images]
        out.total = len(images)
        return out
    out.current = out.current and album.composition_plan == candidates_signature(images)
    keys = {img.id: img.key for img in images}
    grouped = set()
    for page in active_pages(db, album.id):
        ids = [m.image_id for m in page.members]
        grouped.update(ids)
        out.total += 1
        if page.status == "error":
            out.errors += 1
            out.error = out.error or page.last_error
        elif page.status != "ready" or not page_file(album.id, page.id, page.revision).exists():
            out.pending += 1
        else:
            order = min((keys.get(i, "") for i in ids), default="")
            out.items.append(OutputItem(("p", page.id, page.revision), order, page=page))
    singles = [img for img in images if img.id not in grouped]
    out.total += len(singles)
    out.items += [_single(db, album, img) for img in singles]
    out.items.sort(key=lambda it: it.order)
    return out
