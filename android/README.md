# LoCo Agent Android App

Android client for LoCo Agent - a local-first coding assistant with advanced UI for foldable devices.

## Features

### Advanced Multi-Panel Interface

- **Five-Panel System**:
  - **Left Panel**: Workspace browser with file tree (swipe right)
  - **Center Panel**: Chat interface with AI assistant (default view)
  - **Right Panel**: Code editor (swipe left)
  - **Bottom Panel**: Terminal (swipe up from bottom, 40% screen height)
  - **Top Panel**: Settings (swipe down from top, full screen)

### Foldable Device Support (OnePlus Open)

When unfolded:
- **Dual-screen layout** - panels slide to opposite sides
- Left drawer opens on left half of screen
- Right drawer opens on right half of screen
- Chat panel stays centered between active panels
- Terminal and settings work identically across all states

When folded:
- Standard single-screen behavior
- Panels slide over the chat view

### Gestures

- **Horizontal Swipes**:
  - Swipe right → Open workspace/files
  - Swipe left → Open code editor
  - Swipe back → Return to chat

- **Vertical Swipes**:
  - Swipe up from bottom 20% → Open terminal (40% height)
  - Swipe down from top 20% → Open settings (full screen)
  - Swipe in opposite direction → Close overlay

### Terminal Features

- Execute commands (mock implementation)
- Scrollable command history
- Monospace font display
- Command/output differentiation
- Clear terminal option
- 40% screen height overlay
- Accessible from any view

### Settings Features

- Server URL configuration
- Auto-connect on startup
- Dark mode toggle
- Editor font size (10-24sp)
- Terminal font size (10-24sp)
- App version information
- Clear all data option
- Full-screen overlay

## Quick Start

1. Update server URL in Settings (swipe down from top)
2. Chat interface loads automatically
3. Swipe to access workspace, code editor, or terminal
4. All panels have quick-access buttons in headers

## Architecture

- **MVVM** with ViewModel and StateFlow
- **Hilt** dependency injection
- **Retrofit** + **OkHttp WebSocket**
- **Jetpack Compose** UI
- **Window Library** for foldables

## Dual-Screen Behavior

Screen width ≥600dp triggers dual-screen mode:
- Panels use 50% screen width
- Chat centers between active panels
- Smooth side-by-side transitions
- Terminal and Settings overlay both

Standard mode (width <600dp):
- Panels use 80% screen width
- Standard overlay behavior

## License

Same as LoCo Agent project
