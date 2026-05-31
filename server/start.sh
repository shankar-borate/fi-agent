#!/usr/bin/env bash
# server/start.sh — Create venv, install requirements, start FastAPI server (Linux/Mac)
set -euo pipefail

cd "$(dirname "$0")"

echo "=== FI Agent Server (Linux) ==="

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install via: sudo apt-get install -y python3 python3-venv python3-pip"
  exit 1
fi
echo "Python: $(python3 --version)"

# ── Virtual environment ──────────────────────────────────────────────────
VENV=".venv"
if [ ! -f "$VENV/bin/python" ]; then
  echo ""
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
  echo "Done."
else
  echo "Virtual environment present — skipping creation"
fi

PIP="$VENV/bin/pip"
PYTHON="$VENV/bin/python"

# ── Install packages ────────────────────────────────────────────────────
echo ""
echo "Installing/updating packages from requirements.txt..."
"$PIP" install --upgrade pip --quiet
"$PIP" install -r requirements.txt
echo "Done."

# ── Start server ────────────────────────────────────────────────────────
echo ""
echo "Starting FastAPI server on http://0.0.0.0:8000 ..."
echo "Docs at http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""
"$PYTHON" main.py
