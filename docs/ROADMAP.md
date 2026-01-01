# Roadmap (Codex-like Feature Milestones)

## Phase 1: Core Infrastructure (Foundation)
**Goal**: Get the basic plumbing working - server, extension, protocol

### 1.1 Server Foundation
- [ ] FastAPI server with health endpoint
- [ ] SQLite setup with migrations
- [ ] WebSocket streaming protocol
- [ ] Bearer token authentication
- [ ] Workspace registry and policy engine
- [ ] Session store and lifecycle management
- [ ] Audit logging (append-only events)

### 1.2 Extension Foundation
- [ ] VS Code extension boilerplate (TypeScript)
- [ ] Custom sidebar view registration
- [ ] WebSocket client with reconnection logic
- [ ] Token storage in SecretStorage
- [ ] Settings UI (basic)
- [ ] Status bar integration

### 1.3 Protocol Implementation
- [ ] Client ↔ Server message schema validation
- [ ] Streaming token rendering
- [ ] Error handling and recovery
- [ ] Connection status indicators

**Milestone**: Can send a message from extension → server → response streams back

---

## Phase 2: Repo Intelligence (Indexing & Retrieval)
**Goal**: Make the agent repo-aware with fast, accurate retrieval

### 2.1 Indexing Pipeline
- [ ] File discovery (respect .gitignore)
- [ ] Language detection (tree-sitter setup)
- [ ] AST-based chunking (code-aware boundaries)
- [ ] Symbol extraction (functions, classes, imports)
- [ ] File hashing and change detection
- [ ] Incremental indexing on file changes
- [ ] Index status reporting to extension

### 2.2 Vector Store Integration
- [ ] Qdrant adapter (default)
- [ ] Embedding model integration (local)
- [ ] Vector storage with metadata (file path, language, tags)
- [ ] Filtered search (by language, module, recency)
- [ ] Optional reranker integration

### 2.3 Multi-Source Retrieval
- [ ] Symbol index search (fast, precise)
- [ ] Text search (ripgrep integration)
- [ ] Vector search (semantic)
- [ ] Hybrid retrieval (combine all sources)
- [ ] Relevance ranking and pruning
- [ ] Dependency expansion (imports/callees/tests)

### 2.4 Context Pack Builder
- [ ] Bounded context assembly (token budget)
- [ ] Structured context format (goal + evidence + constraints)
- [ ] File content with line numbers
- [ ] Symbol definitions with signatures
- [ ] Test file associations

**Milestone**: Agent can accurately retrieve relevant code given a task description

---

## Phase 3: Codex-like UI (Rich Extension)
**Goal**: Build the UI/UX that matches Claude Code and Codex

### 3.1 Sidebar Chat UI
- [ ] Webview-based chat interface (Svelte/React)
- [ ] Streaming message rendering (Markdown + code)
- [ ] Thinking indicators (phases: analyzing, planning, retrieving, executing)
- [ ] Tool execution visibility (show tool calls and results)
- [ ] Plan presentation (numbered steps with files involved)
- [ ] Message history with persistence

### 3.2 @ Mentions and Context Pickers
- [ ] @ mention file picker (fuzzy search, recent files)
- [ ] @ mention symbol picker (workspace symbols)
- [ ] @ mention diagnostics picker (errors/warnings)
- [ ] @ mention context items (@terminal, @git, @selection, @problems)
- [ ] Visual indicators for added context items

### 3.3 Slash Commands
- [ ] Command registry: /fix, /explain, /test, /optimize, /refactor, /review, /doc, /commit
- [ ] Command-specific context gathering
- [ ] Quick pick menu for command selection
- [ ] Command help and autocomplete

### 3.4 Automatic Context Gathering
- [ ] Current file and selection capture
- [ ] Open editors tracking
- [ ] Diagnostics collection (all sources: TypeScript, ESLint, etc.)
- [ ] Terminal output watcher (capture recent commands and output)
- [ ] Git status integration (branch, staged/modified files, recent commits)
- [ ] Visible range tracking (what user can see)

