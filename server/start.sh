#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  ABC Bank FI Agent — Linux / macOS startup script
#
#  Usage:
#    ./start.sh            Production (foreground)
#    ./start.sh bg         Production (background — writes to fi-agent.log)
#    ./start.sh dev        Development mode (auto-reload, foreground)
#    ./start.sh stop       Stop background process
#    ./start.sh status     Show running status
#    ./start.sh setup      Setup only, don't start server
#    ./start.sh restart    Stop + start in background
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-}"
PORT=8000
VENV=".venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
PIDFILE="fi-agent.pid"
LOGFILE="fi-agent.log"

# Colours
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'

step() { printf "  ${CYAN}[%-5s]${NC} %s\n" "$1" "$2"; }
ok()   { printf "  ${GREEN}[%-5s]${NC} %s\n" "$1" "$2"; }
warn() { printf "  ${YELLOW}[%-5s]${NC} %s\n" "WARN" "$1"; }
err()  { printf "  ${RED}[%-5s]${NC} %s\n"  "ERROR" "$1"; exit 1; }

# ── stop helper ───────────────────────────────────────────────────────────────
do_stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PIDFILE"
            ok "STOP" "Server stopped (pid $PID)"
        else
            warn "Process $PID not running — removing stale pid file"
            rm -f "$PIDFILE"
        fi
    else
        warn "No pid file found — server may not be running"
    fi
}

# ── status helper ─────────────────────────────────────────────────────────────
do_status() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            ok "UP" "Server running — pid $PID  port $PORT"
            echo    "   Log:  $(pwd)/$LOGFILE"
            echo    "   Tail: tail -f $LOGFILE"
        else
            warn "Pid file exists but process $PID is not running"
        fi
    else
        warn "Server is not running (no pid file)"
    fi
}

# Handle stop/status/restart before the setup steps
case "$MODE" in
    stop)    do_stop;   exit 0 ;;
    status)  do_status; exit 0 ;;
    restart)
        do_stop 2>/dev/null || true
        sleep 1
        exec "$0" bg
        ;;
esac

echo ""
echo -e "  ${BLUE}================================================${NC}"
echo -e "  ${BLUE} ABC Bank FI Agent - Server${NC}"
echo -e "  ${BLUE}================================================${NC}"
echo ""

# ── 1. Python check ───────────────────────────────────────────────────────────
PYTHON3=$(command -v python3 || command -v python || true)
[ -z "$PYTHON3" ] && err "Python 3.11+ not found. Install via: sudo apt install python3 python3-venv"
step "INFO" "$($PYTHON3 --version)"

# ── 2. Virtual environment ────────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    step "SETUP" "Creating virtual environment..."
    $PYTHON3 -m venv "$VENV"
    ok "SETUP" "Virtual environment created."
else
    step "INFO" "Virtual environment found."
fi

# ── 3. Install packages ───────────────────────────────────────────────────────
step "SETUP" "Installing packages..."
"$PIP" install --upgrade pip --quiet
"$PIP" install -r requirements.txt --quiet
ok "SETUP" "Packages ready."

# ── 4. .env check ─────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo ""
    warn ".env file not found!"
    echo "         Create .env with:"
    cat << 'ENVEOF'
          FI_AWS_ACCESS_KEY_ID=
          FI_AWS_SECRET_ACCESS_KEY=
          FI_AWS_REGION=ap-south-1
          FI_OPENAI_API_KEY=
          FI_GOOGLE_MAPS_API_KEY=
          FI_STORAGE_ROOT=/var/fi-agent/storage
ENVEOF
    echo ""
else
    step "INFO" ".env found."
fi

# ── 5. Storage directory ──────────────────────────────────────────────────────
STORAGE=$(grep -i "^FI_STORAGE_ROOT" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || true)
STORAGE="${STORAGE:-/var/fi-agent/storage}"
mkdir -p "$STORAGE"
step "INFO" "Storage: $STORAGE"

# ── 6. Web frontend ───────────────────────────────────────────────────────────
if [ ! -f "../web/dist/index.html" ]; then
    step "SETUP" "Web frontend not built — building now..."
    if command -v npm &>/dev/null; then
        pushd ../web > /dev/null
        npm install --silent 2>/dev/null || true
        if npm run build 2>/dev/null; then
            ok "SETUP" "Web frontend built."
        else
            warn "Web build failed. Run: cd ../web && npm run build"
        fi
        popd > /dev/null
    else
        warn "npm not found. Run manually: cd ../web && npm run build"
    fi
else
    step "INFO" "Web frontend ready."
fi

[ "$MODE" = "setup" ] && { echo ""; ok "DONE" "Setup complete. Run ./start.sh to launch."; exit 0; }

# ── 7. Start ──────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${BLUE}------------------------------------------------${NC}"
echo -e "  ${BLUE} Starting server on port ${PORT}${NC}"
echo -e "  ${BLUE}------------------------------------------------${NC}"
echo    "   Customer App:    http://localhost:${PORT}/fi/"
echo    "   Auditor Portal:  http://localhost:${PORT}/fi/auditor/"
echo    "   API Docs:        http://localhost:${PORT}/fi/docs"
echo    "   Health Check:    http://localhost:${PORT}/fi/health"
echo -e "  ${BLUE}------------------------------------------------${NC}"

if [ "$MODE" = "dev" ]; then
    echo "   Press Ctrl+C to stop"
    echo ""
    step "MODE" "Development (auto-reload, foreground)"
    "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload

elif [ "$MODE" = "bg" ]; then
    # ── Background mode ───────────────────────────────────────────────────
    # Kill any existing instance first
    if [ -f "$PIDFILE" ]; then
        OLD_PID=$(cat "$PIDFILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            step "INFO" "Stopping existing process (pid $OLD_PID)..."
            kill "$OLD_PID" && sleep 1
        fi
        rm -f "$PIDFILE"
    fi

    step "MODE" "Production background — log: $(pwd)/$LOGFILE"
    nohup "$PYTHON" -m uvicorn main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --workers 1 \
        >> "$LOGFILE" 2>&1 &

    BG_PID=$!
    disown "$BG_PID"          # detach from shell — survives console close
    echo "$BG_PID" > "$PIDFILE"
    sleep 1   # give uvicorn a moment to start

    if kill -0 "$BG_PID" 2>/dev/null; then
        ok "START" "Server started in background — pid $BG_PID"
        echo ""
        echo    "   Log file:  $(pwd)/$LOGFILE"
        echo    "   Tail logs: tail -f $LOGFILE"
        echo    "   Stop:      ./start.sh stop"
        echo    "   Status:    ./start.sh status"
        echo    "   Restart:   ./start.sh restart"
    else
        err "Server failed to start — check $LOGFILE"
    fi

else
    # ── Foreground production (default) ──────────────────────────────────
    echo "   Press Ctrl+C to stop"
    echo ""
    step "MODE" "Production (foreground)"
    "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --workers 1
fi
