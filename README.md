<p align="center">
  <img src="package/app/static/icon-192.png" width="96" height="96" alt="Frame Art Relay icon">
</p>

<h1 align="center">Frame Art Relay</h1>

<p align="center">
  Turn your photo albums into rotating art on <b>Samsung The Frame</b> TVs,<br>
  served from a small self-hosted app on your <b>Asustor NAS</b> or any always-on computer.
</p>

---

## Features

| | |
| :--- | :--- |
| **Albums** | Photos from local or network folders, or public iCloud shared albums (no Apple login). |
| **Schedule** | Weekly time slots per TV that choose which album is shown. |
| **Rotation** | The app changes the image (1 min to 3 days) among the active album's photos, only while the screen is on. |
| **Layouts** | Two or three photos combined into one 4K image. |
| **Display** | Crop to fill, or whole photos over a paper or blurred background. TV mattes and optional date stamp. |
| **Smart crop** | Optional. Google Gemini finds people and animals so crops keep them. |
| **TV storage** | Albums stay on the TV when the slot changes and are only deleted with the album. MB per album and TV, with a warning above a limit. |
| **TV gallery** | Browse and delete what is stored on the TV. |

Works on phone and desktop, in English and Spanish, with light and dark themes. Every option is explained
behind its **?** button.

## Requirements

- **Samsung The Frame** on the same local network. Tested with a 2019 model (art API 0.97).
- One of:
  - **Asustor NAS** with ADM 3.x and **Entware** (from App Central). Runs on an AS-202TE (32-bit, 1 GB RAM).
  - **Any computer** with Python 3.11 or newer that stays on (Windows, macOS, Linux, Raspberry Pi).

## Installation

### On the NAS

1. Build the package (see [Packaging](#packaging)) or download a release `.apk`.
2. In ADM, go to **App Central → Management → Manual Install** and upload `frame-art_<version>_any.apk`.
3. Open `http://<NAS_IP>:8092`.

Upgrades keep your data. Uninstalling backs up the database to `/volume1/home/frame-art-backup/`.

### On a computer

From the repository root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r package\requirements.txt
```

Then set your photo folders in `package/config/config.yaml` (see [Configuration](#configuration)) and start
the app from the `package` folder:

```powershell
cd package
..\.venv\Scripts\python -m app.main
```

Open `http://localhost:8092`, or `http://<COMPUTER_IP>:8092` from a phone.

- On Linux or macOS, use `python3` and `.venv/bin/python`.
- On Windows, name the Python version (`py -0` lists them). `py -3` may pick a free-threaded build (`3.13t`),
  which does not work.
- If the repository folder is moved or renamed, recreate the venv with `--clear`.
- Allow Python through the Windows firewall (private networks) to reach the app from other devices.

## Getting started

1. **Add a TV.** Go to **TVs → Add TV** and enter its IP address. With the TV in TV mode (not art mode), tap
   **Pair** and accept the prompt on the TV.
2. **Create an album.** Go to **Albums → New album** and add folders or an iCloud link.
3. **Schedule it.** Go to **Schedule** and add a time slot for the album.

Outside the time slots, the TV stays in art mode and its motion sensor turns the screen off.

> [!TIP]
> To stop the TV asking for permission on every connection, set **Settings → General → Device Connection
> Manager → Access Notification** to **First Time Only**.

## Configuration

Override any default from [`config.default.yaml`](package/config/config.default.yaml) in
`package/config/config.yaml`, which survives upgrades:

```yaml
media:
  roots:                          # folders that can be added to albums
    - "/volume1/Photos"
    - 'C:\Users\me\Pictures'
    - '\\192.168.1.20\Photos\Frame'
frame:
  max_images_per_album: 100
  storage_warn_mb: 1024           # warn when the app has uploaded more than this to a TV
icloud:
  max_photos: 300                 # photos downloaded per shared album
```

- Quote Windows paths with single quotes (or use `/`). In double quotes, `\` is an escape character.
- Network shares are accessed as the user running the app. Scanning them is slow, so list specific folders.
- App data is stored in `package/data/`, or in the folder set by `APP_DATA_DIR`.

### iCloud shared albums

Paste a `photos.icloud.com/shared/album/...` or `icloud.com/sharedalbum/#...` link. The album must allow
**Anyone with the Link** or have **Public Website** on. Videos are skipped.

> [!NOTE]
> iCloud access relies on undocumented Apple endpoints, which may change without notice.

### Smart crop with Gemini

Add a Gemini API key in **Settings**, then turn on **Smart crop** in an album. Each photo is sent once, as a
reduced copy without EXIF or location. A daily request limit caps costs; if Gemini fails, photos are
centre-cropped and retried later.

## Security

There is **no login**: anyone who can reach port 8092 controls your TVs.

> [!WARNING]
> Keep it on your local network. Do not expose or forward port 8092.

Report vulnerabilities by opening an issue.

## Development

```powershell
cd package
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8092   # run with auto-reload
..\.venv\Scripts\python -m unittest discover -s tests -t .              # run the tests
```

Python 3.11 matches the NAS. The NAS (32-bit i686, 1 GB RAM) sets these rules:

- **Dependencies:** FastAPI `<0.100`, Pydantic v1, `httpx<0.28`. Pure-Python packages or ones with a
  `manylinux*_i686` wheel only. Pillow is pinned to 9.5.0 on i686.
- **Front end:** one `index.html`, `app.css` and vanilla `app.js`. No Node, bundlers, CDNs, web fonts or
  service workers.
- **Memory:** images are decoded one at a time, using JPEG draft mode.
- **Scripts:** `CONTROL/*.sh` run under BusyBox `/bin/sh` with LF line endings.

```
CONTROL/              ADM package metadata and install/start scripts
package/
├── app/
│   ├── api/          HTTP routes
│   ├── services/     TV client, sync, layouts, photo sources
│   ├── models/       Database tables
│   └── static/       Front end
├── config/           Default configuration
└── tests/            Test suite
tools/                Icon generator and layout benchmark
build_package.py      Builds the .apk
```

## Packaging

```powershell
python build_package.py -m "What changed"   # bump the patch version and build
python build_package.py --bump minor        # or: --bump major, --version X.Y.Z, --no-bump
```

Output goes to `dist/frame-art_<version>_any.apk` (`build.bat` does the same on Windows). To regenerate the
icons from `assets/icon-source.png`, run `python tools/make_icons.py` (needs Pillow).

## License and credits

Released under the [MIT License](LICENSE).

- [samsungtvws](https://github.com/xchwarze/samsung-tv-ws-api) (LGPL-3.0) handles the TV connection.
- The date stamp uses a digits-only subset of [Inter](https://rsms.me/inter/)
  ([SIL Open Font License](package/app/assets/fonts/OFL.txt)).

Not affiliated with Samsung, Apple, Google or Asustor.
