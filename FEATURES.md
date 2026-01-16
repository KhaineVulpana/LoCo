# LoCo Agent - Feature Overview

This document provides a comprehensive overview of all features, both implemented and planned.
Legend: ✅ implemented, 🚧 partially implemented, ⏳ planned.

## ✅ Core Features (Implemented)

### 1. Server Foundation

**FastAPI-based Server**
- ✅ Health check endpoint
- ✅ WebSocket streaming protocol
- ✅ Optional bearer token auth toggle (default off)
- ✅ SQLite schema initialization (no migrations)
- ✅ Session management
- ✅ Workspace registration
- ✅ Workspace policy API (GET/PUT) + persistence
- ✅ Model manager + hot-swap endpoints
- ✅ Qdrant startup helper + Docker Compose support
- ✅ Knowledge + ACE REST endpoints

**Protocol**
- ✅ Client/Server handshake
- ✅ Message type system
- ✅ Context structure (files, diagnostics, git)
- ✅ Streaming responses (delta + final)
- ✅ Error handling

### 2. VS Code Extension

**Core UI**
- ✅ Custom sidebar with chat interface
- ✅ WebSocket client with reconnection
- ✅ Streaming message rendering
- ✅ Markdown support
- ✅ Message history
- ✅ Thinking indicators

**Context Gathering**
- ✅ Active editor (file, selection, visible range)
- ✅ Open editors
- ✅ Diagnostics (errors, warnings from all sources)
- ✅ Git status (branch, modified files, staged files)
- ✅ Automatic context on every message

**Diff Management**
- ✅ Patch tracking UI
- ✅ Accept/Reject actions
- ✅ View diff (side-by-side)
- ✅ Conflict detection before apply
- ✅ Undo stack for applied patches
- ✅ Inline diff decorations in editor
- ✅ Gutter indicators for proposed changes

**Settings**
- ✅ Server URL configuration
- ✅ Model provider selection
- ✅ Auto-context toggle
- ✅ Auth enabled toggle
- ✅ Auto workspace indexing + watcher toggles
- ✅ Workspace policy settings (globs, commands, network)

**Interaction**
- ✅ Slash commands (/fix, /explain, /test, /refactor, /review, /doc, /commit)
- ✅ @mention file picker with mention context injection

### 3. RAG + ACE
- ✅ Embedding manager (sentence-transformers)
- ✅ Qdrant vector store wrapper
- ✅ Knowledge indexer for docs + JSONL training data
- ✅ Retriever for knowledge + ACE bullets
- ✅ Workspace RAG toggle per request (`include_workspace_rag`)
- ✅ Incremental workspace indexing (file watcher, AST chunking, embedding cache)
- ✅ Hybrid workspace retrieval (vector + symbol + text)
- ✅ Ripgrep/regex workspace search (fallback to DB)
- ✅ Lightweight reranking + context pack builder with token budgets
- ✅ ACE playbook persistence in Qdrant
- ✅ ACE auto-learning loop (reflector/curator after interaction)
- ✅ Bullet feedback persistence + dedup/prune safeguards
- ✅ ACE metrics endpoint
- ✅ Module-scoped collections (`loco_rag_{module_id}`, `loco_ace_{module_id}`)
- ✅ 3d-gen training data loader

### 4. Modules
- ✅ VS Code extension module
- ✅ Android app module scaffold
- ✅ 3d-gen desktop module scaffold (Tauri + Three.js UI)

### 5. Tools
- ✅ read_file
- ✅ write_file
- ✅ list_files
- ✅ run_command
- ✅ run_tests
- ✅ apply_patch
- ✅ propose_patch
- ✅ propose_diff
- ✅ report_plan
- ✅ Tool/command approval workflow (request + response)
- ✅ Command policy enforcement (workspace policies)

## 🚧 Partially Implemented Features

### 1. Security + Audit
- 🚧 Audit log tables exist but are not populated yet
- 🚧 Token auth only enforced on WebSocket (HTTP endpoints open)

## ⏳ Planned Features (Not Yet Implemented)
- ⏳ (none listed)
