# Architecture

## Components

### 1) Desktop Agent Server (authoritative)
Responsibilities:
- Session orchestration (multi-step agent loop)
- Repo indexing (incremental, file-watching based)
- Retrieval (symbol/text/vector + rerank)
- ACE artifact store and retrieval
- Tool execution (read/search/plan/propose diff/run commands) with policy enforcement
- Audit logging of all tool calls and file modifications
- Streaming protocol to clients (WS with structured events)
- Model adapter layer (Ollama/vLLM/llama.cpp)

### 2) VS Code Extension (rich client with deep IDE integration)

#### Core Responsibilities:
- **UI**: Custom sidebar with chat interface, streaming responses, thinking indicators
- **Context capture**: Automatic gathering of workspace signals
  - Current file, selection, cursor position
  - Open editors and visible ranges
  - Diagnostics (errors, warnings) from all sources
  - Terminal output (recent commands and results)
  - Git status (staged/unstaged changes, current branch, recent commits)
  - Workspace symbols and recently accessed files
- **Diff handling**: 
  - Inline diff previews with decorations
  - Native VS Code diff viewer integration
  - Accept/reject/undo actions per file or per hunk
  - Real-time diff indicators in editor gutter
- **File operations**:
  - Apply patches using WorkspaceEdit APIs
  - File decorations for AI-modified files
  - TreeView showing all files changed in current session
  - Rollback/revert capabilities
- **Command integration**:
  - Slash commands (/fix, /explain, /test, /optimize, /refactor)
  - @ mention pickers for files, symbols, diagnostics
  - Quick pick menus for model/provider selection
- **Terminal integration**:
  - Capture terminal output in real-time
  - Send output to server for error analysis
  - Execute commands via Terminal API (user-visible)
- **Git integration**:
  - Show diffs before/after AI changes
  - Integration with VS Code's Source Control API
  - Commit suggestions with AI-generated messages

#### Extension Architecture:
```
modules/vscode-extension/
├── src/
│   ├── extension.ts          # Entry point, activation
│   ├── sidebar/
│   │   ├── SidebarProvider.ts       # Custom sidebar webview
│   │   ├── ChatUI.svelte            # Chat interface (Svelte)
│   │   ├── FileChangesTree.ts       # TreeView for changed files
│   │   └── StreamRenderer.ts        # Markdown + code streaming
│   ├── diff/
│   │   ├── DiffManager.ts           # Coordinate diff operations
│   │   ├── InlineDiffDecorator.ts   # Editor decorations for diffs
│   │   ├── DiffApplier.ts           # WorkspaceEdit application
│   │   └── DiffReviewer.ts          # Accept/reject UI
│   ├── context/
│   │   ├── ContextGatherer.ts       # Aggregate workspace context
│   │   ├── DiagnosticsCollector.ts  # Gather errors/warnings
│   │   ├── TerminalWatcher.ts       # Capture terminal output
│   │   └── GitContextProvider.ts    # Git status and diffs
│   ├── commands/
│   │   ├── SlashCommands.ts         # /fix, /test, etc.
│   │   ├── MentionPicker.ts         # @ mention file/symbol picker
│   │   └── QuickActions.ts          # Code actions, quick fixes
│   ├── decorations/
│   │   ├── FileDecorationProvider.ts # Show AI-modified files
│   │   └── GutterDecorations.ts      # Inline change indicators
│   ├── api/
│   │   ├── ServerClient.ts          # HTTP + WS client
│   │   └── types.ts                 # Type definitions
│   └── utils/
│       ├── security.ts              # Token storage, workspace trust
│       └── settings.ts              # Extension configuration
```

## Data flow overview (Codex-like interaction)

### User initiates task:
1. User types in sidebar chat OR uses slash command OR selects code and invokes context menu
2. Extension automatically gathers context:
   - Current file/selection
   - Open editors
   - Diagnostics
   - Terminal output (if relevant)
   - Git status
3. Extension sends to server via WS with structured context pack

### Server processing:
1. Parse intent, extract file/symbol references from @ mentions
2. ACE retrieval (constitution, gotchas, runbook)
3. Agentic RAG (symbol search → vector search → rerank)
4. Build context pack (bounded)
5. Stream plan to client
6. Execute tool calls (read files, search, analyze)
7. Propose patches for each file to modify

### Client rendering:
1. Show streaming thinking/plan in chat
2. As patches arrive, show inline diffs in editors
3. Show file changes tree in sidebar
4. User reviews and accepts/rejects per file or all at once
5. Extension applies via WorkspaceEdit
6. Results (success/failure/test output) stream back to server

### Iteration loop:
1. Server receives results (test failures, build errors, diagnostics)
2. Retrieves around failures (stack traces, relevant files)
3. Proposes fixes
4. Repeat until success or user cancels

## Why Custom Sidebar + Native Diff Viewer (not Chat Participant API)?
- **Custom sidebar** provides complete control over UI/UX to match Codex/Claude Code
- **Native diff viewer** leverages VS Code's battle-tested diffing with accept/reject/undo
- **TreeView for file changes** shows all modifications in one place
- **File decorations** make it obvious which files AI has touched
- **Terminal integration** captures output automatically without user copy/paste

Chat Participant API is still experimental and doesn't provide the level of control needed for multi-file diffs, inline decorations, and complex state management. We can add it later as an alternative entry point.

## Context gathering strategy (automatic, not manual)

Unlike simple chat extensions, this extension behaves like Codex:
1. **Always capture** current file, selection, diagnostics
2. **Conditionally capture** based on task type:
   - For /fix: diagnostics + terminal output + git diff
   - For /test: test file + related source + recent test output
   - For /explain: just the selection or current function
   - For /refactor: current file + dependents + call graph
3. **Never ask user to manually provide context** unless absolutely necessary
4. **Use @ mentions for explicit additions** (e.g., @src/utils/helper.ts)

## Security enforcement (client + server)

### Client-side (last-mile safety):
- Only apply patches within workspace root (respect workspace trust)
- Show diffs before applying (user sees exactly what will change)
- Terminal commands run in user-visible terminal (no hidden execution)
- Token stored in VS Code SecretStorage

### Server-side (policy enforcement):
- Workspace-scoped policies (read/write globs)
- Command approval gates
- Audit logging
- Tool execution guards
