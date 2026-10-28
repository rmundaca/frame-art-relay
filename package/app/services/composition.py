"""Automatic layouts: groups several album photos onto a 3840x2160 page, like an album page.

- Grouping is deterministic and stable: valid pages survive rescans and new photos fill incomplete pages
  or form new ones.
- Each photo is cropped at most MAX_CROP per axis so the group fills the canvas; it is never distorted. The
  leftover space becomes background (paper or the photos themselves, blurred) around the group.
- Single photos can be shown whole over that same background (Album.single_fit = "fit").
- Rendering happens outside HTTP requests, one page and one photo at a time, under image_proc's global
  decode lock.
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
RENDERER_VERSION = 2  # 2: limited cell cropping and blurred background

# Fixed page design, in pixels of the 3840x2160 canvas
MARGIN = 96  # minimum border around the photo group
GAP = 48  # gap between photos
BACKGROUND = (236, 234, 230)  # neutral warm grey, like album paper
JPEG_QUALITY = 90
# Maximum crop of each photo per axis (0.15 = up to 15 % of the width or height) so the group fills the
# canvas. With 3:4 and 4:3 photos, trio_v2h goes from 518 to about 276 px of background per side
MAX_CROP = 0.15
# A single photo that loses at most this fraction of its area when cropped to 16:9 fills the screen
# (4:3, 3:2, 16:9); with more loss (portrait, panoramic) it is grouped or, with "fit", shown whole
SINGLE_MAX_CROP = 0.25
SCREEN_RATIO = FRAME_SIZE[0] / FRAME_SIZE[1]
# Blurred background: photos are shrunk to this canvas, blurred, darkened and scaled up
BLUR_SIZE = (240, 135)
BLUR_RADIUS = 8
BLUR_BRIGHTNESS = 0.75
# A template is only accepted if the photos cover at least MIN_FILL of the canvas and none ends up with its
# short side below MIN_SIDE. So two stacked 3:2 landscapes (36 %) stay single, since they barely lose
# anything at 16:9, while portraits, which would lose a lot when cropped, get grouped.
MIN_FILL = 0.40
MIN_SIDE = 640
# Up to this aspect ratio (width / height) a photo takes a portrait cell: includes square ones
VERTICAL_MAX_RATIO = 1.1
# Partners tried for each photo: the nearest ones in album order
LOOKAHEAD = 8

# Tree of each template: ("row" | "col", children); leaves are the photo's position on the page
TEMPLATES = {
    "pair_v": ("row", [0, 1]),  # dos verticales lado a lado
    "pair_h": ("col", [0, 1]),  # dos horizontales apiladas
    "trio_v2h": ("row", [0, ("col", [1, 2])]),  # one portrait next to two stacked landscapes
    "duo_vh": ("row", [0, 1]),  # one portrait and one landscape, asymmetric
    "trio_v": ("row", [0, 1, 2]),  # three portraits in a row: takes the leftover portrait of an odd count
    "single": ("row", [0]),  # a single photo shown whole (single_fit = "fit"); not used when grouping
}
# Orientation each position requires: v portrait or square, h landscape or panoramic
SLOTS = {"pair_v": "vv", "pair_h": "hh", "trio_v2h": "vhh", "duo_vh": "vh", "trio_v": "vvv"}

# Serializes planning, rendering and cleanup for all albums: only one 4K canvas at a time
_job_lock = threading.Lock()


class CompositionError(Exception):
    """Stable code: composition_source_unavailable, composition_render_failed."""


# ------------------------------------------------------------------ layout

def _orientation(ratio: float) -> str:
    return "v" if ratio <= VERTICAL_MAX_RATIO else "h"


def _linear(node, ratios) -> tuple:
    """(a, b) such that the node width is a * height + b."""
    if isinstance(node, int):
        return ratios[node], 0.0
    kind, children = node
    parts = [_linear(c, ratios) for c in children]
    gaps = GAP * (len(children) - 1)
    if kind == "row":
        return sum(a for a, _ in parts), sum(b for _, b in parts) + gaps
    # Column of common width w: height = w * sum(1/a) - sum(b/a) + gaps; solve for w
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
    """Fraction of the photo lost when cropping it to the screen aspect ratio."""
    return 1 - min(ratio / SCREEN_RATIO, SCREEN_RATIO / ratio)


def crop_factor(template: str, ratios) -> float:
    """Common factor for the cell aspect ratios (photo aspect * f) that fits the group to the usable area of
    the canvas, limited to MAX_CROP per axis: f < 1 crops the sides and f > 1 the top and bottom."""
    box_w, box_h = FRAME_SIZE[0] - 2 * MARGIN, FRAME_SIZE[1] - 2 * MARGIN
    lo, hi = 1 - MAX_CROP, 1 / (1 - MAX_CROP)

    def too_wide(f):
        a, b = _linear(TEMPLATES[template], [r * f for r in ratios])
        return a * box_h + b > box_w

    # Widening the cells always widens the group: find the point where it fills width and height at once
    if too_wide(lo):
        return lo
    if not too_wide(hi):
        return hi
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if too_wide(mid) else (mid, hi)
    return lo


def layout(template: str, ratios: list) -> list:
    """Rectangles (x, y, width, height) for each position, centred on the canvas, with the crop_factor crop."""
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
    """Fraction of the canvas covered by the photos, or None if the template is not suitable."""
    slots = SLOTS[template]
    if len(ratios) != len(slots) or any(_orientation(r) != s for r, s in zip(ratios, slots)):
        return None
    # Two landscapes that already fill the screen on their own (4:3, 3:2, 16:9) are not stacked: they would look smaller
    if template == "pair_h" and any(single_loss(r) <= SINGLE_MAX_CROP for r in ratios):
        return None
    boxes = layout(template, ratios)
    if min(min(w, h) for _, _, w, h in boxes) < MIN_SIDE:
        return None
    fill = sum(w * h for _, _, w, h in boxes) / (FRAME_SIZE[0] * FRAME_SIZE[1])
    return fill if fill >= MIN_FILL else None


# -------------------------------------------------------------------- grouping

def _ordered(template: str, ids: list, ratio: dict, pos: dict) -> list:
    """Members in the order of the template positions; for equal orientation, album order."""
    return sorted(ids, key=lambda i: (SLOTS[template].index(_orientation(ratio[i])), pos[i]))


def group(candidates: list, existing: dict = None) -> tuple:
    """Group photos into pages.

    candidates: [(image_id, aspect ratio or None)] in album order; None means it could not be measured.
    existing: {page_id: (template, [image_id])} from the previous grouping.
    Returns (keep, new): keep = {page_id: (template, [image_id])} for the pages that remain (possibly
    extended), new = [(template, [image_id])]. All other photos stay single.
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

    # Incomplete pages: one portrait with one landscape accepts a second landscape
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

    # Portraits lose the most when cropped to 16:9: they pick a partner first
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

    # A leftover portrait (odd count) joins the nearest pair of portraits, new or existing
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

