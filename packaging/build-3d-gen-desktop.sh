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
    echo "ERROR: Rust/Cargo is not installed"
    echo "Please install Rust from https://www.rust-lang.org/tools/install"
    exit 1
fi

# Check for Tauri CLI
if ! cargo tauri --version &> /dev/null; then
    echo "Installing tauri-cli..."
    cargo install tauri-cli --version 1.5.0
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
