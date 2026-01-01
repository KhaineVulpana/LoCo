# UI/UX Specification (Codex/Claude Code Parity)

This document specifies the exact UI/UX to match Claude Code and GitHub Codex.

## Sidebar Layout

### Primary Sidebar View
```
┌─────────────────────────────────────┐
│  LoCo Agent            [⚙] [↻]  │ <- Header with settings and refresh
├─────────────────────────────────────┤
│  Chat                               │
│  ┌───────────────────────────────┐  │
│  │ @ Mention files or /command   │  │ <- Input with @ and / pickers
│  └───────────────────────────────┘  │
│  [Send] [Attach]                    │
├─────────────────────────────────────┤
│  💬 Chat History                    │
│  ┌───────────────────────────────┐  │
│  │ User: Fix the login bug       │  │
│  │                               │  │
│  │ 🤖 Thinking...                │  │ <- Thinking indicator
│  │ Planning: Analyzing login.ts  │  │ <- Plan steps
│  │                               │  │
│  │ 📝 Proposing changes to:      │  │
│  │   ✓ src/auth/login.ts         │  │ <- File change list
│  │   ⏳ src/auth/session.ts      │  │
│  │                               │  │
│  │ [Accept All] [Reject All]     │  │ <- Bulk actions
│  └───────────────────────────────┘  │
├─────────────────────────────────────┤
│  📁 Changed Files (3)               │ <- TreeView section
│  ├─ ✓ src/auth/login.ts            │ <- Accepted
│  ├─ ⏳ src/auth/session.ts         │ <- Pending
│  └─ ✗ src/utils/helper.ts          │ <- Rejected
└─────────────────────────────────────┘
```

## Chat Input Features

### @ Mentions (Codex-style)
Trigger: User types `@` in input field

Shows quick pick with:
- **Files**:
  - Recently opened files (top 10)
  - All workspace files (fuzzy search)
  - Currently visible editors
  - Git staged/modified files
- **Symbols**:
  - Functions, classes, methods in current file
  - Workspace-wide symbol search
- **Diagnostics**:
  - Current file errors/warnings
  - All workspace problems
- **Context items**:
  - @terminal (recent terminal output)
  - @git (current git status and diff)
  - @selection (current editor selection)
  - @problems (all diagnostics)

### Slash Commands
Trigger: User types `/` at start of input

Available commands:
- `/fix` - Fix errors in current file or selection
- `/explain` - Explain selected code or current file
- `/test` - Generate tests for selected code
- `/optimize` - Optimize performance of selected code
- `/refactor` - Refactor selected code
- `/review` - Review code for issues and improvements
- `/doc` - Generate documentation
- `/commit` - Generate commit message for staged changes

## Inline Diff Preview

### Editor Decorations (before diff applied)
```typescript
// Original code (faded)
function login(username, password) {
  return db.query('SELECT * FROM users WHERE name = ' + username);
}

// Proposed change (highlighted in green)
function login(username: string, password: string): Promise<User> {
  return db.query('SELECT * FROM users WHERE name = ?', [username]);
}
```

### Diff Actions (appear in editor)
```
┌────────────────────────────────────────┐
│ 🤖 AI proposed change                  │
│ [Accept] [Reject] [Edit] [View Diff]   │ <- Inline action bar
└────────────────────────────────────────┘
```

### Gutter Indicators
- Green bar on left gutter for added lines
- Red bar for removed lines
- Blue bar for modified lines
- Click gutter to see before/after

## File Changes TreeView

Located below chat in sidebar, shows all files modified in current session.

### States:
- ⏳ **Pending**: Diff proposed, not yet applied
- ✓ **Accepted**: Diff applied successfully
- ✗ **Rejected**: User rejected the diff
- ⚠️ **Conflict**: Diff failed to apply cleanly
- 🔄 **Modified**: File changed since AI proposal

### Actions per file:
- Click → Open diff viewer (before/after)
- Right-click menu:
  - Accept
  - Reject
  - View Diff
  - Undo (if already applied)
  - Open File

### Bulk actions (header):
- Accept All
- Reject All
- Review All (opens diffs in tabs)

## Streaming Response UI

### Thinking Phase
```
🤖 Thinking...
  ├─ Reading src/auth/login.ts
  ├─ Analyzing authentication flow
  ├─ Searching for related security patterns
  └─ Planning changes
```

