# Frame Art

A lightweight, self-hosted web app for an **Asustor NAS** that turns photo albums into rotating art on
**Samsung The Frame** TVs. Albums come from NAS folders or public iCloud shared albums; each TV follows a
weekly schedule of time slots.

Built for low-end hardware: it runs on an Asustor AS-202TE (i686, 32-bit, 1 GB RAM) with FastAPI, SQLite and a
dependency-free vanilla JS front end.

## Features

- **Albums** from NAS folders (optionally recursive) and public iCloud shared albums, no Apple login needed.
- **Schedule**: per-TV weekly time slots that pick which album is shown and when.
- **Rotation** using the TV's native slideshow (10 min to 3 days), or app-driven rotation for 1-5 minutes.
- **Automatic layouts**: two or three photos combined into one 3840x2160 image, like an album page.
- **Display options**: crop to fill the screen or show portraits whole over a paper or blurred background;
  TV mattes; optional date stamp on iCloud photos.
- **Smart crop** (optional): asks Google Gemini where people and animals are so crops keep them.
- **TV gallery**: browse and delete what is on the TV's "My Photos".
- Mobile-friendly, installable as a home-screen web app, light and dark themes, English and Spanish UI.

Every option in the album and settings forms is explained in the app's help (**?**) button.

## Requirements

- Asustor NAS with ADM 3.x and **Entware** installed from App Central (provides Python 3.11).
  Other x86/ARM hosts with Python 3.10+ work for development.
- Samsung The Frame on the same LAN. Developed and tested against a 2019 model (art API 0.97).

## Install on the NAS

1. Build the package (see [Packaging](#packaging)) or download a release `.apk`.
2. ADM → App Central → Management → Manual Install → upload `frame-art_<version>_any.apk`.
3. Open `http://<NAS_IP>:8092`.

The installer creates a virtualenv with the dependencies. Upgrades keep the database, tokens, caches and
`config/config.yaml`. Uninstalling backs up the database to `/volume1/home/frame-art-backup/`.

## First use

1. **TVs** → Add TV with its IP address. Switch the TV to TV mode (not art mode), tap **Pair** and accept the
   prompt on screen. To stop it asking again: TV Settings → General → Device Connection Manager → Access
   Notification → First Time Only.
2. **Albums** → New album, then add NAS folders or an iCloud link.
3. **Schedule** → add a time slot that assigns the album to the TV.

Outside every time slot rotation stops and the TV stays in art mode; its motion sensor turns the screen off.

## Configuration

Defaults live in [package/config/config.default.yaml](package/config/config.default.yaml). Override any key in
`package/config/config.yaml` (not packaged, preserved on upgrade):

```yaml
media:
  roots:            # NAS folders that can be added to albums
    - "/volume1/Photos"
frame:
  max_images_per_album: 100
icloud:
  max_photos: 300   # photos downloaded per shared album
```

Mutable data (SQLite database, TV tokens, caches, Gemini settings) lives in `package/data/`, or in the folder
set by the `APP_DATA_DIR` environment variable.

### iCloud shared albums

Both `https://photos.icloud.com/shared/album/...` and `https://www.icloud.com/sharedalbum/#...` links work. In
the album's sharing options, allow **Anyone with the Link** or turn on **Public Website**. Photos are downloaded
as JPEG to the data cache; videos are skipped. These integrations use undocumented Apple endpoints that may
change.

### Smart crop with Gemini

Off by default. Add a Gemini API key in **Settings** and enable **Smart crop** on an album. Each photo is sent
once, as a reduced copy (no EXIF, no location), and only to the Gemini API host. A daily request limit is
configurable. If Gemini fails, photos are centre-cropped and retried later.

## Development

Python 3.11 is recommended (it matches the NAS). From the repository root on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r package\requirements.txt
cd package
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8092
..\.venv\Scripts\python -m unittest discover -s tests -t .
```

On Linux or macOS use `python3 -m venv .venv` and `.venv/bin/...` instead.

### Platform constraints

The NAS is 32-bit i686 with 1 GB of RAM, which drives a few hard rules:

- FastAPI `<0.100`, Pydantic v1, `httpx<0.28`. Only pure-Python packages or packages with a
  `manylinux*_i686` wheel (Pillow is pinned to 9.5.0 on i686).
- No Node, bundlers, CDNs, web fonts or service workers. The front end is one `index.html`, one `app.css` and
  one vanilla `app.js`.
- Images are decoded one at a time with JPEG draft mode to keep peak memory low.
- `CONTROL/*.sh` scripts run under BusyBox `/bin/sh` and must use LF line endings.

### Project layout

```
CONTROL/            ADM package metadata and install/start scripts
package/app/        FastAPI app: api/ (routes), services/ (TV client, sync, layouts, sources), models/
package/app/static/ Single-page front end (index.html, css/app.css, js/app.js)
package/config/     Default configuration
package/tests/      unittest suite
tools/              Icon generator and a layout rendering benchmark
build_package.py    Builds the .apk
```

## Packaging

```powershell
python build_package.py -m "What changed"   # bump patch version -> dist/frame-art_<version>_any.apk
python build_package.py --bump minor        # or major, --version X.Y.Z, --no-bump
```

`build.bat` is a Windows shortcut for the same script. To regenerate icons from `assets/icon-source.png`
(1024x1024): `pip install Pillow` and run `python tools/make_icons.py`.

## Credits

- [samsungtvws](https://github.com/xchwarze/samsung-tv-ws-api) (LGPL-3.0) for the TV connection.
- The date stamp uses a digits-only subset of [Inter](https://rsms.me/inter/), under the SIL Open Font License
  ([package/app/assets/fonts/OFL.txt](package/app/assets/fonts/OFL.txt)).

Not affiliated with Samsung, Apple, Google or Asustor.