# Margin around the subject we try to keep, as a fraction of the photo
SUBJECT_PAD = 0.025


def subject_box(album: Album, img: Image) -> Optional[list]:
    """Current subject box ([x0, y0, x1, y1] in 0-1) if the album uses detection, or None."""
    if not album.subject_detection or not img.subject_box or img.subject_sig != _version(img):
        return None
    try:
        box = json.loads(img.subject_box)
        return [float(v) for v in box] if len(box) == 4 else None
    except (ValueError, TypeError):
        return None


def subjects_pending(album: Album, images: list) -> bool:
    """There are unanalysed photos and detection works: the output waits so two versions are not uploaded."""
    return bool(album.subject_detection and not album.subject_error
                and any(img.subject_sig != _version(img) for img in images))


def detect_subjects(db: Session, album: Album, client=None) -> None:
    """Analyse with Gemini the album photos that go to the TV and have no result for their version yet.

    A failure specific to one photo leaves it without a subject (centre crop); a general one (network, key, quota)
    stops the batch and is stored in album.subject_error: the output continues with centre crops and retries later."""
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
            box = None  # unreadable photo: no subject
        img.subject_box, img.subject_sig = (json.dumps(box) if box else ""), version
        db.commit()
    album.subject_error = error
    db.commit()


def _window(lo: float, hi: float, visible: float, keep_start: bool) -> float:
    """Position (0-1, like ImageOps.fit centering) of a window of size visible over [0, 1] that contains
    [lo, hi] if it fits; otherwise centred on the subject or, with keep_start, aligned to its start (heads)."""
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
    """ImageOps.fit centering that keeps the subject when cropping the photo to the cell aspect ratio."""
    if not box:
        return 0.5, 0.5
    x0, y0, x1, y1 = box
    if cell_ratio < photo_ratio:  # the sides are cropped
        return _window(x0, x1, cell_ratio / photo_ratio, False), 0.5
    return 0.5, _window(y0, y1, photo_ratio / cell_ratio, True)


