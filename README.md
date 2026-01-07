# LoCo Agent - Complete Project

A **local-first, LAN-served coding agent** with VS Code extension, Android app, and comprehensive packaging scripts.

## 📦 Project Structure

```
LoCoProject/
- backend/             # FastAPI backend server
- modules/             # Frontend modules
  - vscode-extension/  # VS Code extension
  - android-app/       # Android mobile app
  - 3d-gen-desktop/    # Tauri desktop app
- packaging/           # Build scripts for distribution
- docs/                # Documentation
- schemas/             # API schemas
- README.md            # This file
```


## 🚀 Quick Start

### 1. Server Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Server: `http://localhost:3199`

### 2. VS Code Extension

```bash
cd modules/vscode-extension
npm install
npm run compile
# Press F5 in VS Code to launch
```

### 3. Android App

```bash
cd modules/android-app
# Open in Android Studio or:
./gradlew assembleDebug
```

## 🔨 Building for Distribution

See `packaging/README.md` for complete build instructions.

**Quick build**:
```bash
cd packaging

# Server installer
./build-server-linux.sh      # Linux/macOS
build-server-windows.bat     # Windows

# Extension package
./build-extension.sh

# Android APK
./build-android-apk.sh

# Build everything
./build-all.sh
```

## 📱 Components

### Server
- WebSocket streaming
- Agentic RAG + ACE
- Multi-file editing
- Workspace management

### Extension
- Chat sidebar
- Inline diffs
- @ mentions, slash commands
- Context gathering

### Android
- Five-panel swipeable UI
- Terminal (swipe up)
- Settings (swipe down)
- Foldable device support

## 📚 Documentation

- Server API: `http://localhost:3199/docs`
- Extension: `modules/vscode-extension/README.md`
- Android: `modules/android-app/README.md`
- 3D-Gen Desktop: `modules/3d-gen-desktop/README.md`
- Packaging: `packaging/README.md`

## 🔧 Prerequisites

- Python 3.10+
- Node.js 18+
- Java 17+ (for Android)
- Ollama or other LLM
- Docker (for Qdrant)

## 📄 License

[Your License]
