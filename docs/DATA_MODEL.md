# Data Model (Complete SQL Schema)

## Schema Design Principles
- Normalized for consistency, denormalized where needed for performance
- Audit trail (append-only tool_events)
- Soft deletes (deleted_at timestamp) for sessions and workspaces
- Timestamps for all mutable entities
- Foreign keys with CASCADE where appropriate

---

## Core Tables

### workspaces
Registered workspace roots (one per VS Code workspace folder)

```sql
CREATE TABLE workspaces (
  id TEXT PRIMARY KEY,  -- uuid v4
  path TEXT NOT NULL UNIQUE,  -- absolute path to workspace root
  name TEXT NOT NULL,  -- user-friendly name (defaults to folder name)
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_indexed_at TEXT,  -- when indexing last completed
  index_status TEXT NOT NULL DEFAULT 'pending',  -- pending, indexing, ready, failed, text_only
  index_progress REAL DEFAULT 0.0,  -- 0.0 to 1.0
  total_files INTEGER DEFAULT 0,
  indexed_files INTEGER DEFAULT 0,
  total_chunks INTEGER DEFAULT 0,
  deleted_at TEXT  -- soft delete
);

CREATE INDEX idx_workspaces_path ON workspaces(path) WHERE deleted_at IS NULL;
CREATE INDEX idx_workspaces_status ON workspaces(index_status) WHERE deleted_at IS NULL;
```

### workspace_policies
Security policies per workspace

```sql
CREATE TABLE workspace_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  
  -- Read/write permissions (glob patterns)
  allowed_read_globs TEXT NOT NULL DEFAULT '["**/*"]',  -- JSON array
  allowed_write_globs TEXT NOT NULL DEFAULT '["**/*"]',  -- JSON array
  blocked_globs TEXT NOT NULL DEFAULT '[".git/**", "node_modules/**"]',  -- JSON array
  
  -- Command execution policy
  command_approval TEXT NOT NULL DEFAULT 'prompt',  -- always, never, prompt
  allowed_commands TEXT NOT NULL DEFAULT '[]',  -- JSON array of allowed commands
  blocked_commands TEXT NOT NULL DEFAULT '["rm -rf", "sudo", "curl"]',  -- JSON array
  
  -- Network access
  network_enabled INTEGER NOT NULL DEFAULT 0,  -- boolean
  
  -- Auto-approval thresholds
  auto_approve_simple_changes INTEGER NOT NULL DEFAULT 0,  -- < 10 lines
  auto_approve_tests INTEGER NOT NULL DEFAULT 0,  -- test file changes
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_policies_workspace ON workspace_policies(workspace_id);
```

---

## Session Management

### sessions
Chat sessions (one per sidebar conversation)

```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,  -- uuid v4
  workspace_id TEXT NOT NULL,
  title TEXT,  -- auto-generated from first message
  model_provider TEXT NOT NULL,  -- ollama, vllm, llamacpp
  model_name TEXT NOT NULL,  -- codellama:13b, etc.
  context_window INTEGER NOT NULL,  -- detected from model
  context_strategy TEXT NOT NULL,  -- minimal, balanced, full
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  deleted_at TEXT,  -- soft delete
  
  -- Session state
  status TEXT NOT NULL DEFAULT 'active',  -- active, cancelled, completed, error
  current_step INTEGER DEFAULT 0,
  total_steps INTEGER DEFAULT 0,
  
  -- Metadata
  total_messages INTEGER DEFAULT 0,
  total_patches_proposed INTEGER DEFAULT 0,
  total_patches_applied INTEGER DEFAULT 0,
  total_commands_run INTEGER DEFAULT 0,
  
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_workspace ON sessions(workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_sessions_status ON sessions(status) WHERE deleted_at IS NULL;
```

### session_messages
Messages in a session (user and assistant)

```sql
CREATE TABLE session_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,  -- user, assistant, system
  content TEXT NOT NULL,
  
  -- Context snapshot (for user messages)
  context_json TEXT,  -- full context structure as JSON
  context_hash TEXT,  -- SHA-256 of context (deduplication)
  
  -- Token usage (for assistant messages)
  tokens_prompt INTEGER,
  tokens_completion INTEGER,
  tokens_total INTEGER,
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_session ON session_messages(session_id, created_at);
CREATE INDEX idx_messages_context_hash ON session_messages(context_hash);
```

---

## Audit Logs

### tool_events
Append-only audit log of all tool executions

