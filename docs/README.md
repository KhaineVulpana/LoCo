# LoCo Agent Local (Repo-Ready Spec)

A **local-first, LAN-served coding agent** with a **feature-rich VS Code extension**, designed to operate **identically to Claude Code and GitHub Codex**: dedicated chat sidebar, inline diffs, multi-file editing, @ mentions, slash commands, automatic context gathering, iterative "fix → run → verify" loops, plus **Agentic RAG** and **Agentic Context Engineering (ACE)**.

> This repository is a **spec + scaffolding**: stable interfaces, schemas, folder structure, and "contract-first" modules.  
> It is intentionally implementation-light so you can swap models/vector stores/tool runners without refactoring the whole product.

## Key design choices (optimized for Codex-like UX)
- **VS Code extension in TypeScript** with deep VS Code API integration: Custom Sidebar with chat UI, TreeView for file changes, native diff viewer, file decorations, terminal integration, git status tracking, automatic context capture, and @ mention file/symbol picker.
- **Agent Server in Python (FastAPI)** to keep ML/embedding/ranking/tooling pipelines simple and replaceable.
- **Model backends are pluggable** (Ollama/vLLM/llama.cpp/OpenAI-compatible local servers) via adapters.
- **Vector store is pluggable** with a strong default of **Qdrant** for robust filtering and operational maturity.
- **Metadata persistence** via SQLite (sessions, policies, audit logs, ACE artifacts) with schema migrations.

## Project layout
- `modules/vscode-extension/` — VS Code extension (rich client with deep IDE integration)
  - `src/sidebar/` — Custom sidebar panel (chat UI, file changes tree)
  - `src/diff/` — Inline diff handling and native diff viewer integration
  - `src/context/` — Automatic context gathering (selection, diagnostics, git, terminal)
  - `src/commands/` — Slash commands and @ mention handlers
  - `src/decorations/` — File decorations for AI-modified files
- `backend/` — Agent Server (authoritative brain)
- `schemas/` — JSON Schemas for API + WS events
- `docs/` — detailed specs: security, data model, indexing, RAG, ACE, tools, UI/UX
- `scripts/` — dev scripts & codegen placeholders

## Quick start (dev, when you implement)
1. Run Qdrant (recommended):
   - `docker compose up -d qdrant`
2. Start server:
   - `cd backend && uvicorn app.main:app --reload --port 3199`
3. Run extension:
   - Open `modules/vscode-extension/` in VS Code → `F5` (Extension Development Host)
4. Configure in extension settings:
   - `locoAgent.serverUrl = "https://<desktop-ip>:3199"` (or http for dev)
   - `locoAgent.modelProvider = "ollama"` (or vllm, llama.cpp)
   - `locoAgent.autoContext = true` (gather context automatically)

## UI/UX Features (Codex-like)
- **Dedicated sidebar** with chat interface and file changes tree
- **Inline diff previews** with accept/reject/undo actions
- **@ mentions** for files, symbols, and workspace references
- **Slash commands**: /fix, /explain, /test, /optimize, /refactor
- **Streaming responses** with thinking indicators and tool use visibility
- **Multi-file editing** in a single agent response
- **Terminal integration** for automatic test/build output capture
- **Git integration** showing changed files with diff indicators
- **File decorations** showing AI-modified files in explorer

## Docs
- **Architecture**: `docs/ARCHITECTURE.md`
- **API / WS protocol**: `docs/PROTOCOL.md`
- **Security & sandboxing**: `docs/SECURITY.md`
- **Indexing + Agentic RAG**: `docs/RAG_AND_INDEXING.md`
- **ACE (Context Engineering)**: `docs/ACE.md`
- **Data model**: `docs/DATA_MODEL.md`
- **UI/UX Spec**: `docs/UI_UX.md`
- **Milestones**: `docs/ROADMAP.md`

---

Date: 2025-12-30
