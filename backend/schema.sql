-- LoCo Agent Database Schema

-- Workspaces
CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_indexed_at TEXT,
  index_status TEXT NOT NULL DEFAULT 'pending',
  index_progress REAL DEFAULT 0.0,
  total_files INTEGER DEFAULT 0,
  indexed_files INTEGER DEFAULT 0,
  total_chunks INTEGER DEFAULT 0,
  deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_workspaces_path ON workspaces(path) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(index_status) WHERE deleted_at IS NULL;

-- Workspace Policies
CREATE TABLE IF NOT EXISTS workspace_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  allowed_read_globs TEXT NOT NULL DEFAULT '["**/*"]',
  allowed_write_globs TEXT NOT NULL DEFAULT '["**/*"]',
  blocked_globs TEXT NOT NULL DEFAULT '[".git/**", "node_modules/**"]',
  command_approval TEXT NOT NULL DEFAULT 'prompt',
  allowed_commands TEXT NOT NULL DEFAULT '[]',
  blocked_commands TEXT NOT NULL DEFAULT '["rm -rf", "sudo", "curl"]',
  network_enabled INTEGER NOT NULL DEFAULT 0,
  auto_approve_simple_changes INTEGER NOT NULL DEFAULT 0,
  auto_approve_tests INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policies_workspace ON workspace_policies(workspace_id);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  title TEXT,
  model_provider TEXT NOT NULL,
  model_name TEXT NOT NULL,
  context_window INTEGER NOT NULL,
  context_strategy TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  deleted_at TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  current_step INTEGER DEFAULT 0,
  total_steps INTEGER DEFAULT 0,
  total_messages INTEGER DEFAULT 0,
  total_patches_proposed INTEGER DEFAULT 0,
  total_patches_applied INTEGER DEFAULT 0,
  total_commands_run INTEGER DEFAULT 0,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_workspace ON sessions(workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC) WHERE deleted_at IS NULL;

-- Session Messages
CREATE TABLE IF NOT EXISTS session_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  context_json TEXT,
  context_hash TEXT,
  tokens_prompt INTEGER,
  tokens_completion INTEGER,
  tokens_total INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id, created_at);

-- Tool Events
CREATE TABLE IF NOT EXISTS tool_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  args_json TEXT NOT NULL,
  result_json TEXT,
  error_json TEXT,
  status TEXT NOT NULL,
  duration_ms INTEGER,
  requires_approval INTEGER NOT NULL DEFAULT 0,
  approval_status TEXT,
  approved_by TEXT,
  approved_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tool_events_session ON tool_events(session_id, created_at);

-- Patch Events
CREATE TABLE IF NOT EXISTS patch_events (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  base_hash TEXT NOT NULL,
  proposed_hash TEXT,
  actual_hash TEXT,
  diff TEXT NOT NULL,
  rationale TEXT,
  acceptance_criteria TEXT,
  status TEXT NOT NULL,
  error_message TEXT,
  proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
  decided_at TEXT,
  applied_at TEXT,
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_patch_events_session ON patch_events(session_id, proposed_at);
CREATE INDEX IF NOT EXISTS idx_patch_events_file ON patch_events(workspace_id, file_path);

-- Files
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  language TEXT,
  size_bytes INTEGER NOT NULL,
  line_count INTEGER,
  index_status TEXT NOT NULL DEFAULT 'pending',
  parse_error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_accessed_at TEXT,
  access_count INTEGER DEFAULT 0,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  UNIQUE (workspace_id, path)
);

CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(workspace_id);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(workspace_id, path);

-- Chunks
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  workspace_id TEXT NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  start_offset INTEGER NOT NULL,
  end_offset INTEGER NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  tokens_estimated INTEGER,
  chunk_type TEXT NOT NULL,
  parent_chunk_id INTEGER,
  vector_id TEXT,
  embedding_model TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_chunk_id) REFERENCES chunks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);

-- Symbols
CREATE TABLE IF NOT EXISTS symbols (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  workspace_id TEXT NOT NULL,
  chunk_id INTEGER,
  name TEXT NOT NULL,
  qualified_name TEXT,
  kind TEXT NOT NULL,
  signature TEXT,
  line INTEGER NOT NULL,
  column INTEGER NOT NULL,
  end_line INTEGER,
  end_column INTEGER,
  parent_symbol_id INTEGER,
  is_exported INTEGER DEFAULT 0,
  is_private INTEGER DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE SET NULL,
  FOREIGN KEY (parent_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(workspace_id, name);

-- ACE Artifacts
CREATE TABLE IF NOT EXISTS ace_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  scope TEXT NOT NULL,
  scope_path TEXT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT,
  confidence REAL DEFAULT 1.0,
  last_verified_at TEXT,
  times_retrieved INTEGER DEFAULT 0,
  times_applied INTEGER DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_by_session_id TEXT,
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by_session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ace_workspace ON ace_artifacts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ace_type ON ace_artifacts(artifact_type);

-- Embedding Cache
CREATE TABLE IF NOT EXISTS embedding_cache (
  content_hash TEXT PRIMARY KEY,
  embedding_blob BLOB NOT NULL,
  embedding_model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at TEXT NOT NULL DEFAULT (datetime('now')),
  use_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_embedding_cache_model ON embedding_cache(embedding_model);

-- Schema Migrations
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_migrations (version) VALUES (1);
