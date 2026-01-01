# Protocol (HTTP + WebSocket)

This product is **contract-first**: clients and server communicate via strict JSON schemas in `schemas/`.

## Base URL
- `https://<desktop-host>:3199` (recommended)
- `http://<desktop-host>:3199` (dev only)

## Authentication
- Bearer token in `Authorization: Bearer <token>`
- Token stored in VS Code SecretStorage.
- Pairing flow is optional; start with manual token.

## HTTP endpoints (v1)

### Health
- `GET /v1/health`

### Workspaces
- `GET /v1/workspaces`
- `POST /v1/workspaces/register`
- `GET /v1/workspaces/{workspace_id}`
- `GET /v1/workspaces/{workspace_id}/policy`
- `PUT /v1/workspaces/{workspace_id}/policy`

### Indexing
- `POST /v1/workspaces/{workspace_id}/index/rebuild`
- `POST /v1/workspaces/{workspace_id}/index/refresh`
- `POST /v1/workspaces/{workspace_id}/index/incremental` (for file watcher events)
- `GET /v1/workspaces/{workspace_id}/index/status`

### Sessions
- `POST /v1/sessions`
- `GET /v1/sessions?workspace_id=...`
- `GET /v1/sessions/{session_id}`
- `DELETE /v1/sessions/{session_id}`

### Models
- `GET /v1/models` (list available models)
- `GET /v1/models/current` (get current model configuration)
- `PUT /v1/models/current` (set model provider and configuration)

## WebSocket streaming

### Connect
- `WS /v1/sessions/{session_id}/stream`

## Client → Server messages

### Initial handshake
```typescript
{
  "type": "client.hello",
  "client_info": {
    "name": "vscode-extension",
    "version": "0.1.0",
    "capabilities": ["diff_preview", "terminal_exec", "git_integration"]
  }
}
```

### User message with automatic context
```typescript
{
  "type": "client.user_message",
  "message": "Fix the authentication bug",
  "context": {
    // Current editor context
    "active_editor": {
      "file_path": "src/auth/login.ts",
      "language": "typescript",
      "selection": {
        "start": { "line": 23, "character": 0 },
        "end": { "line": 45, "character": 12 }
      },
      "visible_range": {
        "start": 1,
        "end": 100
      },
      "content_hash": "sha256:abc123..."
    },
    
    // Open editors (for multi-file context)
    "open_editors": [
      {
        "file_path": "src/auth/session.ts",
        "is_dirty": false,
        "visible": true
      }
    ],
    
    // Diagnostics (errors/warnings)
    "diagnostics": [
      {
        "file_path": "src/auth/login.ts",
        "severity": "error",
        "message": "Property 'password' is used before being defined",
        "line": 23,
        "character": 15,
        "source": "typescript"
      }
    ],
    
    // Terminal output (recent)
    "terminal_output": {
      "command": "npm test",
      "exit_code": 1,
      "stdout": "FAIL src/auth/login.test.ts...",
      "stderr": "",
      "timestamp": "2025-12-30T10:30:45Z"
    },
    
    // Git status
    "git_context": {
      "branch": "feature/auth-fix",
      "staged_files": [],
      "modified_files": ["src/auth/login.ts", "src/auth/session.ts"],
      "recent_commits": [
        {
          "sha": "abc123",
          "message": "Add password validation",
          "author": "Kevin",
          "timestamp": "2025-12-30T09:15:00Z"
        }
      ]
    },
    
    // Explicit @ mentions
    "mentions": [
      {
        "type": "file",
        "path": "src/utils/validator.ts"
      },
      {
        "type": "symbol",
        "name": "validatePassword",
        "file_path": "src/utils/validator.ts",
        "line": 12
      }
    ],
    
    // Slash command (if used)
    "command": "/fix"
  }
}
```

### Context update (during conversation)
```typescript
{
  "type": "client.context_update",
  "updates": {
    "diagnostics": [ /* new diagnostics */ ],
    "terminal_output": { /* latest output */ }
  }
}
```

### Approval response
```typescript
{
  "type": "client.approval_response",
  "request_id": "req_abc123",
  "approved": true,
  "scope": "all" | "file" | "hunk",
  "file_path": "src/auth/login.ts" // if scope is file or hunk
}
```

### Patch apply result
```typescript
{
  "type": "client.patch_apply_result",
  "patch_id": "patch_abc123",
  "file_path": "src/auth/login.ts",
  "success": true,
  "error": null, // or { "message": "...", "type": "conflict" }
  "applied_hash": "sha256:def456..."
}
```

### Command execution result
```typescript
{
  "type": "client.command_result",
  "command_id": "cmd_abc123",
  "command": "npm test",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 2340
}
```

### Cancel request
```typescript
{
  "type": "client.cancel",
  "reason": "user_cancelled"
}
```

## Server → Client messages

### Server handshake
```typescript
{
  "type": "server.hello",
  "server_info": {
    "version": "0.1.0",
    "model": {
      "provider": "ollama",
      "model_name": "codellama:13b",
      "capabilities": ["chat", "code_completion", "refactor"]
    },
    "capabilities": ["agentic_rag", "ace", "multi_file_edit"]
  }
}
```

### Thinking indicators (streaming)
```typescript
{
  "type": "assistant.thinking",
  "phase": "analyzing" | "planning" | "retrieving" | "executing",
  "message": "Analyzing authentication flow..."
}
```

