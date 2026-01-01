#!/bin/bash
# LoCo Agent Android App - APK Build Script
# Creates signed APK for distribution

set -e

echo "================================"
echo "LoCo Android App - Build APK"
echo "================================"
echo

# Check if we're in the Android project directory
if [ ! -f "app/build.gradle.kts" ]; then
    echo "ERROR: Please run this script from the Android project root directory"
    echo "Expected structure: app/build.gradle.kts"
    exit 1
fi

# Check for Java
if ! command -v java &> /dev/null; then
    echo "ERROR: Java is not installed"
    echo "Please install Java 17 from https://adoptium.net/"
    exit 1
fi

# Detect build type
BUILD_TYPE="release"
SIGN_APK=false

echo "Build Options:"
echo "1. Debug APK (unsigned, for testing)"
echo "2. Release APK (requires keystore for signing)"
echo
read -p "Select build type [1-2]: " choice

case $choice in
    1)
        BUILD_TYPE="debug"
        SIGN_APK=false
        ;;
    2)
        BUILD_TYPE="release"
        SIGN_APK=true
        ;;
    *)
        echo "Invalid choice. Building debug APK..."
        BUILD_TYPE="debug"
        SIGN_APK=false
        ;;
esac

echo
echo "Building $BUILD_TYPE APK..."
echo

# Make gradlew executable
chmod +x gradlew

if [ "$SIGN_APK" = true ]; then
    echo "[1/5] Checking for keystore..."
    
    KEYSTORE_FILE="keystore/loco-release.keystore"
    KEYSTORE_PROPERTIES="keystore.properties"
    
    if [ ! -f "$KEYSTORE_FILE" ]; then
        echo "No keystore found. Creating new keystore..."
        mkdir -p keystore
        
        read -p "Enter keystore password: " -s KEYSTORE_PASSWORD
        echo
        read -p "Enter key alias: " KEY_ALIAS
        read -p "Enter key password: " -s KEY_PASSWORD
        echo
        
        keytool -genkeypair -v \
            -keystore "$KEYSTORE_FILE" \
            -alias "$KEY_ALIAS" \
            -keyalg RSA \
            -keysize 2048 \
            -validity 10000 \
            -storepass "$KEYSTORE_PASSWORD" \
            -keypass "$KEY_PASSWORD"
        
        # Create keystore.properties
        cat > "$KEYSTORE_PROPERTIES" << EOF
storePassword=$KEYSTORE_PASSWORD
keyPassword=$KEY_PASSWORD
keyAlias=$KEY_ALIAS
storeFile=../keystore/loco-release.keystore
EOF
        
        echo "Keystore created at $KEYSTORE_FILE"
        echo "IMPORTANT: Keep this file and password secure!"
    else
        if [ ! -f "$KEYSTORE_PROPERTIES" ]; then
            echo "ERROR: Keystore found but keystore.properties is missing"
            echo "Please create keystore.properties with:"
            echo "  storePassword=<password>"
            echo "  keyPassword=<password>"
            echo "  keyAlias=<alias>"
            echo "  storeFile=../keystore/loco-release.keystore"
            exit 1
        fi
        echo "Using existing keystore: $KEYSTORE_FILE"
    fi
    
    echo "[2/5] Cleaning previous builds..."
    ./gradlew clean
    
    echo "[3/5] Running lint checks..."
    ./gradlew lintRelease || echo "Warning: Lint issues found"
    
    echo "[4/5] Building signed release APK..."
    ./gradlew assembleRelease
    
    APK_PATH="app/build/outputs/apk/release/app-release.apk"
    
else
    echo "[1/3] Cleaning previous builds..."
    ./gradlew clean
    
    echo "[2/3] Building debug APK..."
    ./gradlew assembleDebug
    
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
fi

if [ ! -f "$APK_PATH" ]; then
    echo "ERROR: Build failed! APK not created."
    exit 1
fi

echo "[Final] Preparing distribution..."

# Create releases directory
mkdir -p releases

# Get version from build.gradle.kts
VERSION=$(grep -m 1 "versionName" app/build.gradle.kts | sed 's/.*"\(.*\)".*/\1/')

if [ "$BUILD_TYPE" == "release" ]; then
    OUTPUT_FILE="releases/LoCoAgent-${VERSION}-release.apk"
    
    # Sign the APK
    echo "Signing APK..."
    # The APK should already be signed by Gradle if keystore.properties exists
    cp "$APK_PATH" "$OUTPUT_FILE"
    
    # Verify signature
    echo "Verifying signature..."
    jarsigner -verify -verbose -certs "$OUTPUT_FILE" || echo "Warning: Signature verification had issues"
    
else
    OUTPUT_FILE="releases/LoCoAgent-${VERSION}-debug.apk"
    cp "$APK_PATH" "$OUTPUT_FILE"
fi

# Get APK info
APK_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')

echo
echo "================================"
echo "Build Complete!"
echo "================================"
echo
echo "APK: $OUTPUT_FILE"
echo "Size: $APK_SIZE"
echo "Version: $VERSION"
echo "Build Type: $BUILD_TYPE"
echo

if [ "$BUILD_TYPE" == "release" ]; then
    echo "This is a SIGNED RELEASE APK ready for distribution."
    echo
    echo "To install on device:"
    echo "  adb install -r $OUTPUT_FILE"
    echo
    echo "Or transfer to device and install manually."
    echo
    echo "IMPORTANT: Keep your keystore safe! You'll need it for updates."
else
    echo "This is a DEBUG APK for testing only."
    echo
    echo "To install on device:"
    echo "  adb install -r $OUTPUT_FILE"
    echo
    echo "For production release, run this script and select option 2."
fi

echo
echo "APK Location: $OUTPUT_FILE"
echo
