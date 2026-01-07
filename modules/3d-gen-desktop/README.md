# LoCo 3D-Gen Desktop (Tauri)

Desktop frontend for the 3D-Gen experience. This uses the same backend server
and sends `frontend_id: "3d-gen"` with every message so the correct RAG/ACE
collections are used.

## What this app does

- Chat on the left, 3D preview on the right.
- Listens for mesh JSON in assistant responses and renders it with Three.js.
- Connects to the existing FastAPI backend over WebSocket.

## Prereqs

- Rust toolchain
- Tauri CLI (`cargo install tauri-cli`)
- Backend server running (`backend/app/main.py`)

## Run (dev)

1. Start the backend server.
2. Open a terminal:

```bash
cd modules/3d-gen-desktop/src-tauri
cargo tauri dev
```

## Build (Windows)

```bash
cd modules/3d-gen-desktop/src-tauri
cargo tauri build
```

## App configuration

Fill in these fields in the UI:

- Server URL (default: `http://localhost:3199`)
- Workspace path (any local folder)
- Token (optional; only needed if you enforce auth)

## Mesh JSON format

The viewer looks for a JSON block in assistant output:

```json
{
  "mesh": {
    "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
    "triangles": [[0, 1, 2]],
    "normals": [[0, 0, 1], [0, 0, 1], [0, 0, 1]],
    "uvs": [[0, 0], [1, 0], [0, 1]]
  },
  "csharp_code": "..."
}
```

The renderer also accepts top-level `vertices`/`triangles` without a `mesh` wrapper.

## Android later

This uses Tauri for desktop. For Android later, keep this UI code and migrate
the shell to Tauri v2 mobile (or embed the UI in a native WebView).
