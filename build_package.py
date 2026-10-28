#!/usr/bin/env python3
"""
build_package.py - Builds the Asustor ADM APKG package (.apk) with semver versioning.

Usage:
    python build_package.py                       # patch: 1.0.0 -> 1.0.1
    python build_package.py --bump minor          # 1.0.0 -> 1.1.0
    python build_package.py --bump major          # 1.0.0 -> 2.0.0
    python build_package.py --version 1.2.0       # exact version
    python build_package.py --no-bump             # rebuild the current version
    python build_package.py -m "Change note"      # entry in CONTROL/changelog.txt
"""
import argparse
import io
import json
import os
import re
import sys
import tarfile
import zipfile
from datetime import date
from pathlib import Path

# Safe UTF-8 output on Windows consoles
if (sys.stdout.encoding or "").lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
CONTROL_DIR = ROOT_DIR / "CONTROL"
PACKAGE_DIR = ROOT_DIR / "package"
DIST_DIR = ROOT_DIR / "dist"
CONFIG_JSON = CONTROL_DIR / "config.json"
CHANGELOG_TXT = CONTROL_DIR / "changelog.txt"
APP_INIT_PY = PACKAGE_DIR / "app" / "__init__.py"

# Never packaged: caches, environments, tests, runtime data and local overrides
EXCLUDED_DIR_NAMES = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "venv", ".venv", "tests"}
EXCLUDED_PATHS = {"data", "config/config.yaml"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".log", ".bak", ".tmp", ".apk", ".db", ".db-wal", ".db-shm")


def load_config() -> dict:
    if not CONFIG_JSON.exists():
        raise FileNotFoundError(f"{CONFIG_JSON} not found")
    return json.loads(CONFIG_JSON.read_text(encoding="utf-8"))


def parse_semver(ver: str):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", ver.strip())
    if not m:
        raise ValueError(f"Invalid version: '{ver}' (expected X.Y.Z)")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_version(ver: str, kind: str) -> str:
    major, minor, patch = parse_semver(ver)
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def update_version_in_files(new_version: str, note: str, app_name: str):
    print(f"\n[1/4] Updating version to {new_version}...")

    config = load_config()
    config.setdefault("general", {})["version"] = new_version
    config["version"] = new_version
    CONFIG_JSON.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  [OK] {CONFIG_JSON.relative_to(ROOT_DIR)}")

    existing = CHANGELOG_TXT.read_text(encoding="utf-8").strip() if CHANGELOG_TXT.exists() else ""
    if not existing.startswith(new_version):
        entry = f"{new_version} ({date.today().isoformat()})\n- {note or f'{app_name} update.'}\n\n"
        CHANGELOG_TXT.write_text(entry + existing + "\n", encoding="utf-8")
        print(f"  [OK] {CHANGELOG_TXT.relative_to(ROOT_DIR)}")

    if APP_INIT_PY.exists():
        content = APP_INIT_PY.read_text(encoding="utf-8")
        content = re.sub(r'__version__\s*=\s*["\'][^"\']+["\']', f'__version__ = "{new_version}"', content)
        APP_INIT_PY.write_text(content, encoding="utf-8")
        print(f"  [OK] {APP_INIT_PY.relative_to(ROOT_DIR)}")


def _tarinfo(name: str, mode: int, mtime: float, size: int = 0, is_dir: bool = False) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(name=name)
    ti.mode = mode
    ti.mtime = int(mtime)
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = "root"
    if is_dir:
        ti.type = tarfile.DIRTYPE
    else:
        ti.size = size
    return ti


def build_control_tar() -> bytes:
    print("\n[2/4] Building control.tar.gz...")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in sorted(CONTROL_DIR.iterdir()):
            if not path.is_file():
                continue
            data = path.read_bytes()
            mode = 0o644
            if path.suffix == ".sh":
                data = data.replace(b"\r\n", b"\n")  # CRLF breaks /bin/sh on the NAS
                mode = 0o755
            tar.addfile(_tarinfo(path.name, mode, path.stat().st_mtime, len(data)), io.BytesIO(data))
            print(f"   + {path.name} ({oct(mode)})")
    return buf.getvalue()


def _excluded(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in EXCLUDED_DIR_NAMES for p in parts):
        return True
    if parts[0] in EXCLUDED_PATHS or rel in EXCLUDED_PATHS:
        return True
    return rel.endswith(EXCLUDED_SUFFIXES)


def build_data_tar() -> bytes:
    print("\n[3/4] Building data.tar.gz...")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(PACKAGE_DIR):
            base = Path(root)
            dirs[:] = sorted(d for d in dirs if not _excluded((base / d).relative_to(PACKAGE_DIR).as_posix()))
            for d in dirs:
                full = base / d
                tar.addfile(_tarinfo(full.relative_to(PACKAGE_DIR).as_posix(), 0o755, full.stat().st_mtime, is_dir=True))
            for f in sorted(files):
                full = base / f
                rel = full.relative_to(PACKAGE_DIR).as_posix()
                if _excluded(rel):
                    continue
                data = full.read_bytes()
                tar.addfile(_tarinfo(rel, 0o644, full.stat().st_mtime, len(data)), io.BytesIO(data))
    return buf.getvalue()


def build_apkg(version: str, config: dict):
    pkg = config["general"]["package"]
    port = config.get("adm-desktop", {}).get("app", {}).get("port")
    control_bytes = build_control_tar()
    print(f"  [OK] control.tar.gz: {len(control_bytes) / 1024:.1f} KB")
    data_bytes = build_data_tar()
    print(f"  [OK] data.tar.gz: {len(data_bytes) / 1024:.1f} KB")

    print("\n[4/4] Creating .apk container...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [DIST_DIR / f"{pkg}.apk", DIST_DIR / f"{pkg}_{version}_any.apk"]
    for target in outputs:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("apkg-version", b"2.0\n")
            zf.writestr("control.tar.gz", control_bytes)
            zf.writestr("data.tar.gz", data_bytes)
        print(f"  [OK] dist/{target.name} ({target.stat().st_size / 1024:.1f} KB)")

    print("\n" + "=" * 65)
    print(f" {config['general']['name']} v{version} packaged")
    print("=" * 65)
    print("  1. ADM (http://<NAS_IP>:8000) -> App Central -> Management -> Manual Install")
    print(f"  2. Upload dist/{outputs[1].name} and install it")
    print(f"  3. Open http://<NAS_IP>:{port}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Builds the Asustor APKG package.")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--version", type=str, default=None, help="Exact version X.Y.Z")
    parser.add_argument("--no-bump", action="store_true", help="Keep the current version")
    parser.add_argument("-m", "--message", type=str, default=None, help="Note for changelog.txt")
    args = parser.parse_args()

    config = load_config()
    current = config.get("general", {}).get("version") or config.get("version", "1.0.0")
    if args.no_bump:
        new_version = current
    elif args.version:
        parse_semver(args.version)
        new_version = args.version
    else:
        new_version = bump_version(current, args.bump)

    print("=" * 65)
    print(f"  {config['general']['name']} - Asustor Package Builder")
    print(f"  v{current} -> v{new_version}")
    print("=" * 65)

    update_version_in_files(new_version, args.message, config["general"]["name"])
    build_apkg(new_version, load_config())


if __name__ == "__main__":
    main()
