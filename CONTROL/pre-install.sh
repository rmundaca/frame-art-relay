#!/bin/sh
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

exit 0
