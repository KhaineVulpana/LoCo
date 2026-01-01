# LoCo Agent - Feature Overview

This document provides a comprehensive overview of all features, both implemented and planned.

## ✅ Core Features (Implemented)

### 1. Server Foundation

**FastAPI-based Server**
- ✅ Health check endpoint
- ✅ WebSocket streaming protocol
- ✅ Bearer token authentication
- ✅ SQLite database with migrations
- ✅ Session management
- ✅ Workspace registration
- ✅ Audit logging infrastructure

**Protocol**
- ✅ Client/Server handshake
- ✅ Message type system
- ✅ Context structure (files, diagnostics, git, terminal)
- ✅ Streaming responses
- ✅ Error handling

### 2. VS Code Extension

**Core UI**
- ✅ Custom sidebar with chat interface
- ✅ WebSocket client with reconnection
- ✅ Streaming message rendering
- ✅ Markdown support with syntax highlighting
- ✅ Message history
- ✅ Thinking indicators

**Context Gathering**
- ✅ Active editor (file, selection, visible range)
- ✅ Open editors
- ✅ Diagnostics (errors, warnings from all sources)
- ✅ Git status (branch, modified files, staged files)
- ✅ Automatic context on every message

**Diff Management**
- ✅ Patch storage and tracking
- ✅ Accept/Reject actions
- ✅ View diff (side-by-side comparison)
- ✅ WorkspaceEdit API integration

**Settings**
- ✅ Server URL configuration
- ✅ Model provider selection
- ✅ Auto-context toggle
- ✅ Inline diff preview toggle

### 3. Database Schema

- ✅ Workspaces table
- ✅ Workspace policies
- ✅ Sessions table
- ✅ Session messages
- ✅ Tool events (audit log)
- ✅ Patch events
- ✅ Files table
- ✅ Chunks table
- ✅ Symbols table
- ✅ ACE artifacts table
- ✅ Embedding cache

### 4. Security

- ✅ Token generation and storage
- ✅ SecretStorage integration (VS Code)
- ✅ Workspace trust checking
- ✅ Bearer token authentication
- ✅ Audit logging structure

### 5. Configuration

- ✅ Environment variables (.env)
- ✅ VS Code settings integration
- ✅ Model provider abstraction
- ✅ Context window detection
- ✅ Docker Compose for Qdrant

## 🚧 Partially Implemented Features

### 1. Protocol Messages

**Implemented:**
- ✅ client.hello
- ✅ server.hello
- ✅ client.user_message
- ✅ assistant.thinking
- ✅ assistant.message_final
- ✅ server.error

**Planned:**
- ⏳ agent.plan (structure exists, needs full implementation)
- ⏳ patch.proposed (structure exists, needs server-side generation)
- ⏳ tool.execute (structure exists, needs tool runners)
- ⏳ tool.request_approval
- ⏳ command.request_approval

### 2. Diff Application

**Implemented:**
- ✅ Patch tracking
- ✅ Accept/Reject UI
- ✅ View diff
- ✅ Basic diff parsing

**Needs:**
- ⏳ Proper unified diff library (diff-match-patch)
- ⏳ Conflict detection
- ⏳ Undo stack
- ⏳ Inline decorations in editor
- ⏳ Gutter indicators

## 📋 Planned Features (Not Yet Implemented)

### 1. Indexing Pipeline

- ⏳ File discovery (with .gitignore support)
- ⏳ Language detection (tree-sitter)
- ⏳ AST-based chunking
- ⏳ Symbol extraction
- ⏳ Incremental indexing (file watcher)
- ⏳ File hashing and change detection
- ⏳ Progress reporting to extension

### 2. Embedding & Vector Search

- ⏳ Embedding model loading
- ⏳ Batch embedding
- ⏳ Qdrant client integration
- ⏳ Vector storage with metadata
- ⏳ Filtered search (by language, module, recency)
- ⏳ Embedding cache

### 3. Agentic RAG

**Symbol Search:**
- ⏳ SQLite FTS for symbol names
- ⏳ Signature matching
- ⏳ Qualified name search

**Text Search:**
- ⏳ Ripgrep integration
- ⏳ Regex support
- ⏳ Multi-line search

**Vector Search:**
- ⏳ Semantic search via Qdrant
- ⏳ Relevance ranking
- ⏳ Reranker (optional)

**Hybrid Retrieval:**
- ⏳ Combine symbol + text + vector
- ⏳ Context pack builder
- ⏳ Token budget management
- ⏳ Dependency expansion

### 4. Slash Commands

- ⏳ /fix - Fix errors in current file
- ⏳ /explain - Explain selected code
- ⏳ /test - Generate tests
- ⏳ /optimize - Optimize performance
- ⏳ /refactor - Refactor code
- ⏳ /review - Code review
- ⏳ /doc - Generate documentation
- ⏳ /commit - Generate commit message

### 5. @ Mentions

**Pickers:**
- ⏳ File picker (fuzzy search, recent files)
- ⏳ Symbol picker (workspace symbols)
- ⏳ Diagnostics picker
- ⏳ Context items (@terminal, @git, @selection)

**Visual Indicators:**
- ⏳ Show added context items
- ⏳ Remove context items
- ⏳ Context item badges

### 6. Tool Execution

**Tools:**
- ⏳ read_file
- ⏳ search_symbols
- ⏳ search_text
- ⏳ vector_search
- ⏳ propose_diff
- ⏳ execute_command

