#!/bin/bash
# LoCo 3D-Gen Desktop - Tauri Packaging Script
# Creates installer bundles for distribution

set -e

echo "================================"
echo "LoCo 3D-Gen Desktop - Build"
echo "================================"
echo

# Check if we're in the right directory
if [ ! -f "modules/3d-gen-desktop/src-tauri/Cargo.toml" ]; then
    echo "ERROR: Please run this script from the LoCo project root directory"
    echo "Expected structure: modules/3d-gen-desktop/src-tauri/Cargo.toml"
    exit 1
fi

# Check for Cargo
if ! command -v cargo &> /dev/null; then
    if [ -x "$HOME/.cargo/bin/cargo" ]; then
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
fi
if ! command -v cargo &> /dev/null; then
    echo "ERROR: Rust/Cargo is not installed"
    echo "Please install Rust from https://www.rust-lang.org/tools/install"
    exit 1
fi

# Ensure a compatible Rust toolchain is available for building the Tauri CLI
TAURI_CLI_TOOLCHAIN="1.79.0"
if ! command -v rustup &> /dev/null; then
    echo "ERROR: rustup is required to install the Tauri toolchain"
    echo "Please install Rust from https://www.rust-lang.org/tools/install"
    exit 1
fi
if ! rustup toolchain list | grep -q "$TAURI_CLI_TOOLCHAIN"; then
    echo "Installing Rust toolchain $TAURI_CLI_TOOLCHAIN..."
    rustup toolchain install "$TAURI_CLI_TOOLCHAIN"
fi

# Check for Tauri CLI (v1.x required for this module)
TAURI_CMD=(cargo tauri)
TAURI_VERSION=$(cargo tauri --version 2>/dev/null | awk '{print $2}')
if [ -z "$TAURI_VERSION" ] || [ "${TAURI_VERSION%%.*}" != "1" ]; then
    LOCAL_TAURI_ROOT="$(pwd)/packaging/.tauri-cli"
    LOCAL_TAURI_BIN="$LOCAL_TAURI_ROOT/bin/cargo-tauri"
    if [ ! -x "$LOCAL_TAURI_BIN" ]; then
        echo "Installing tauri-cli 1.5.0..."
        cargo +"$TAURI_CLI_TOOLCHAIN" install tauri-cli --version 1.5.0 --locked --root "$LOCAL_TAURI_ROOT"
    fi
    export PATH="$LOCAL_TAURI_ROOT/bin:$PATH"
fi

echo "[1/2] Building Tauri bundles..."
pushd modules/3d-gen-desktop/src-tauri >/dev/null
cargo tauri build
popd >/dev/null

echo "[2/2] Collecting artifacts..."
mkdir -p out
BUNDLE_DIR="modules/3d-gen-desktop/src-tauri/target/release/bundle"
FOUND=0

for file in "$BUNDLE_DIR"/msi/*.msi; do
    if [ -f "$file" ]; then
        cp "$file" out/
        FOUND=1
    fi
done

for file in "$BUNDLE_DIR"/nsis/*.exe; do
    if [ -f "$file" ]; then
        cp "$file" out/
        FOUND=1
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "ERROR: No bundled artifacts found in $BUNDLE_DIR"
    exit 1
fi

echo
echo "================================"
echo "Build Complete!"
echo "================================"
echo
echo "Output folder: out"
echo
