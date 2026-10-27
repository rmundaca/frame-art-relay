"""Mide en el NAS el renderizado de una composición con fotos reales (fases 10 y 11).

Uso (desde package/, con el Python del venv de la app):
    python ../tools/compose_bench.py vertical.jpg horizontal1.jpg horizontal2.jpg [--blur] [--date 2021-04-24]
    python ../tools/compose_bench.py vertical.jpg --single [--blur] [--date 2021-04-24]

Elige la plantilla que la app usaría con esas proporciones (o "single", una foto completa sobre el fondo),
genera la página de 3840x2160 con el mismo código que la app y muestra el tiempo y el pico de memoria del
proceso (ru_maxrss). Umbral de aceptación propuesto: pico inferior a 200 MB con tres originales de 48 MP.
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
    except ImportError:  # Windows: sin ru_maxrss
        return float("nan")
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB en Linux


def main(args):
    paths = args.photos
    sizes = [oriented_size(p) for p in paths]
    ratios = [w / h for w, h in sizes]
    if args.single:
        if len(paths) != 1:
            sys.exit("--single admite una sola foto")
        template, order = "single", [0]
    else:
        _, new = composition.group(list(enumerate(ratios)))
        if not new or len(new[0][1]) != len(paths):
            sys.exit(f"Esas proporciones no forman una sola página: {[round(r, 2) for r in ratios]} -> {new}")
        template, order = new[0]
    boxes = composition.layout(template, [ratios[i] for i in order])
    background = "blur" if args.blur else "paper"
    f = composition.crop_factor(template, [ratios[i] for i in order])
    print(f"Plantilla {template}; fotos {[f'{w}x{h}' for w, h in sizes]}; recorte f={f:.3f}; fondo {background}; "
          f"fondo lateral {boxes[0][0]} px; antes: {peak_mb():.0f} MB")
    start = time.monotonic()
    with heavy():
        canvas = composition._compose([paths[i] for i in order], boxes, [args.date] * len(order), background)
        rendered = time.monotonic() - start
        out = Path(tempfile.gettempdir()) / "compose-bench.jpg"
        canvas.save(out, "JPEG", quality=composition.JPEG_QUALITY, optimize=True)
        canvas.close()
    print(f"Renderizado {rendered:.1f} s, total {time.monotonic() - start:.1f} s, "
          f"pico del proceso {peak_mb():.0f} MB -> {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("photos", nargs="+")
    p.add_argument("--single", action="store_true", help="Una foto completa sobre el fondo (single_fit = fit)")
    p.add_argument("--blur", action="store_true", help="Fondo desenfocado en lugar de papel")
    p.add_argument("--date", default="", help="Fecha que se dibuja en cada foto (YYYY-MM-DD)")
    main(p.parse_args())