**Command Execution:**
- ⏳ Local terminal execution (VS Code Terminal API)
- ⏳ Output capture (stdout, stderr, exit code)
- ⏳ Server-side runner (optional, sandboxed)
- ⏳ Approval gates
- ⏳ Time limits

### 7. Iterative Fix Loop

- ⏳ Test/build failure detection
- ⏳ Error parsing (Jest, pytest, TypeScript, ESLint)
- ⏳ Stack trace extraction
- ⏳ Retrieval around failures
- ⏳ Propose fixes
- ⏳ Re-run verification
- ⏳ Iterate until success or max retries

### 8. ACE (Agentic Context Engineering)

**Artifact Types:**
- ⏳ Constitution (project rules)
- ⏳ Runbook (verified commands)
- ⏳ Gotchas (failure → fix patterns)
- ⏳ Decisions (architectural decisions)
- ⏳ Glossary (domain terms → code locations)

**Lifecycle:**
- ⏳ Creation after successful checkpoints
- ⏳ User approval for artifacts
- ⏳ Versioning
- ⏳ Retrieval at task start
- ⏳ Quality gates (1-5 bullet points, scoped, verifiable)

### 9. File Changes TreeView

- ⏳ TreeView in sidebar
- ⏳ File states (pending, accepted, rejected, conflict)
- ⏳ Per-file actions (accept, reject, view diff, undo)
- ⏳ Bulk actions (accept all, reject all)
- ⏳ File decorations in explorer

### 10. Model Adapters

**Ollama:**
- ⏳ Model listing
- ⏳ Chat completion
- ⏳ Streaming
- ⏳ Context window detection

**vLLM:**
- ⏳ OpenAI-compatible API
- ⏳ Streaming support

**llama.cpp:**
- ⏳ HTTP server integration

### 11. Advanced Features (Future)

**Multi-Agent Collaboration:**
- ⏳ Code review agent
- ⏳ Test generation agent
- ⏳ Security audit agent

**IDE Integrations:**
- ⏳ IntelliJ plugin
- ⏳ Neovim plugin

**Advanced RAG:**
- ⏳ Callgraph-aware retrieval
- ⏳ Test-to-source mapping
- ⏳ Dependency impact analysis

**Code Intelligence:**
- ⏳ Type inference for dynamic languages
- ⏳ Dead code detection
- ⏳ Optimization suggestions
- ⏳ Security vulnerability scanning

## Development Roadmap

See [ROADMAP.md](./docs/ROADMAP.md) for detailed implementation phases.

### Phase 1: Foundation ✅
- ✅ Server (FastAPI, SQLite, WebSocket)
- ✅ Extension (TypeScript, sidebar, WebSocket client)
- ✅ Protocol implementation
- ✅ Database schema

### Phase 2: Repo Intelligence 🚧
- ⏳ Indexing pipeline
- ⏳ Vector store integration
- ⏳ Multi-source retrieval
- ⏳ Context pack builder

### Phase 3: Codex-like UI 🚧
- ✅ Sidebar chat UI
- ✅ Automatic context gathering
- ⏳ @ mentions and pickers
- ⏳ Slash commands
- ⏳ File changes TreeView

### Phase 4: Diff & Patch 🚧
- ✅ Diff generation (basic)
- ✅ Inline diff preview (basic)
- ✅ Native diff viewer integration
- ⏳ Patch application (robust)
- ⏳ File decorations

### Phase 5: Agentic Loop 📋
- ⏳ Command execution
- ⏳ Failure analysis
- ⏳ Fix iteration
- ⏳ Verification

### Phase 6: ACE 📋
- ⏳ Artifact types
- ⏳ Artifact creation
- ⏳ Artifact retrieval
- ⏳ Quality gates

### Phase 7: Hardening 📋
- ⏳ Security (TLS, pairing)
- ⏳ Performance (caching, batching)
- ⏳ Error recovery
- ⏳ Testing

### Phase 8: Advanced Features 📋
- ⏳ Multi-agent collaboration
- ⏳ IDE integrations
- ⏳ Advanced RAG
- ⏳ Code intelligence

## Feature Comparison

| Feature | LoCo Agent | GitHub Copilot | Claude Code |
|---------|---------------|----------------|-------------|
| Local-first | ✅ Yes | ❌ Cloud | ❌ Cloud |
| Full code stays local | ✅ Yes | ❌ No | ❌ No |
| Custom sidebar | ✅ Yes | ❌ No | ✅ Yes |
| @ mentions | 🚧 Planned | ❌ No | ✅ Yes |
| Slash commands | 🚧 Planned | ❌ No | ✅ Yes |
| Multi-file editing | 🚧 Planned | ❌ No | ✅ Yes |
| Inline diffs | ✅ Yes | ✅ Yes | ✅ Yes |
| Auto context | ✅ Yes | ❌ Limited | ✅ Yes |
| Agentic RAG | 🚧 Planned | ❌ No | ❌ No |
| ACE (learns patterns) | 🚧 Planned | ❌ No | ❌ No |
| Pluggable models | ✅ Yes | ❌ No | ❌ No |
| Audit logs | ✅ Yes | ❌ No | ❌ No |

Legend:
- ✅ Implemented
- 🚧 Partially implemented / In progress
- ⏳ Planned
- ❌ Not available

---

**Current Status:** Foundation complete, working on intelligence layer (indexing, RAG, tool execution)