```sql
CREATE TABLE tool_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  
  tool_name TEXT NOT NULL,  -- read_file, search_symbols, propose_diff, execute_command
  args_json TEXT NOT NULL,  -- JSON of arguments
  result_json TEXT,  -- JSON of result (if successful)
  error_json TEXT,  -- JSON of error (if failed)
  
  status TEXT NOT NULL,  -- started, completed, failed, cancelled
  duration_ms INTEGER,  -- execution time
  
  -- Approval tracking
  requires_approval INTEGER NOT NULL DEFAULT 0,
  approval_status TEXT,  -- pending, approved, rejected
  approved_by TEXT,  -- user or auto
  approved_at TEXT,
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX idx_tool_events_session ON tool_events(session_id, created_at);
CREATE INDEX idx_tool_events_workspace ON tool_events(workspace_id, created_at);
CREATE INDEX idx_tool_events_tool_name ON tool_events(tool_name);
CREATE INDEX idx_tool_events_status ON tool_events(status);
CREATE INDEX idx_tool_events_approval ON tool_events(approval_status) WHERE requires_approval = 1;
```

### patch_events
Track all proposed and applied patches

```sql
CREATE TABLE patch_events (
  id TEXT PRIMARY KEY,  -- patch_id (uuid)
  session_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  
  file_path TEXT NOT NULL,  -- relative to workspace root
  base_hash TEXT NOT NULL,  -- SHA-256 before patch
  proposed_hash TEXT,  -- SHA-256 after patch (proposed)
  actual_hash TEXT,  -- SHA-256 after patch (actual, if applied)
  
  diff TEXT NOT NULL,  -- unified diff
  rationale TEXT,
  acceptance_criteria TEXT,  -- JSON array
  
  status TEXT NOT NULL,  -- proposed, accepted, rejected, applied, failed, conflict
  error_message TEXT,
  
  proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
  decided_at TEXT,  -- when user accepted/rejected
  applied_at TEXT,  -- when actually applied
  
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX idx_patch_events_session ON patch_events(session_id, proposed_at);
CREATE INDEX idx_patch_events_file ON patch_events(workspace_id, file_path);
CREATE INDEX idx_patch_events_status ON patch_events(status);
```

### command_events
Track all command executions

```sql
CREATE TABLE command_events (
  id TEXT PRIMARY KEY,  -- command_id (uuid)
  session_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  
  command TEXT NOT NULL,
  working_directory TEXT NOT NULL,
  environment_json TEXT,  -- JSON of env vars
  
  exit_code INTEGER,
  stdout TEXT,  -- truncated to 100KB
  stderr TEXT,  -- truncated to 100KB
  duration_ms INTEGER,
  
  status TEXT NOT NULL,  -- requested, approved, running, completed, failed, cancelled
  error_message TEXT,
  
  -- Approval tracking
  requires_approval INTEGER NOT NULL DEFAULT 1,
  approval_status TEXT,  -- pending, approved, rejected
  approved_at TEXT,
  
  requested_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT,
  completed_at TEXT,
  
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX idx_command_events_session ON command_events(session_id, requested_at);
CREATE INDEX idx_command_events_workspace ON command_events(workspace_id);
CREATE INDEX idx_command_events_status ON command_events(status);
```

---

## File Indexing

### files
Indexed files in workspace

```sql
CREATE TABLE files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  path TEXT NOT NULL,  -- relative to workspace root
  
  content_hash TEXT NOT NULL,  -- SHA-256 of content
  language TEXT,  -- detected language (typescript, python, etc.)
  size_bytes INTEGER NOT NULL,
  line_count INTEGER,
  
  -- Index status
  index_status TEXT NOT NULL DEFAULT 'pending',  -- pending, indexed, failed, partially_indexed
  parse_error TEXT,  -- if tree-sitter parse failed
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_accessed_at TEXT,  -- for tiered storage
  access_count INTEGER DEFAULT 0,
  
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  UNIQUE (workspace_id, path)
);

CREATE INDEX idx_files_workspace ON files(workspace_id);
CREATE INDEX idx_files_path ON files(workspace_id, path);
CREATE INDEX idx_files_hash ON files(content_hash);
CREATE INDEX idx_files_language ON files(workspace_id, language);
CREATE INDEX idx_files_access ON files(last_accessed_at DESC);  -- for tiered storage
```

### chunks
Code/text chunks from files

```sql
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  workspace_id TEXT NOT NULL,
  
  -- Chunk location
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  start_offset INTEGER NOT NULL,  -- byte offset
  end_offset INTEGER NOT NULL,
  
  -- Chunk content
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,  -- SHA-256 for deduplication
  tokens_estimated INTEGER,
  
  -- Chunk type
  chunk_type TEXT NOT NULL,  -- function, class, method, top_level, text, heuristic
  parent_chunk_id INTEGER,  -- for nested chunks (method in class)
  
  -- Vector storage reference
  vector_id TEXT,  -- ID in Qdrant
  embedding_model TEXT,  -- model used for embedding
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_chunk_id) REFERENCES chunks(id) ON DELETE SET NULL
);

CREATE INDEX idx_chunks_file ON chunks(file_id);
CREATE INDEX idx_chunks_workspace ON chunks(workspace_id);
CREATE INDEX idx_chunks_content_hash ON chunks(content_hash);
CREATE INDEX idx_chunks_vector_id ON chunks(vector_id);
CREATE INDEX idx_chunks_type ON chunks(chunk_type);
```

