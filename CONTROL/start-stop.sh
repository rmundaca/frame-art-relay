#!/bin/sh
PKG="frame-art"
PORT=8092

export PATH="/opt/bin:/opt/sbin:$PATH"

APKG_PATH="/usr/local/AppCentral/$PKG"
PID_FILE="/var/run/$PKG.pid"
LOG_FILE="$APKG_PATH/data/app.log"
PYTHON_BIN="$APKG_PATH/venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
    if [ -x "/opt/bin/python3" ]; then
        PYTHON_BIN="/opt/bin/python3"
    else
        PYTHON_BIN="python3"
    fi
fi

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start() {
    echo "Starting $PKG..."
    if is_running; then
        echo "$PKG is already running."
        return 0
    fi
    cd "$APKG_PATH" || exit 1
    mkdir -p data

    # Minimal log rotation: keep a single previous log once it exceeds 5 MB
    if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 5242880 ]; then
        mv -f "$LOG_FILE" "$LOG_FILE.1"
    fi

    # Single worker and no access log: minimal RAM and idle disks
    nohup "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
        --workers 1 --no-access-log >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "$PKG started with PID $(cat "$PID_FILE")."
}

stop() {
    echo "Stopping $PKG..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill -15 "$PID"
            sleep 2
            kill -0 "$PID" 2>/dev/null && kill -9 "$PID"
        fi
        rm -f "$PID_FILE"
        echo "$PKG stopped."
    else
        echo "PID file not found. Process may not be running."
    fi
}

status() {
    if is_running; then
        echo "$PKG is running (PID: $(cat "$PID_FILE"))."
        exit 0
    fi
    echo "$PKG is stopped."
    exit 1
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 1; start ;;
    status) status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