### 3.5 File Changes TreeView
- [ ] TreeView in sidebar showing all modified files
- [ ] File states: pending, accepted, rejected, conflict, modified
- [ ] Per-file actions: accept, reject, view diff, undo
- [ ] Bulk actions: accept all, reject all, review all
- [ ] File decorations in explorer (show AI-modified files)

**Milestone**: Extension UI matches Codex with sidebar, @ mentions, slash commands, context gathering

---

## Phase 4: Diff & Patch Application (Multi-File Editing)
**Goal**: Propose, preview, and apply code changes like Codex

### 4.1 Diff Generation (Server)
- [ ] Unified diff generation (git-style)
- [ ] Minimal diff optimization (stable formatting)
- [ ] Per-file patches with hunks
- [ ] Rationale and acceptance criteria for each patch
- [ ] Multi-file patch proposals in single response

### 4.2 Inline Diff Preview (Extension)
- [ ] Editor decorations for proposed changes (green/red/blue bars)
- [ ] Inline diff rendering (before/after)
- [ ] Accept/reject/edit action bar above diffs
- [ ] Gutter indicators (click to see before/after)
- [ ] Syntax highlighting in diff preview

### 4.3 Native Diff Viewer Integration
- [ ] Open VS Code diff viewer on "View Diff" click
- [ ] Before/after side-by-side comparison
- [ ] Navigate between hunks (F7/Shift+F7)
- [ ] Accept/reject from diff viewer

### 4.4 Patch Application (Extension)
- [ ] Apply patches via WorkspaceEdit API
- [ ] Workspace trust enforcement (only inside workspace root)
- [ ] Conflict detection and reporting
- [ ] Rollback/undo support
- [ ] Success/failure reporting to server

### 4.5 File Decorations
- [ ] File decorations in explorer showing AI-modified files
- [ ] Decoration states: pending, applied, conflict
- [ ] Decoration removal after commit or undo

**Milestone**: Agent can propose and apply multi-file changes with full preview and control

---

## Phase 5: Agentic Loop (Iterative Fix → Run → Verify)
**Goal**: Agent iterates on failures until success or user cancellation

### 5.1 Command Execution
- [ ] Local terminal execution (VS Code Terminal API)
- [ ] Command output capture (stdout, stderr, exit code)
- [ ] Optional server-side execution with sandboxing
- [ ] Command approval gates (policy-based)
- [ ] Time limits and output size limits

### 5.2 Failure Analysis
- [ ] Parse test failures (Jest, pytest, etc.)
- [ ] Parse build errors (TypeScript, ESLint, etc.)
- [ ] Extract stack traces and error messages
- [ ] Retrieve around failures (relevant files and lines)

### 5.3 Fix Iteration
- [ ] Propose fixes based on failure analysis
- [ ] Apply fixes automatically (if policy allows)
- [ ] Re-run tests/build after each fix
- [ ] Iterate until success or max iterations
- [ ] Stop conditions (success, max retries, user cancel)

### 5.4 Verification
- [ ] Run tests after applying patches
- [ ] Run build/linter after changes
- [ ] Report verification results in chat
- [ ] Auto-accept if all verifications pass (optional setting)

**Milestone**: Agent can fix bugs iteratively by running tests and analyzing failures

---

## Phase 6: ACE (Context Engineering)
**Goal**: Agent learns from successes and failures without bloating prompts