def page_signature(template: str, images: list, dates: list = (), background: str = "paper",
                   subjects: list = ()) -> str:
    parts = [f"r{RENDERER_VERSION}", template, f"{MARGIN},{GAP},{BACKGROUND},{JPEG_QUALITY},{MAX_CROP}",
             background, *(_version(img) for img in images)]
    if any(dates):
        # Only if some photo has a date: pages without dates keep their previous signature
        parts.append("dates:" + ",".join(dates))
    if any(subjects):
        parts.append("subjects:" + json.dumps(list(subjects)))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def single_sig(date: str, fitted: bool = False, background: str = "paper", subject: Optional[list] = None) -> str:
    """Variant of a single image on the TV (TvContent.render_sig); "" is the 16:9 crop without a date."""
    parts = [f"fit{RENDERER_VERSION}:{MAX_CROP}:{background}"] if fitted else []
    if date:
        parts.append(f"date={date}")
    if subject:
        parts.append("subj=" + ",".join(f"{v:.3f}" for v in subject))
    return ";".join(parts)


def fits_single(album: Album, img: Image) -> bool:
    """The single photo is shown whole over the background: the album asks for it and a 16:9 crop would lose a lot."""
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
    """Recompute the album grouping, keeping the pages that are still valid."""
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
    """Background made from the photos themselves: the group stretched to the whole canvas, heavily blurred and darkened.

    Works on a BLUR_SIZE canvas and each photo is decoded at the smallest scale (draft)."""
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
    """3840x2160 canvas with each photo cropped to its cell (centred or towards its subject) and its date; one photo
    decoded at a time."""
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
    """JPEG of a single photo: cropped to 16:9 or, if item.fitted, whole over the album background."""
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
    """Render the JPEG and thumbnail of the current revision; leaves the page ready or in error."""
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
            # Header and limits before decoding; if the file changed, wait for the rescan
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
        logger.warning("Layout %s: %s", page.id, exc)
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
    """Delete retired pages, revisions no TV uses any more, and temp files from interrupted jobs."""
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
    """Plan, render whatever is pending (including work left half-done by a restart) and clean up."""
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
    key: tuple  # ("i", image_id, variant) or ("p", page_id, revision)
    order: str
    image: Optional[Image] = None
    page: Optional[CompositionPage] = None
    date: str = ""  # date drawn on a single image
    fitted: bool = False  # single image shown whole over the background instead of cropped to 16:9
    background: str = "paper"
    subject: Optional[list] = None  # subject box the crop is steered towards


@dataclass
class Output:
    items: list = field(default_factory=list)
    photos: int = 0  # candidate original photos
    total: int = 0  # final images for the TV according to the grouping
    pending: int = 0
    errors: int = 0
    error: Optional[str] = None
    current: bool = True  # the grouping matches the current photos

    @property
    def complete(self) -> bool:
        """The whole output is rendered: the previous one can be retired."""
        return self.current and not self.pending and not self.errors


def row_key(row: TvContent) -> tuple:
    return ("p", row.page_id, row.page_revision) if row.page_id else ("i", row.image_id, row.render_sig or "")


def _single(db: Session, album: Album, img: Image) -> OutputItem:
    date, fitted = date_label(db, album, img), fits_single(album, img)
    subject = subject_box(album, img) if img.width and img.height else None
    return OutputItem(("i", img.id, single_sig(date, fitted, album.background, subject)), img.key, image=img,
                      date=date, fitted=fitted, background=album.background, subject=subject)


def effective_output(db: Session, album: Album) -> Output:
    """What should be on the TV: rendered layouts and ungrouped images, in album order."""
    images = album_images(db, album)
    out = Output(photos=len(images))
    # Until the date is read we do not know which variant to upload: wait for the layout task
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