### Planning Phase
```
📋 Plan:
  1. Add input validation to prevent SQL injection
  2. Add TypeScript types for parameters
  3. Use parameterized queries
  4. Add error handling for database failures
```

### Tool Use Phase
```
🔧 Tools:
  ├─ read_file: src/auth/login.ts ✓
  ├─ search_symbols: "db.query" ✓
  ├─ read_file: src/db/connection.ts ✓
  └─ propose_diff: src/auth/login.ts ⏳
```

### Diff Proposal Phase
```
📝 Proposing changes to 2 files:
  ✓ src/auth/login.ts (Accept | Reject | Diff)
  ⏳ src/auth/session.ts (waiting...)
```

## Settings UI

Accessible via gear icon in sidebar header.

### Categories:
1. **Server**:
   - Server URL
   - Connection status indicator
   - Reconnect button
2. **Model**:
   - Provider (Ollama/vLLM/llama.cpp)
   - Model selection dropdown
   - Temperature slider
   - Max tokens
3. **Context**:
   - Auto-gather diagnostics (on/off)
   - Auto-gather terminal output (on/off)
   - Auto-gather git status (on/off)
   - Include test files by default (on/off)
4. **Diff Behavior**:
   - Auto-accept simple changes (on/off)
   - Show inline diffs (on/off)
   - Require approval for deletions (on/off)
5. **Security**:
   - Command approval policy (always/never/prompt)
   - Allowed command patterns
   - Read-only mode (on/off)

## Context Menu Integration

### Right-click in editor:
- "Ask LoCo Agent" (with selection or without)
- "Fix with LoCo Agent"
- "Explain this code"
- "Generate tests for this"
- "Refactor this code"

### Right-click in file explorer:
- "Add to LoCo Agent context"
- "Analyze file with LoCo Agent"

## Status Bar

Bottom status bar shows:
- 🤖 Connection status (connected/disconnected)
- Model name (e.g., "codellama:13b")
- Current session info
- Click to open sidebar

## Keyboard Shortcuts

- `Cmd/Ctrl + Shift + A` - Open sidebar
- `Cmd/Ctrl + Shift + K` - Focus chat input
- `Cmd/Ctrl + Shift + D` - Show all diffs
- `Cmd/Ctrl + Shift + Enter` - Send message
- `Esc` - Cancel current agent run

## Progress Indicators

### During indexing:
```
⏳ Indexing workspace... (1,234 / 5,678 files)
[================>           ] 45%
```

### During retrieval:
```
🔍 Searching codebase...
  ├─ Symbol search: 12 results
  ├─ Text search: 45 results
  └─ Vector search: 8 results
```

### During test execution:
```
🧪 Running tests...
  ✓ 12 passed
  ✗ 2 failed
  ⏭ 5 skipped
```

## Error Handling UI

### Server connection error:
```
❌ Cannot connect to LoCo Agent server
Server URL: https://192.168.1.100:3199
[Retry] [Settings] [View Logs]
```

### Patch application error:
```
⚠️ Failed to apply changes to login.ts
Reason: File has been modified since diff was generated
[View Conflict] [Regenerate Diff] [Skip File]
```

### Tool execution error:
```
🛑 Command failed: npm test
Exit code: 1
[View Output] [Fix Command] [Cancel]
```

## Diff Viewer Integration

When user clicks "View Diff", open VS Code's native diff viewer:
- Left: Original file
- Right: Proposed changes
- Unified diff view with line-by-line comparison
- Accept/Reject buttons at top
- Navigate between hunks with F7/Shift+F7

## Git Integration

### Before committing AI changes:
```
📊 AI Changes Summary:
  3 files modified
  +127 lines
  -43 lines
  
🤖 Suggested commit message:
  "Fix SQL injection in authentication

  - Add input validation
  - Use parameterized queries
  - Add TypeScript types"

[Edit Message] [Commit] [Cancel]
```

## Terminal Integration

When terminal output is relevant, show in chat:
```
🖥️ Terminal Output:
┌──────────────────────────────────────┐
│ $ npm test                           │
│                                      │
│ FAIL src/auth/login.test.ts          │
│   ✕ should validate input (23ms)    │
│                                      │
│ Expected: true                       │
│ Received: undefined                  │
└──────────────────────────────────────┘

I see the test is failing because...
```

## Mobile/Responsive Considerations

While primarily desktop-focused, the sidebar should:
- Use flex layout for resizing
- Collapse sections when sidebar is narrow
- Maintain readability at 300px minimum width
- Use icons instead of text labels when space constrained