### Plan presentation
```typescript
{
  "type": "agent.plan",
  "steps": [
    {
      "step_number": 1,
      "description": "Add input validation to prevent SQL injection",
      "files_involved": ["src/auth/login.ts"]
    },
    {
      "step_number": 2,
      "description": "Add TypeScript types for parameters",
      "files_involved": ["src/auth/login.ts", "src/types/auth.ts"]
    }
  ],
  "rationale": "These changes address the security vulnerability..."
}
```

### Retrieval status
```typescript
{
  "type": "agent.retrieve.status",
  "stage": "symbol_search" | "text_search" | "vector_search" | "reranking",
  "results_count": 12,
  "message": "Found 12 relevant symbols"
}
```

### Tool execution event
```typescript
{
  "type": "tool.execute",
  "tool_name": "read_file" | "search_symbols" | "search_text" | "vector_search",
  "args": {
    "file_path": "src/auth/login.ts"
  },
  "status": "started" | "completed" | "failed",
  "result": { /* tool-specific result */ }
}
```

### Patch proposal
```typescript
{
  "type": "patch.proposed",
  "patch_id": "patch_abc123",
  "file_path": "src/auth/login.ts",
  "diff": "--- a/src/auth/login.ts\n+++ b/src/auth/login.ts\n...",
  "rationale": "Added input validation to prevent SQL injection",
  "acceptance_criteria": [
    "Tests pass",
    "No SQL injection vulnerabilities",
    "Type safety maintained"
  ],
  "requires_approval": true,
  "hunks": [
    {
      "old_start": 23,
      "old_lines": 5,
      "new_start": 23,
      "new_lines": 8,
      "content": "..."
    }
  ]
}
```

### Approval request
```typescript
{
  "type": "tool.request_approval",
  "request_id": "req_abc123",
  "tool_name": "write_file" | "execute_command" | "delete_file",
  "args": {
    "file_path": "src/auth/login.ts",
    "reason": "Apply security fix"
  },
  "risk_level": "low" | "medium" | "high"
}
```

### Command approval request
```typescript
{
  "type": "command.request_approval",
  "command_id": "cmd_abc123",
  "command": "npm test",
  "working_directory": "/workspace/path",
  "environment": { "NODE_ENV": "test" },
  "requires_approval": true,
  "reason": "Verify fix resolves test failures"
}
```

### Streaming tokens (during response generation)
```typescript
{
  "type": "assistant.token",
  "token": "The",
  "cumulative_text": "The authentication bug..."
}
```

### Final message
```typescript
{
  "type": "assistant.message_final",
  "message": "I've fixed the authentication bug by adding input validation...",
  "metadata": {
    "tokens_used": 1234,
    "files_modified": 2,
    "tools_used": ["read_file", "search_symbols", "propose_diff"],
    "success": true
  }
}
```

### Error
```typescript
{
  "type": "server.error",
  "error": {
    "code": "RETRIEVAL_FAILED" | "MODEL_ERROR" | "POLICY_VIOLATION",
    "message": "Failed to retrieve relevant context",
    "details": { /* error-specific details */ },
    "recoverable": true | false
  }
}
```

### Session state update
```typescript
{
  "type": "session.state",
  "state": {
    "pending_patches": ["patch_abc123", "patch_def456"],
    "applied_patches": ["patch_xyz789"],
    "pending_approvals": ["req_abc123"],
    "current_step": 2,
    "total_steps": 5
  }
}
```

## Patch format

Unified diff (git-style), UTF-8:
```diff
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -23,5 +23,8 @@ function login(username, password) {
-  return db.query('SELECT * FROM users WHERE name = ' + username);
+  if (!username || !password) {
+    throw new Error('Invalid credentials');
+  }
+  return db.query('SELECT * FROM users WHERE name = ?', [username]);
}
```

Every patch proposal includes:
- Minimal, stable diff (prefer small hunks)
- File path (relative to workspace root)
- Per-hunk line numbers
- Rationale (why this change)
- Acceptance criteria (how to verify)

## Command execution modes

1. **local_terminal** (default, recommended):
   - Extension runs via VS Code Terminal API
   - User sees command in terminal
   - Output captured and sent to server
   
2. **server_runner** (optional, for sandboxing):
   - Server runs command in controlled environment
   - Output streamed to client
   - Time limits and resource constraints

Server MUST respect policy for each mode and request approval when required.

## Context gathering strategy

Extension automatically gathers:
- **Always**: Current file, selection, diagnostics, open editors
- **Conditionally** (based on slash command or task):
  - `/fix`: diagnostics + terminal output + git diff
  - `/test`: test files + source files + recent test output
  - `/explain`: just selection or current function scope
  - `/refactor`: current file + dependents + imports
  
Extension sends context in `client.user_message` without requiring server request.

## File watching and incremental indexing

Extension sends file change events to server for incremental indexing:
```typescript
{
  "type": "client.file_changes",
  "changes": [
    {
      "type": "created" | "modified" | "deleted",
      "file_path": "src/utils/new_helper.ts",
      "content_hash": "sha256:abc123...",
      "timestamp": "2025-12-30T10:35:12Z"
    }
  ]
}
```

Server updates index incrementally without full rebuild.