### symbols
Extracted symbols (functions, classes, variables)

```sql
CREATE TABLE symbols (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  workspace_id TEXT NOT NULL,
  chunk_id INTEGER,  -- reference to chunk containing this symbol
  
  name TEXT NOT NULL,
  qualified_name TEXT,  -- full.path.to.symbol
  kind TEXT NOT NULL,  -- function, class, method, variable, constant, type
  signature TEXT,  -- function(arg1: type1) -> return_type
  
  line INTEGER NOT NULL,
  column INTEGER NOT NULL,
  end_line INTEGER,
  end_column INTEGER,
  
  -- Relationships
  parent_symbol_id INTEGER,  -- for methods in classes
  is_exported INTEGER DEFAULT 0,
  is_private INTEGER DEFAULT 0,
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE SET NULL,
  FOREIGN KEY (parent_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE INDEX idx_symbols_file ON symbols(file_id);
CREATE INDEX idx_symbols_workspace ON symbols(workspace_id);
CREATE INDEX idx_symbols_name ON symbols(workspace_id, name);
CREATE INDEX idx_symbols_kind ON symbols(workspace_id, kind);
CREATE INDEX idx_symbols_qualified ON symbols(qualified_name);

-- Full-text search for symbols
CREATE VIRTUAL TABLE symbols_fts USING fts5(
  name,
  qualified_name,
  signature,
  content='symbols',
  content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER symbols_fts_insert AFTER INSERT ON symbols BEGIN
  INSERT INTO symbols_fts(rowid, name, qualified_name, signature)
  VALUES (new.id, new.name, new.qualified_name, new.signature);
END;

CREATE TRIGGER symbols_fts_delete AFTER DELETE ON symbols BEGIN
  DELETE FROM symbols_fts WHERE rowid = old.id;
END;

CREATE TRIGGER symbols_fts_update AFTER UPDATE ON symbols BEGIN
  DELETE FROM symbols_fts WHERE rowid = old.id;
  INSERT INTO symbols_fts(rowid, name, qualified_name, signature)
  VALUES (new.id, new.name, new.qualified_name, new.signature);
END;
```

### file_dependencies
Import/export relationships between files

```sql
CREATE TABLE file_dependencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  
  source_file_id INTEGER NOT NULL,  -- file that imports
  target_file_id INTEGER NOT NULL,  -- file being imported
  
  import_type TEXT NOT NULL,  -- import, require, include
  imported_symbols TEXT,  -- JSON array of specific symbols (e.g., ["foo", "bar"])
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (source_file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (target_file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  UNIQUE (source_file_id, target_file_id)
);

CREATE INDEX idx_deps_source ON file_dependencies(source_file_id);
CREATE INDEX idx_deps_target ON file_dependencies(target_file_id);
CREATE INDEX idx_deps_workspace ON file_dependencies(workspace_id);
```

### file_summaries
AI-generated summaries of files (optional, for large context windows)

```sql
CREATE TABLE file_summaries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  workspace_id TEXT NOT NULL,
  
  summary TEXT NOT NULL,  -- 2-3 sentence summary
  key_functions TEXT,  -- JSON array of important function names
  dependencies TEXT,  -- JSON array of key dependencies
  
  generated_by_model TEXT NOT NULL,  -- model that generated summary
  generated_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  UNIQUE (file_id)
);

CREATE INDEX idx_summaries_file ON file_summaries(file_id);
```

---

## ACE (Agentic Context Engineering)

### ace_artifacts
Learned project patterns and rules

```sql
CREATE TABLE ace_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  
  artifact_type TEXT NOT NULL,  -- constitution, runbook, gotcha, decision, glossary
  scope TEXT NOT NULL,  -- workspace, module, file
  scope_path TEXT,  -- specific module or file path
  
  title TEXT NOT NULL,
  content TEXT NOT NULL,  -- bullet points (JSON array of strings)
  
  -- Metadata
  tags TEXT,  -- JSON array for retrieval
  confidence REAL DEFAULT 1.0,  -- 0.0 to 1.0
  last_verified_at TEXT,
  times_retrieved INTEGER DEFAULT 0,
  times_applied INTEGER DEFAULT 0,
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_by_session_id TEXT,  -- which session created this
  
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by_session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_ace_workspace ON ace_artifacts(workspace_id);
CREATE INDEX idx_ace_type ON ace_artifacts(artifact_type);
CREATE INDEX idx_ace_scope ON ace_artifacts(scope, scope_path);
CREATE INDEX idx_ace_confidence ON ace_artifacts(confidence DESC);

-- Full-text search for ACE artifacts
CREATE VIRTUAL TABLE ace_artifacts_fts USING fts5(
  title,
  content,
  tags,
  content='ace_artifacts',
  content_rowid='id'
);
```

