#!/usr/bin/env python3
"""Genera todos los iconos (ADM, PWA, favicon) desde assets/icon-source.png (1024×1024)."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icon-source.png"
STATIC = ROOT / "package" / "app" / "static"
BACKGROUND = (244, 244, 246)  # #F4F4F6: rellena cualquier transparencia

TARGETS = {
    ROOT / "CONTROL" / "icon.png": 128,
    STATIC / "icon.png": 128,
    STATIC / "icon-192.png": 192,
    STATIC / "icon-512.png": 512,
    STATIC / "apple-touch-icon.png": 180,
    STATIC / "favicon-32x32.png": 32,
    STATIC / "favicon-16x16.png": 16,
}


def main():
    src = Image.open(SOURCE).convert("RGBA")
    if src.width != src.height:
        raise SystemExit("assets/icon-source.png debe ser cuadrado")
    flat = Image.new("RGB", src.size, BACKGROUND)
    flat.paste(src, mask=src.getchannel("A"))

    for path, size in TARGETS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        flat.resize((size, size), Image.LANCZOS).save(path, optimize=True)
        print(f"  [OK] {path.relative_to(ROOT)} ({size}x{size})")
    flat.save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32)])
    print(f"  [OK] {(STATIC / 'favicon.ico').relative_to(ROOT)} (16, 32)")


if __name__ == "__main__":
    main()
