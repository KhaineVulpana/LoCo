# LoCo Agent - Complete Project

A **local-first, LAN-served coding agent** with VS Code extension, Android app, and comprehensive packaging scripts.

## 📦 Project Structure

```
LoCoProject/
├── server/              # FastAPI backend server
├── extension/           # VS Code extension
├── android/             # Android mobile app
├── packaging/           # Build scripts for distribution
├── docs/                # Documentation
├── schemas/             # API schemas
└── README.md           # This file
```

## 🚀 Quick Start

### 1. Server Setup

```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Server: `http://localhost:3199`

### 2. VS Code Extension

```bash
cd extension
npm install
npm run compile
# Press F5 in VS Code to launch
```

### 3. Android App

```bash
cd android
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
- Extension: `extension/README.md`
- Android: `android/README.md`
- Packaging: `packaging/README.md`

## 🔧 Prerequisites

- Python 3.10+
- Node.js 18+
- Java 17+ (for Android)
- Ollama or other LLM
- Docker (for Qdrant)

## 📄 License

[Your License]