### ace_artifact_versions
Version history for artifacts (track evolution)

```sql
CREATE TABLE ace_artifact_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  artifact_id INTEGER NOT NULL,
  
  version INTEGER NOT NULL,
  content TEXT NOT NULL,  -- content at this version
  confidence REAL NOT NULL,
  
  change_reason TEXT,  -- why was this updated
  changed_by_session_id TEXT,
  
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  
  FOREIGN KEY (artifact_id) REFERENCES ace_artifacts(id) ON DELETE CASCADE,
  UNIQUE (artifact_id, version)
);

CREATE INDEX idx_ace_versions_artifact ON ace_artifact_versions(artifact_id, version DESC);
```

---

## Caching Tables

### embedding_cache
Cache embeddings by content hash

```sql
CREATE TABLE embedding_cache (
  content_hash TEXT PRIMARY KEY,
  embedding_blob BLOB NOT NULL,  -- numpy array serialized
  embedding_model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at TEXT NOT NULL DEFAULT (datetime('now')),
  use_count INTEGER DEFAULT 0
);

CREATE INDEX idx_embedding_cache_model ON embedding_cache(embedding_model);
CREATE INDEX idx_embedding_cache_last_used ON embedding_cache(last_used_at);

-- Periodically clean old unused embeddings
-- DELETE FROM embedding_cache WHERE last_used_at < datetime('now', '-30 days');
```

---

## Migrations

### schema_migrations
Track applied migrations

```sql
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Initial version
INSERT INTO schema_migrations (version) VALUES (1);
```

---

## Views (Convenience Queries)

### Recent sessions view
```sql
CREATE VIEW v_recent_sessions AS
SELECT 
  s.id,
  s.title,
  s.workspace_id,
  w.name as workspace_name,
  s.model_name,
  s.status,
  s.total_messages,
  s.total_patches_applied,
  s.created_at,
  s.updated_at,
  (SELECT content FROM session_messages 
   WHERE session_id = s.id AND role = 'user' 
   ORDER BY created_at ASC LIMIT 1) as first_message
FROM sessions s
JOIN workspaces w ON s.workspace_id = w.id
WHERE s.deleted_at IS NULL
ORDER BY s.updated_at DESC;
```

### Workspace statistics view
```sql
CREATE VIEW v_workspace_stats AS
SELECT 
  w.id,
  w.name,
  w.path,
  w.index_status,
  w.total_files,
  w.indexed_files,
  w.total_chunks,
  COUNT(DISTINCT s.id) as total_sessions,
  COUNT(DISTINCT f.language) as language_count,
  SUM(f.size_bytes) as total_size_bytes,
  w.last_indexed_at,
  w.updated_at
FROM workspaces w
LEFT JOIN sessions s ON w.id = s.workspace_id AND s.deleted_at IS NULL
LEFT JOIN files f ON w.id = f.workspace_id
WHERE w.deleted_at IS NULL
GROUP BY w.id;
```

### Pending approvals view
```sql
CREATE VIEW v_pending_approvals AS
SELECT 
  'patch' as approval_type,
  p.id,
  p.session_id,
  p.workspace_id,
  p.file_path,
  p.proposed_at as requested_at
FROM patch_events p
WHERE p.status = 'proposed'

UNION ALL

SELECT 
  'command' as approval_type,
  c.id,
  c.session_id,
  c.workspace_id,
  c.command as file_path,
  c.requested_at
FROM command_events c
WHERE c.approval_status = 'pending';
```

---

## Database Maintenance

### Vacuum and optimize (run periodically)
```sql
-- Reclaim space
VACUUM;

-- Update statistics for query planner
ANALYZE;
```

### Archive old data
```sql
-- Archive sessions older than 30 days
CREATE TABLE IF NOT EXISTS sessions_archive AS 
  SELECT * FROM sessions WHERE 1=0;

INSERT INTO sessions_archive 
SELECT * FROM sessions 
WHERE updated_at < datetime('now', '-30 days');

UPDATE sessions 
SET deleted_at = datetime('now')
WHERE updated_at < datetime('now', '-30 days');

-- Clean up soft-deleted records after 90 days
DELETE FROM sessions 
WHERE deleted_at < datetime('now', '-90 days');

DELETE FROM workspaces 
WHERE deleted_at < datetime('now', '-90 days');
```

### Clean embedding cache
```sql
-- Remove embeddings not used in 30 days
DELETE FROM embedding_cache 
WHERE last_used_at < datetime('now', '-30 days');
```
