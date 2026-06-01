#!/usr/bin/env bash
# web/start.sh — Vite dev server (Linux/macOS)
#
#  Usage:
#    ./start.sh            Dev server (foreground)
#    ./start.sh bg         Dev server (background — survives console close)
#    ./start.sh stop       Stop background process
#    ./start.sh status     Show running status
#    ./start.sh restart    Stop + start in background
set -euo pipefail

cd "$(dirname "$0")"

MODE="${1:-}"
PIDFILE="vite.pid"
LOGFILE="vite.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'

ok()   { printf "  ${GREEN}[%-5s]${NC} %s\n" "$1" "$2"; }
warn() { printf "  ${YELLOW}[%-5s]${NC} %s\n" "WARN" "$1"; }
err()  { printf "  ${RED}[%-5s]${NC} %s\n"  "ERROR" "$1"; exit 1; }

do_stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PIDFILE"
            ok "STOP" "Dev server stopped (pid $PID)"
        else
            warn "Process $PID not running — removing stale pid file"
            rm -f "$PIDFILE"
        fi
    else
        warn "No pid file found — server may not be running"
    fi
}

do_status() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            ok "UP" "Dev server running — pid $PID  port 5173"
            echo "   Log:  $(pwd)/$LOGFILE"
            echo "   Tail: tail -f $LOGFILE"
        else
            warn "Pid file exists but process $PID is not running"
        fi
    else
        warn "Dev server is not running (no pid file)"
    fi
}

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
echo -e "  ${BLUE} FI Agent — Web Dev Server${NC}"
echo -e "  ${BLUE}================================================${NC}"
echo ""

if ! command -v node &>/dev/null; then
    err "Node.js not found. Install via: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
fi
echo "   Node : $(node --version)"
echo "   npm  : $(npm --version)"

if [ ! -d "node_modules" ]; then
    echo ""
    echo "   Installing npm packages..."
    npm install
fi

if [ "$MODE" = "bg" ]; then
    # Kill any existing instance first
    if [ -f "$PIDFILE" ]; then
        OLD_PID=$(cat "$PIDFILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "   Stopping existing process (pid $OLD_PID)..."
            kill "$OLD_PID" && sleep 1
        fi
        rm -f "$PIDFILE"
    fi

    echo ""
    ok "MODE" "Background — log: $(pwd)/$LOGFILE"
    nohup npm run dev >> "$LOGFILE" 2>&1 &
    BG_PID=$!
    disown "$BG_PID"          # detach from shell — survives console close
    echo "$BG_PID" > "$PIDFILE"
    sleep 2   # give Vite a moment to start

    if kill -0 "$BG_PID" 2>/dev/null; then
        ok "START" "Dev server started in background — pid $BG_PID"
        echo ""
        echo "   URL:       http://localhost:5173"
        echo "   Log file:  $(pwd)/$LOGFILE"
        echo "   Tail logs: tail -f $LOGFILE"
        echo "   Stop:      ./start.sh stop"
        echo "   Status:    ./start.sh status"
    else
        err "Dev server failed to start — check $LOGFILE"
    fi

else
    echo ""
    echo "   URL: http://localhost:5173"
    echo "   Press Ctrl+C to stop"
    echo ""
    ok "MODE" "Foreground"
    npm run dev
fi
