#!/bin/sh
PKG="frame-art"
APKG_PATH="/usr/local/AppCentral/$PKG"
STASH_DIR="/volume1/.$PKG-upgrade"
cd "$APKG_PATH" || exit 1

# Upgrade: restore what pre-install.sh stashed
RESTORED=0
if [ -d "$STASH_DIR/data" ]; then
    rm -rf data
    mv "$STASH_DIR/data" data && RESTORED=1
    if [ -f "$STASH_DIR/config.yaml" ]; then
        mkdir -p config
        cp "$STASH_DIR/config.yaml" config/config.yaml
    fi
    if [ -d "$STASH_DIR/venv" ]; then
        rm -rf venv
        mv "$STASH_DIR/venv" venv
    fi
    [ "$RESTORED" -eq 1 ] && rm -rf "$STASH_DIR"
fi

mkdir -p data
LOG_FILE="$APKG_PATH/data/install.log"
echo "=== Installing $PKG: $(date) ===" > "$LOG_FILE"
[ "$RESTORED" -eq 1 ] && echo "Data restored from $STASH_DIR" >> "$LOG_FILE"

export PATH="/opt/bin:/opt/sbin:$PATH"

# 1. Python 3.11 + pip + virtualenv from Entware (--force-space: bogus "0 kB free" on /opt)
if [ -x "/opt/bin/opkg" ]; then
    echo "[1/4] Checking Python in Entware..." >> "$LOG_FILE"
    if [ ! -x "/opt/bin/python3" ] || [ ! -x "/opt/bin/pip3" ]; then
        echo "Installing python3, pip, openssl and sqlite3 via opkg..." >> "$LOG_FILE"
        /opt/bin/opkg update >> "$LOG_FILE" 2>&1
        /opt/bin/opkg install --force-space python3 python3-pip python3-openssl python3-sqlite3 >> "$LOG_FILE" 2>&1
    fi
    if [ ! -x "/opt/bin/virtualenv" ] && [ -x "/opt/bin/pip3" ]; then
        echo "Installing virtualenv..." >> "$LOG_FILE"
        /opt/bin/pip3 install --no-cache-dir virtualenv >> "$LOG_FILE" 2>&1
    fi
fi

# 2. Pick Python >= 3.10
PYTHON_EXE=""
if [ -x "/opt/bin/python3" ]; then
    PYTHON_EXE="/opt/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)' 2>/dev/null)
    if [ -n "$PY_VER" ] && [ "$PY_VER" -ge 310 ]; then
        PYTHON_EXE="python3"
    fi
fi
if [ -z "$PYTHON_EXE" ]; then
    echo "ERROR: Python >= 3.10 not found." >> "$LOG_FILE"
    exit 1
fi
echo "[2/4] Python found: $PYTHON_EXE ($($PYTHON_EXE --version 2>&1))" >> "$LOG_FILE"

# 3. venv (kept across upgrades if it exists and works)
if [ ! -x "venv/bin/python" ]; then
    echo "[3/4] Creating virtual environment..." >> "$LOG_FILE"
    rm -rf venv
    if [ -x "/opt/bin/virtualenv" ]; then
        /opt/bin/virtualenv -p "$PYTHON_EXE" venv >> "$LOG_FILE" 2>&1
    else
        "$PYTHON_EXE" -m venv venv >> "$LOG_FILE" 2>&1
    fi
fi

# 4. Dependencies (pure Python / i686)
if [ -f "requirements.txt" ] && [ -x "venv/bin/pip" ]; then
    echo "[4/4] Installing dependencies..." >> "$LOG_FILE"
    ./venv/bin/pip install --upgrade pip >> "$LOG_FILE" 2>&1
    # Leftovers from Pydantic v2 break FastAPI < 0.100
    ./venv/bin/pip uninstall -y pydantic-settings pydantic-core >> "$LOG_FILE" 2>&1 || true
    ./venv/bin/pip install --no-cache-dir -r requirements.txt >> "$LOG_FILE" 2>&1

    # i686 wheels use the *.cpython-311-i386-linux-gnu.so suffix, which Entware's Python does not recognise
    for so in $(find venv/lib -name '*.cpython-*-linux-gnu.so'); do
        link="${so%.cpython-*-linux-gnu.so}.so"
        [ -e "$link" ] || ln -s "$(basename "$so")" "$link"
    done
    if ./venv/bin/python -c "from PIL import Image" >> "$LOG_FILE" 2>&1; then
        echo "Pillow OK" >> "$LOG_FILE"
    else
        echo "ERROR: Pillow does not load" >> "$LOG_FILE"
    fi
fi

chmod -R 755 data
echo "=== Installation finished: $(date) ===" >> "$LOG_FILE"
exit 0
