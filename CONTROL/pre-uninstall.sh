#!/bin/sh
PKG="frame-art"
APKG_PATH="/usr/local/AppCentral/$PKG"

if [ -f "$APKG_PATH/CONTROL/start-stop.sh" ]; then
    "$APKG_PATH/CONTROL/start-stop.sh" stop
fi

# Respaldo de la base de datos antes de que ADM borre el directorio
if [ -f "$APKG_PATH/data/app.db" ]; then
    BACKUP_DIR="/volume1/home/$PKG-backup"
    mkdir -p "$BACKUP_DIR"
    cp "$APKG_PATH/data/app.db" "$BACKUP_DIR/app.db.bak"
    echo "Base de datos respaldada en $BACKUP_DIR/app.db.bak"
fi

exit 0