### 6.1 Artifact Types
- [ ] Constitution: project rules (style, constraints, do/don't)
- [ ] Runbook: verified commands and procedures
- [ ] Gotchas: failure → fix patterns
- [ ] Decisions: architectural decisions with rationale
- [ ] Glossary: domain terms → code locations

### 6.2 Artifact Creation
- [ ] Trigger after successful checkpoints (tests pass, build succeeds)
- [ ] Extract patterns from successful tasks
- [ ] User approval for artifact creation
- [ ] Versioning (track changes to artifacts)
- [ ] Scope artifacts (workspace, module, file)

### 6.3 Artifact Retrieval
- [ ] Retrieve constitution at task start (always)
- [ ] Retrieve relevant gotchas (module-specific)
- [ ] Retrieve runbook commands (when needed)
- [ ] Context budget discipline (prefer ACE over raw logs)

### 6.4 Quality Gates
- [ ] 1-5 bullet points per artifact
- [ ] Verifiable (includes command or file evidence)
- [ ] Tagged for retrieval (workspace, module, file, keywords)
- [ ] Confidence score and last-verified timestamp

**Milestone**: Agent improves over time by learning project patterns

---

## Phase 7: Hardening & Polish
**Goal**: Make it production-ready and robust

### 7.1 Security
- [ ] TLS for LAN deployment (self-signed cert generation)
- [ ] Device pairing flow (alternative to manual token)
- [ ] Workspace trust integration (respect VS Code workspace trust)
- [ ] Command allowlist enforcement
- [ ] Audit log viewer in extension

### 7.2 Performance
- [ ] Caching (embeddings, retrieval results, file hashes)
- [ ] Batching (index updates, vector inserts)
- [ ] Background indexing (don't block user)
- [ ] Streaming optimizations (chunked responses)
- [ ] Memory management (cleanup old sessions)

### 7.3 Error Recovery
- [ ] Reconnection logic (exponential backoff)
- [ ] Resume interrupted sessions
- [ ] Rollback failed patches automatically
- [ ] Graceful degradation (work without vector store)

### 7.4 Testing
- [ ] Unit tests (server and extension)
- [ ] Integration tests (protocol, retrieval, diff application)
- [ ] E2E tests (full user flows)
- [ ] Regression harness (catch regressions in retrieval quality)

### 7.5 Documentation
- [ ] User guide (setup, usage, troubleshooting)
- [ ] Developer guide (architecture, extending, custom models)
- [ ] API reference (protocol, schemas, adapters)
- [ ] Example configurations (model providers, security policies)

**Milestone**: Production-ready with tests, docs, and hardening

---

## Phase 8: Advanced Features (Future)
**Goal**: Go beyond Codex with unique capabilities

### 8.1 Multi-Agent Collaboration
- [ ] Code review agent (separate model)
- [ ] Test generation agent
- [ ] Security audit agent
- [ ] Agents communicate via structured protocol

### 8.2 IDE Integrations
- [ ] IntelliJ plugin
- [ ] Neovim plugin
- [ ] Emacs integration

### 8.3 Advanced RAG
- [ ] Callgraph-aware retrieval
- [ ] Test-to-source mapping
- [ ] Dependency impact analysis
- [ ] Historical code evolution tracking

### 8.4 Code Intelligence
- [ ] Type inference for dynamic languages
- [ ] Dead code detection
- [ ] Optimization suggestions
- [ ] Security vulnerability scanning

**Milestone**: Beyond Codex with unique local-first capabilities

---

## Implementation Priority

**Critical path** (must have for MVP):
1. Phase 1 (Foundation)
2. Phase 2 (Indexing & Retrieval)
3. Phase 3 (Codex-like UI)
4. Phase 4 (Diff & Patch)
5. Phase 5 (Iterative Loop)

**High value** (makes it great):
6. Phase 6 (ACE)
7. Phase 7 (Hardening)

**Future enhancements**:
8. Phase 8 (Advanced Features)

---

## Success Criteria

### MVP (Phases 1-5):
- User can chat with agent in sidebar
- Agent retrieves relevant code accurately
- Agent proposes multi-file changes with inline diffs
- User can accept/reject changes with preview
- Agent iterates on test failures until success

### Production-ready (Phases 1-7):
- Secure LAN deployment with TLS
- Fast indexing and retrieval (<5s for 10k files)
- Robust error handling and recovery
- Comprehensive audit logs
- Full test coverage
- Clear documentation

### Differentiated (Phase 8):
- Learns from project patterns (ACE)
- Multi-agent workflows
- Superior retrieval quality vs cloud alternatives
- Unique local-first capabilities
