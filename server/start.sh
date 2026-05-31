#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  ABC Bank FI Agent — Linux / macOS startup script
#
#  Usage:
#    ./start.sh            Production mode
#    ./start.sh dev        Development mode (auto-reload)
#    ./start.sh setup      Setup only, don't start server
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-}"
PORT=8000
VENV=".venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

# Colours
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'

step() { printf "  ${CYAN}[%-5s]${NC} %s\n" "$1" "$2"; }
ok()   { printf "  ${GREEN}[%-5s]${NC} %s\n" "$1" "$2"; }
warn() { printf "  ${YELLOW}[%-5s]${NC} %s\n" "WARN" "$1"; }
err()  { printf "  ${RED}[%-5s]${NC} %s\n"  "ERROR" "$1"; exit 1; }

echo ""
echo -e "  ${BLUE}================================================${NC}"
echo -e "  ${BLUE} ABC Bank FI Agent - Server${NC}"
echo -e "  ${BLUE}================================================${NC}"
echo ""

# ── 1. Python check ────────────────────────────────────────────────────────
PYTHON3=$(command -v python3 || command -v python || true)
[ -z "$PYTHON3" ] && err "Python 3.11+ not found. Install via: sudo apt install python3 python3-venv"
step "INFO" "$($PYTHON3 --version)"

# ── 2. Virtual environment ─────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    step "SETUP" "Creating virtual environment..."
    $PYTHON3 -m venv "$VENV"
    ok "SETUP" "Virtual environment created."
else
    step "INFO" "Virtual environment found."
fi

# ── 3. Install packages ────────────────────────────────────────────────────
step "SETUP" "Installing packages..."
"$PIP" install --upgrade pip --quiet
"$PIP" install -r requirements.txt --quiet
ok "SETUP" "Packages ready."

# ── 4. .env check ─────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo ""
    warn ".env file not found!"
    echo "         Create .env with:"
    cat << 'EOF'
          FI_AWS_ACCESS_KEY_ID=
          FI_AWS_SECRET_ACCESS_KEY=
          FI_AWS_REGION=ap-south-1
          FI_OPENAI_API_KEY=
          FI_GOOGLE_MAPS_API_KEY=
          FI_STORAGE_ROOT=/var/fi-agent/storage
EOF
    echo ""
else
    step "INFO" ".env found."
fi

# ── 5. Storage directory ───────────────────────────────────────────────────
STORAGE=$(grep -i "^FI_STORAGE_ROOT" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || true)
STORAGE="${STORAGE:-/var/fi-agent/storage}"
mkdir -p "$STORAGE"
step "INFO" "Storage: $STORAGE"

# ── 6. Web frontend ────────────────────────────────────────────────────────
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

# ── 7. Start ───────────────────────────────────────────────────────────────
echo ""
echo -e "  ${BLUE}------------------------------------------------${NC}"
echo -e "  ${BLUE} Starting server on port ${PORT}${NC}"
echo -e "  ${BLUE}------------------------------------------------${NC}"
echo    "   Customer App:   http://localhost:${PORT}/fi/"
echo    "   Auditor Portal: http://localhost:${PORT}/auditor/"
echo    "   Dashboard:      http://localhost:${PORT}/"
echo    "   API Docs:       http://localhost:${PORT}/docs"
echo    "   Health Check:   http://localhost:${PORT}/health"
echo -e "  ${BLUE}------------------------------------------------${NC}"
echo    "   Press Ctrl+C to stop"
echo ""

if [ "$MODE" = "dev" ]; then
    step "MODE" "Development (auto-reload enabled)"
    echo ""
    "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
else
    step "MODE" "Production"
    echo ""
    "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --workers 1
fi
