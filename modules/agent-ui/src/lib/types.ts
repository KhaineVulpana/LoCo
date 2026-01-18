export type Workspace = {
  id: string;
  path: string;
  name: string;
  created_at: string;
  last_indexed_at?: string | null;
  index_status: string;
  index_progress: number;
  total_files: number;
  indexed_files: number;
  total_chunks: number;
};

export type WorkspacePolicy = {
  allowed_read_globs: string[];
  allowed_write_globs: string[];
  blocked_globs: string[];
  command_approval: "always" | "never" | "prompt";
  allowed_commands: string[];
  blocked_commands: string[];
  network_enabled: boolean;
  auto_approve_simple_changes: boolean;
  auto_approve_tests: boolean;
  auto_approve_tools: string[];
};

export type Folder = {
  id: string;
  workspace_id: string;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
};

export type Session = {
  id: string;
  workspace_id: string;
  folder_id?: string | null;
  agent_id?: string | null;
  title?: string | null;
  model_provider: string;
  model_name: string;
  model_url?: string | null;
  context_window: number;
  temperature: number;
  created_at: string;
  status: string;
};

export type SessionMessage = {
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
  metadata?: Record<string, unknown> | null;
};

export type AgentVersion = {
  id: string;
  version: number;
  title?: string | null;
  config: Record<string, unknown>;
  created_at: string;
};

export type Agent = {
  id: string;
  workspace_id: string;
  name: string;
  description?: string | null;
  active_version_id?: string | null;
  active_version?: AgentVersion | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type ModelInfo = {
  id: string;
  provider: string;
  url: string;
  display_name?: string | null;
};

export type ModelStatus = {
  is_loaded: boolean;
  current_model?: {
    provider: string;
    model_name: string;
    url: string;
    context_window: number;
    temperature: number;
    display_name: string;
  } | null;
};

export type UploadAttachment = {
  id: string;
  workspace_id: string;
  session_id?: string | null;
  agent_id?: string | null;
  file_name: string;
  mime_type?: string | null;
  size_bytes: number;
  storage_path: string;
  content_hash?: string | null;
  purpose: string;
  created_at: string;
};

export type KnowledgeStats = {
  success: boolean;
  stats: Record<string, unknown>;
};

export type AceMetrics = {
  success: boolean;
  module_id: string;
  total_bullets: number;
  sections: Record<string, number>;
  helpful_total: number;
  harmful_total: number;
  average_score: number;
};

export type KnowledgeItem = {
  id: string;
  payload: Record<string, unknown>;
};

export type AceBullet = {
  id: string;
  section: string;
  content: string;
  helpful_count: number;
  harmful_count: number;
  metadata?: Record<string, unknown>;
};

export type ToolEvent = {
  tool_name: string;
  args?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  status: string;
  duration_ms?: number | null;
  requires_approval?: boolean;
  approval_status?: string | null;
  created_at: string;
};

export type SessionTrace = {
  session: Session & { updated_at?: string };
  prompt?: SessionMessage | null;
  assistant?: SessionMessage | null;
  tool_events: ToolEvent[];
};

export type SearchResult = {
  session_id: string;
  title?: string | null;
  last_message_at?: string | null;
  snippet?: string | null;
};

export type MessageSearchResult = {
  session_id: string;
  session_title?: string | null;
  role: string;
  content: string;
  created_at: string;
};

export type ChatItem =
  | { kind: "message"; id: string; role: string; content: string; timestamp?: string }
  | { kind: "tool"; id: string; tool: string; content: string }
  | { kind: "status"; id: string; label: string; detail?: string }
  | { kind: "error"; id: string; label: string; detail?: string };

export type ServerInfo = {
  version?: string;
  model?: {
    provider?: string;
    model_name?: string;
    capabilities?: string[];
  };
  capabilities?: string[];
};
