"""Benchmarks rendering a layout with real photos on the NAS.

Usage (from package/, with the Python of the app's venv):
    python ../tools/compose_bench.py portrait.jpg landscape1.jpg landscape2.jpg [--blur] [--date 2021-04-24]
    python ../tools/compose_bench.py portrait.jpg --single [--blur] [--date 2021-04-24]

Picks the template the app would use for those aspect ratios (or "single", one photo whole over the background),
renders the 3840x2160 page with the same code as the app and prints the time and the process peak memory
(ru_maxrss). Proposed acceptance threshold: peak below 200 MB with three 48 MP originals.
"""
import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="compose-bench-"))
sys.path.insert(0, str(Path.cwd()))

from app.services import composition  # noqa: E402
from app.services.image_proc import heavy, oriented_size  # noqa: E402


def peak_mb() -> float:
    try:
        import resource
    except ImportError:  # Windows: no ru_maxrss
        return float("nan")
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB on Linux


def main(args):
    paths = args.photos
    sizes = [oriented_size(p) for p in paths]
    ratios = [w / h for w, h in sizes]
    if args.single:
        if len(paths) != 1:
            sys.exit("--single takes a single photo")
        template, order = "single", [0]
    else:
        _, new = composition.group(list(enumerate(ratios)))
        if not new or len(new[0][1]) != len(paths):
            sys.exit(f"Those aspect ratios do not form a single page: {[round(r, 2) for r in ratios]} -> {new}")
        template, order = new[0]
    boxes = composition.layout(template, [ratios[i] for i in order])
    background = "blur" if args.blur else "paper"
    f = composition.crop_factor(template, [ratios[i] for i in order])
    print(f"Template {template}; photos {[f'{w}x{h}' for w, h in sizes]}; crop f={f:.3f}; background {background}; "
          f"side background {boxes[0][0]} px; before: {peak_mb():.0f} MB")
    start = time.monotonic()
    with heavy():
        canvas = composition._compose([paths[i] for i in order], boxes, [args.date] * len(order), background)
        rendered = time.monotonic() - start
        out = Path(tempfile.gettempdir()) / "compose-bench.jpg"
        canvas.save(out, "JPEG", quality=composition.JPEG_QUALITY, optimize=True)
        canvas.close()
    print(f"Rendered in {rendered:.1f} s, total {time.monotonic() - start:.1f} s, "
          f"process peak {peak_mb():.0f} MB -> {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("photos", nargs="+")
    p.add_argument("--single", action="store_true", help="One photo whole over the background (single_fit = fit)")
    p.add_argument("--blur", action="store_true", help="Blurred background instead of paper")
    p.add_argument("--date", default="", help="Date drawn on each photo (YYYY-MM-DD)")
    main(p.parse_args())
