#!/bin/bash
# LoCo Agent VS Code Extension - Packaging Script
# Creates .vsix file for distribution

set -e

echo "================================"
echo "LoCo VS Code Extension - Build"
echo "================================"
echo

# Check if we're in the right directory
if [ ! -f "extension/package.json" ]; then
    echo "ERROR: Please run this script from the LoCo project root directory"
    echo "Expected structure: extension/package.json"
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

# Check for npm
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm is not installed"
    exit 1
fi

echo "[1/5] Installing dependencies..."
cd extension
npm install

echo "[2/5] Installing vsce (VS Code Extension Manager)..."
npm install -g @vscode/vsce --quiet

echo "[3/5] Running tests..."
npm test || echo "Warning: Tests failed or not configured"

echo "[4/5] Building extension..."
npm run compile

if [ ! -d "out" ]; then
    echo "ERROR: Build failed! 'out' directory not created."
    cd ..
    exit 1
fi

echo "[5/5] Packaging extension..."

# Update version if needed
VERSION=$(node -p "require('./package.json').version")
echo "Extension version: $VERSION"

# Package the extension
vsce package --out ../releases/

cd ..

VSIX_FILE="releases/loco-agent-${VERSION}.vsix"

if [ ! -f "$VSIX_FILE" ]; then
    echo "ERROR: Packaging failed! .vsix file not created."
    exit 1
fi

echo
echo "================================"
echo "Build Complete!"
echo "================================"
echo
echo "Extension package: $VSIX_FILE"
echo
echo "To install:"
echo "  1. Open VS Code"
echo "  2. Go to Extensions (Ctrl+Shift+X)"
echo "  3. Click '...' menu → 'Install from VSIX...'"
echo "  4. Select: $VSIX_FILE"
echo
echo "Or install via command line:"
echo "  code --install-extension $VSIX_FILE"
echo
echo "To publish to marketplace:"
echo "  vsce publish"
echo "  (Requires: https://marketplace.visualstudio.com publisher account)"
echo
