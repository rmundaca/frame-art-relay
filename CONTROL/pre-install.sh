#!/bin/sh
PKG="frame-art"
APKG_PATH="/usr/local/AppCentral/$PKG"
STASH_DIR="/volume1/.$PKG-upgrade"

# Requiere Python >= 3.10. En el AS-202TE el Python de ADM es 3.7: hace falta Entware (App Central).

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
    echo "ERROR: esta aplicación requiere Python 3.10 o superior."
    echo "Instala 'Entware' desde App Central y vuelve a intentarlo."
    echo "=================================================================="
    exit 1
fi

# Actualización: ADM borra la carpeta de la app entera, así que se apartan los datos (BD, tokens,
# cachés), el override de configuración y el venv; post-install.sh los devuelve.
if [ -d "$APKG_PATH/data" ]; then
    if [ -f "$APKG_PATH/CONTROL/start-stop.sh" ]; then
        "$APKG_PATH/CONTROL/start-stop.sh" stop  # cierra la BD (checkpoint del WAL) antes de moverla
    fi
    rm -rf "$STASH_DIR"
    mkdir -p "$STASH_DIR"
    mv "$APKG_PATH/data" "$STASH_DIR/data" || exit 1
    [ -f "$APKG_PATH/config/config.yaml" ] && cp "$APKG_PATH/config/config.yaml" "$STASH_DIR/config.yaml"
    [ -d "$APKG_PATH/venv" ] && mv "$APKG_PATH/venv" "$STASH_DIR/venv"
    echo "Datos apartados en $STASH_DIR"
fi

exit 0
