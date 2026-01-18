#!/bin/bash

# LoCo Agent Frontend Suite Startup Script
set -euo pipefail

MODE=${1:-web}
MODULE_DIR="modules/agent-ui"

if ! command -v node >/dev/null 2>&1; then
  echo "Error: Node.js not found. Please install Node.js 18+."
  exit 1
fi

if [ ! -d "$MODULE_DIR" ]; then
  echo "Error: $MODULE_DIR not found."
  exit 1
fi

cd "$MODULE_DIR"

if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

if [ "$MODE" = "desktop" ]; then
  if ! command -v cargo >/dev/null 2>&1; then
    echo "Error: Rust toolchain not found. Install Rust (https://www.rust-lang.org/tools/install)."
    exit 1
  fi
  echo "Starting desktop app (Tauri)..."
  cd src-tauri
  cargo tauri dev
  exit 0
fi

echo "Starting frontend dev server..."
echo "Open http://localhost:5173/app/"

npm run dev -- --host
