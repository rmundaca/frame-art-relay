#!/bin/sh
PKG="frame-art"
APKG_PATH="/usr/local/AppCentral/$PKG"
STASH_DIR="/volume1/.$PKG-upgrade"

# Requires Python >= 3.10. ADM's Python on the AS-202TE is 3.7, so Entware (App Central) is needed.

export PATH="/opt/bin:/opt/sbin:$PATH"

HAS_MODERN_PY=0
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)' 2>/dev/null)
    if [ -n "$PY_VER" ] && [ "$PY_VER" -ge 310 ]; then
        HAS_MODERN_PY=1
    fi
fi

if [ "$HAS_MODERN_PY" -eq 0 ] && [ ! -x "/opt/bin/opkg" ] && [ ! -x "/opt/bin/python3" ]; then
    echo "=================================================================="
    echo "ERROR: this app requires Python 3.10 or later."
    echo "Install 'Entware' from App Central and try again."
    echo "=================================================================="
    exit 1
fi

# Upgrade: ADM deletes the whole app folder, so the data (DB, tokens, caches), the config override
# and the venv are stashed; post-install.sh restores them.
if [ -d "$APKG_PATH/data" ]; then
    if [ -f "$APKG_PATH/CONTROL/start-stop.sh" ]; then
        "$APKG_PATH/CONTROL/start-stop.sh" stop  # closes the DB (WAL checkpoint) before moving it
    fi
    rm -rf "$STASH_DIR"
    mkdir -p "$STASH_DIR"
    mv "$APKG_PATH/data" "$STASH_DIR/data" || exit 1
    [ -f "$APKG_PATH/config/config.yaml" ] && cp "$APKG_PATH/config/config.yaml" "$STASH_DIR/config.yaml"
    [ -d "$APKG_PATH/venv" ] && mv "$APKG_PATH/venv" "$STASH_DIR/venv"
    echo "Data stashed in $STASH_DIR"
fi

exit 0
