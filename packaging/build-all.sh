#!/bin/bash
# LoCo Agent - Build All Distributions
# Builds server, extension, and Android app

set -e

echo "========================================"
echo "LoCo Agent - Build All Distributions"
echo "========================================"
echo

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "ERROR: Unsupported OS for automated builds: $OSTYPE"
    echo "Please run individual build scripts on Windows"
    exit 1
fi

BUILD_SERVER=true
BUILD_EXTENSION=true
BUILD_ANDROID=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-only)
            BUILD_EXTENSION=false
            BUILD_ANDROID=false
            shift
            ;;
        --extension-only)
            BUILD_SERVER=false
            BUILD_ANDROID=false
            shift
            ;;
        --android-only)
            BUILD_SERVER=false
            BUILD_EXTENSION=false
            BUILD_ANDROID=true
            shift
            ;;
        --with-android)
            BUILD_ANDROID=true
            shift
            ;;
        --skip-server)
            BUILD_SERVER=false
            shift
            ;;
        --skip-extension)
            BUILD_EXTENSION=false
            shift
            ;;
        --help)
            echo "Usage: ./build-all.sh [OPTIONS]"
            echo
            echo "Options:"
            echo "  --server-only       Build only the server"
            echo "  --extension-only    Build only the VS Code extension"
            echo "  --android-only      Build only the Android app"
            echo "  --with-android      Include Android app in build"
            echo "  --skip-server       Skip server build"
            echo "  --skip-extension    Skip extension build"
            echo "  --help              Show this help message"
            echo
            echo "Default: Builds server and extension (not Android)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac
done

# Create releases directory
mkdir -p releases

# Build Server
if [ "$BUILD_SERVER" = true ]; then
    echo
    echo "========================================"
    echo "Building Server ($OS)"
    echo "========================================"
    echo
    
    if [ -f "build-server-linux.sh" ]; then
        ./build-server-linux.sh
    else
        echo "ERROR: build-server-linux.sh not found"
        exit 1
    fi
fi

# Build Extension
if [ "$BUILD_EXTENSION" = true ]; then
    echo
    echo "========================================"
    echo "Building VS Code Extension"
    echo "========================================"
    echo
    
    if [ -f "build-extension.sh" ]; then
        ./build-extension.sh
    else
        echo "ERROR: build-extension.sh not found"
        exit 1
    fi
fi

# Build Android
if [ "$BUILD_ANDROID" = true ]; then
    echo
    echo "========================================"
    echo "Building Android APK"
    echo "========================================"
    echo
    
    if [ -d "../LoCoAndroid" ]; then
        cd ../LoCoAndroid
        if [ -f "build-android-apk.sh" ]; then
            ./build-android-apk.sh
        else
            echo "ERROR: build-android-apk.sh not found in LoCoAndroid/"
            cd ..
            exit 1
        fi
        cd ..
    else
        echo "WARNING: LoCoAndroid directory not found. Skipping Android build."
    fi
fi

echo
echo "========================================"
echo "Build Complete!"
echo "========================================"
echo
echo "Distribution files created in releases/:"
echo

if [ "$BUILD_SERVER" = true ]; then
    if [ "$OS" == "linux" ]; then
        echo "  ✓ LoCoAgent-Server-Linux.run"
    else
        echo "  ✓ LoCoAgent-Server-macOS.tar.gz"
    fi
fi

if [ "$BUILD_EXTENSION" = true ]; then
    VSIX_FILE=$(ls releases/loco-agent-*.vsix 2>/dev/null | head -1)
    if [ -n "$VSIX_FILE" ]; then
        echo "  ✓ $(basename $VSIX_FILE)"
    fi
fi

if [ "$BUILD_ANDROID" = true ]; then
    APK_FILES=$(ls releases/LoCoAgent-*.apk 2>/dev/null)
    if [ -n "$APK_FILES" ]; then
        for apk in $APK_FILES; do
            echo "  ✓ $(basename $apk)"
        done
    fi
fi

echo
echo "All distributions ready for release!"
echo
