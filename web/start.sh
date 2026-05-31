#!/usr/bin/env bash
# web/start.sh — Install npm packages and start the Vite dev server (Linux/Mac)
set -euo pipefail

cd "$(dirname "$0")"

echo "=== FI Agent Web (Linux) ==="

if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install via: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
  exit 1
fi
echo "Node  : $(node --version)"
echo "npm   : $(npm --version)"

if [ ! -d "node_modules" ]; then
  echo ""
  echo "Installing npm packages..."
  npm install
  echo "Done."
else
  echo "node_modules present — skipping install"
fi

echo ""
echo "Starting Vite dev server on http://localhost:5173 ..."
echo "Press Ctrl+C to stop"
echo ""
npm run dev
