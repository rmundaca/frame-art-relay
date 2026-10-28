<p align="center">
  <img src="package/app/static/icon-192.png" width="96" height="96" alt="Frame Art Relay icon">
</p>

<h1 align="center">Frame Art Relay</h1>

<p align="center">
  Turn your photo albums into rotating art on <b>Samsung The Frame</b> TVs,<br>
  served from a small self-hosted app on your <b>Asustor NAS</b>.
</p>

---

## Features

| | |
| :--- | :--- |
| **Albums** | Photos from NAS folders or public iCloud shared albums. No Apple login needed. |
| **Schedule** | Weekly time slots per TV that choose which album is shown, and when. |
| **Rotation** | The TV's native slideshow (10 min to 3 days), or app-driven changes every 1 to 5 min. |
| **Layouts** | Two or three photos combined into one 4K image, like an album page. |
| **Display** | Crop to fill the screen or show photos whole over a paper or blurred background. TV mattes and an optional date stamp on iCloud photos. |
| **Smart crop** | Optional. Google Gemini finds people and animals so crops keep them. |
| **TV gallery** | Browse and delete what is stored on the TV. |

The interface works on phone and desktop, can be added to the home screen, has light and dark themes, and is
available in English and Spanish. Every option has an explanation behind the **?** button.

## Requirements

- **Asustor NAS** running ADM 3.x, with **Entware** installed from App Central (it provides Python 3.11).
- **Samsung The Frame** on the same local network. Developed and tested with a 2019 model (art API 0.97).

The app is built for low-end hardware: it runs on an AS-202TE (32-bit, 1 GB RAM).

## Installation

1. Build the package (see [Packaging](#packaging)) or download a release `.apk`.
2. In ADM, open **App Central → Management → Manual Install** and upload `frame-art_<version>_any.apk`.
3. Open `http://<NAS_IP>:8092` in a browser.

Upgrades keep your data and settings. Uninstalling backs up the database to `/volume1/home/frame-art-backup/`.

## Getting started

1. **Add a TV.** Go to **TVs → Add TV** and enter its IP address. Switch the TV to TV mode (not art mode),
   tap **Pair** and accept the prompt on the TV.
2. **Create an album.** Go to **Albums → New album**, then add NAS folders or an iCloud link.
3. **Schedule it.** Go to **Schedule** and add a time slot that shows the album on the TV.

Outside the time slots, rotation stops and the TV stays in art mode. Its motion sensor turns the screen off.

> [!TIP]
> To stop the TV asking for permission on every connection, go to the TV's **Settings → General → Device
> Connection Manager → Access Notification** and choose **First Time Only**.

## Configuration

Defaults live in [`package/config/config.default.yaml`](package/config/config.default.yaml). To change them,
create `package/config/config.yaml` with only the keys you want to override. It survives upgrades.

```yaml
media:
  roots:                    # NAS folders that can be added to albums
    - "/volume1/Photos"
frame:
  max_images_per_album: 100
icloud:
  max_photos: 300           # photos downloaded per shared album
```

App data (database, TV tokens, caches, Gemini settings) is stored in `package/data/`. Set the `APP_DATA_DIR`
environment variable to use another folder.

### iCloud shared albums

Both link formats work:

- `https://photos.icloud.com/shared/album/...`
- `https://www.icloud.com/sharedalbum/#...`

In the album's sharing options, allow **Anyone with the Link** or turn on **Public Website**. Photos are
downloaded as JPEG; videos are skipped.

> [!NOTE]
> iCloud access relies on undocumented Apple endpoints, which may change without notice.

### Smart crop with Gemini

Smart crop is off by default. To use it, add a Gemini API key in **Settings**, then turn on **Smart crop** in
an album.

- Each photo is sent only once, as a reduced copy without EXIF data or location.
- A daily request limit keeps costs under control.
- If Gemini is unavailable, photos are centre-cropped and retried later.

## Security

Frame Art Relay has **no login**. Anyone who can reach port 8092 can control your TVs and change the app's settings.

> [!WARNING]
> Keep it on your local network. Do not expose port 8092 to the internet or forward it on your router.

To report a vulnerability, please open an issue on this repository.

## Development

Python 3.11 is recommended, since it matches the NAS.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r package\requirements.txt
cd package
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8092   # run the app
..\.venv\Scripts\python -m unittest discover -s tests -t .              # run the tests
```

On Linux or macOS, use `python3 -m venv .venv` and `.venv/bin/...` instead.

### Platform constraints

The NAS is a 32-bit i686 machine with 1 GB of RAM, which sets a few firm rules:

- **Dependencies:** FastAPI `<0.100`, Pydantic v1 and `httpx<0.28`. Only pure-Python packages or packages with
  a `manylinux*_i686` wheel. Pillow is pinned to 9.5.0 on i686.
- **Front end:** one `index.html`, one `app.css` and one vanilla `app.js`. No Node, bundlers, CDNs, web fonts
  or service workers.
- **Memory:** images are decoded one at a time, using JPEG draft mode.
- **Scripts:** `CONTROL/*.sh` run under BusyBox `/bin/sh` and must use LF line endings.

### Project layout

```
CONTROL/              ADM package metadata and install/start scripts
package/
├── app/
│   ├── api/          HTTP routes
│   ├── services/     TV client, sync, layouts, photo sources
│   ├── models/       Database tables
│   └── static/       Front end (index.html, css/app.css, js/app.js)
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

The package is written to `dist/frame-art_<version>_any.apk`. On Windows, `build.bat` runs the same script.

To regenerate the icons from `assets/icon-source.png` (1024×1024), run `pip install Pillow` and then
`python tools/make_icons.py`.

## License

Frame Art Relay is released under the [MIT License](LICENSE).

The bundled date-stamp font is a digits-only subset of [Inter](https://rsms.me/inter/), which keeps its own
[SIL Open Font License](package/app/assets/fonts/OFL.txt).

## Credits

- [samsungtvws](https://github.com/xchwarze/samsung-tv-ws-api) (LGPL-3.0) handles the TV connection.
- [Inter](https://rsms.me/inter/) by The Inter Project Authors, for the date stamp.

Frame Art Relay is not affiliated with Samsung, Apple, Google or Asustor.
