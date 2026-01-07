# LoCo Agent - Distribution Packaging Scripts

This directory contains scripts to package each component of LoCo Agent for distribution.

## Overview

- **Server**: Windows installer (.exe), Linux/macOS self-extracting installer
- **VS Code Extension**: VSIX package for VS Code marketplace
- **Android App**: Signed APK for distribution

## Prerequisites

### All Platforms
- Git (for version management)

### Server Packaging

**Windows**:
- Python 3.10+ (https://www.python.org/)
- PyInstaller (installed by script)
- Inno Setup 6 (https://jrsoftware.org/isdl.php)

**Linux/macOS**:
- Python 3.10+
- PyInstaller (installed by script)
- tar/gzip (usually pre-installed)

### Extension Packaging

**All Platforms**:
- Node.js 18+ (https://nodejs.org/)
- npm (comes with Node.js)
- vsce (installed by script)

### Android Packaging

**All Platforms**:
- Java 17+ (https://adoptium.net/)
- Android SDK (via Android Studio)
- Gradle (included in project)

## Usage

### 1. Server Packaging

#### Windows Installer

```bash
# From LoCo project root
build-server-windows.bat
```

**Output**: `releases/LoCoAgent-Server-Setup.exe`

**What it does**:
1. Builds standalone executable with PyInstaller
2. Creates Inno Setup installer script
3. Compiles full Windows installer
4. Installer will:
   - Install to Program Files
   - Create AppData directory for database/config
   - Add Start Menu shortcuts
   - Optionally install as Windows Service
   - Set up automatic updates

**Installation locations**:
- Program: `C:\Program Files\LoCo Agent Server\`
- Data: `C:\ProgramData\LoCoAgent\`
- Config: `%APPDATA%\LoCoAgent\.env`

#### Linux/macOS Installer

```bash
# From LoCo project root
chmod +x build-server-linux.sh
./build-server-linux.sh
```

**Output**: 
- Linux: `releases/LoCoAgent-Server-Linux.run` (self-extracting)
- macOS: `releases/LoCoAgent-Server-macOS.tar.gz`

**What it does**:
1. Builds standalone executable with PyInstaller
2. Creates installer package with scripts
3. Includes systemd service file (Linux)
4. Self-extracting installer that:
   - Installs to `/opt/loco-agent` or `~/.local/share/loco-agent`
   - Creates config directory at `~/.config/loco-agent`
   - Sets up systemd service
   - Adds `loco-agent` command to PATH

**Installation**:
```bash
# Linux
./LoCoAgent-Server-Linux.run

# macOS
tar xzf LoCoAgent-Server-macOS.tar.gz
cd loco-agent-installer
./install.sh
```

### 2. VS Code Extension Packaging

#### All Platforms

```bash
# From LoCo project root

# Linux/macOS:
chmod +x build-extension.sh
./build-extension.sh

# Windows:
build-extension.bat
```

**Output**: `releases/loco-agent-<version>.vsix`

**What it does**:
1. Installs npm dependencies
2. Runs TypeScript compilation
3. Runs tests
4. Packages as VSIX file

**Installation**:
```bash
# Via command line
code --install-extension releases/loco-agent-<version>.vsix

# Or via VS Code UI:
# Extensions → ... menu → Install from VSIX
```

**Publishing to Marketplace**:
```bash
cd modules/vscode-extension
vsce publish
# Requires publisher account: https://marketplace.visualstudio.com/
```

### 3. Android APK Packaging

#### All Platforms

```bash
# From repo root:
cd modules/android-app

# Linux/macOS:
chmod +x ../../packaging/build-android-apk.sh
../../packaging/build-android-apk.sh

# Windows:
..\..\packaging\build-android-apk.bat
```

**Build Options**:
1. **Debug APK**: Unsigned, for testing only
2. **Release APK**: Signed with keystore, ready for distribution

**Output**: `releases/LoCoAgent-<version>-<debug|release>.apk`

**What it does**:

For **Debug** build:
1. Cleans previous builds
2. Builds unsigned debug APK
3. Copies to releases directory

For **Release** build:
1. Checks for/creates keystore
2. Cleans previous builds  
3. Runs lint checks
4. Builds signed release APK
5. Verifies signature
6. Copies to releases directory

**Keystore Management**:
- First run creates new keystore at `keystore/loco-release.keystore`
- Creates `keystore.properties` with credentials
- **CRITICAL**: Keep keystore file and passwords secure!
- You need the same keystore to publish app updates

**Installation on Device**:
```bash
# Via ADB
adb install -r releases/LoCoAgent-<version>-release.apk

# Or transfer APK to device and install manually
# Settings → Security → Unknown Sources (enable)
```

## Directory Structure After Building

```
LoCo/
├── releases/
│   ├── LoCoAgent-Server-Setup.exe          # Windows installer
│   ├── LoCoAgent-Server-Linux.run          # Linux installer
│   ├── LoCoAgent-Server-macOS.tar.gz       # macOS package
│   ├── loco-agent-<version>.vsix           # VS Code extension
│   ├── LoCoAgent-<version>-debug.apk       # Android debug
│   └── LoCoAgent-<version>-release.apk     # Android release
├── installer_build/                         # Temp files (server)
├── backend/dist/                            # PyInstaller output
└── keystore/                               # Android signing keys
    └── loco-release.keystore               # KEEP SECURE!
```

## Build All Script

For convenience, you can create a master build script:

```bash
#!/bin/bash
# build-all.sh - Build all distributions

echo "Building all LoCo Agent distributions..."

# Server
./build-server-linux.sh

# Extension
./build-extension.sh

# Android
cd modules/android-app
../../packaging/build-android-apk.sh
cd ../..

echo "All builds complete! Check releases/ directory"
```

## Version Management

Update versions in:
- Server: `backend/app/core/config.py` → `VERSION`
- Extension: `modules/vscode-extension/package.json` → `version`
- Android: `modules/android-app/app/build.gradle.kts` → `versionName` and `versionCode`

## Distribution Checklist

Before releasing:

### Server
- [ ] Test on clean Windows/Linux/macOS install
- [ ] Verify database creation
- [ ] Check Qdrant connection
- [ ] Test with different LLM providers
- [ ] Verify service installation
- [ ] Test uninstaller

### Extension
- [ ] Test in VS Code
- [ ] Verify server connection
- [ ] Test all commands (@-mentions, slash commands)
- [ ] Check chat functionality
- [ ] Test file editing features
- [ ] Verify settings

### Android
- [ ] Test on multiple devices
- [ ] Verify all gestures (swipe left/right/up/down)
- [ ] Test foldable device support
- [ ] Check server connection
- [ ] Test terminal functionality
- [ ] Verify settings persistence
- [ ] Test on different Android versions (min SDK 26)

## Security Notes

### Keystore (Android)
- **Never commit keystore to Git**
- **Never share keystore file or passwords**
- **Backup keystore in secure location**
- You cannot update your app without the original keystore

### Signing Certificates
- Consider using CI/CD for automated signing
- Use environment variables for sensitive data
- Rotate certificates periodically

## Troubleshooting

### Server Build Issues

**PyInstaller missing modules**:
Add to `--hidden-import` list in build script

**Database path issues**:
Ensure `{app}` or `{data_dir}` placeholders are replaced correctly

### Extension Build Issues

**vsce command not found**:
```bash
npm install -g @vscode/vsce
```

**TypeScript errors**:
```bash
npm install
npm run compile
```

### Android Build Issues

**Gradle daemon issues**:
```bash
./gradlew --stop
./gradlew clean
```

**Signing errors**:
Verify `keystore.properties` exists and has correct paths

**Build fails**:
Check `app/build/outputs/logs/` for details

## CI/CD Integration

These scripts can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Build Server (Linux)
  run: ./build-server-linux.sh

- name: Build Extension
  run: ./build-extension.sh

- name: Build Android APK
  run: cd modules/android-app && ../../packaging/build-android-apk.sh
```

## Support

For issues with packaging:
1. Check script output for specific errors
2. Verify all prerequisites are installed
3. Ensure you're in correct directory
4. Check logs in respective build directories

## License

Same as LoCo Agent project
