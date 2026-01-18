import type {
  Agent,
  AgentVersion,
  Folder,
  KnowledgeItem,
  MessageSearchResult,
  ModelInfo,
  ModelStatus,
  KnowledgeStats,
  AceMetrics,
  SessionTrace,
  SearchResult,
  Session,
  SessionMessage,
  AceBullet,
  UploadAttachment,
  Workspace,
  WorkspacePolicy
} from "./types";
import type { StoredSettings } from "./storage";

async function apiFetch<T>(settings: StoredSettings, path: string, options?: RequestInit): Promise<T> {
  const base = settings.serverUrl.replace(/\/$/, "");
  const url = `${base}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  const extraHeaders = options?.headers;
  if (extraHeaders) {
    if (Array.isArray(extraHeaders)) {
      extraHeaders.forEach(([key, value]) => {
        headers[key] = value;
      });
    } else if (extraHeaders instanceof Headers) {
      extraHeaders.forEach((value, key) => {
        headers[key] = value;
      });
    } else {
      Object.assign(headers, extraHeaders as Record<string, string>);
    }
  }
  if (settings.token) {
    headers["Authorization"] = `Bearer ${settings.token}`;
  }

  const resp = await fetch(url, {
    ...options,
    headers
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Request failed: ${resp.status}`);
  }

  return (await resp.json()) as T;
}

export async function getWorkspaces(settings: StoredSettings): Promise<Workspace[]> {
  return apiFetch(settings, "/v1/workspaces");
}

export async function registerWorkspace(settings: StoredSettings, path: string, name?: string) {
  return apiFetch<Workspace>(settings, "/v1/workspaces/register", {
    method: "POST",
    body: JSON.stringify({ path, name })
  });
}

export async function getWorkspacePolicy(settings: StoredSettings, workspaceId: string): Promise<WorkspacePolicy> {
  return apiFetch(settings, `/v1/workspaces/${workspaceId}/policy`);
}

export async function updateWorkspacePolicy(
  settings: StoredSettings,
  workspaceId: string,
  payload: Partial<WorkspacePolicy>
): Promise<WorkspacePolicy> {
  return apiFetch(settings, `/v1/workspaces/${workspaceId}/policy`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function getFolders(settings: StoredSettings, workspaceId?: string): Promise<Folder[]> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return apiFetch(settings, `/v1/folders${query}`);
}

export async function createFolder(settings: StoredSettings, workspaceId: string, name: string, description?: string) {
  return apiFetch<Folder>(settings, "/v1/folders", {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId, name, description })
  });
}

export async function listSessions(settings: StoredSettings, workspaceId?: string, folderId?: string): Promise<Session[]> {
  const params = new URLSearchParams();
  if (workspaceId) params.set("workspace_id", workspaceId);
  if (folderId) params.set("folder_id", folderId);
  const query = params.toString();
  return apiFetch(settings, `/v1/sessions${query ? `?${query}` : ""}`);
}

export async function createSession(settings: StoredSettings, payload: Record<string, unknown>): Promise<Session> {
  return apiFetch(settings, "/v1/sessions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateSession(settings: StoredSettings, sessionId: string, payload: Record<string, unknown>): Promise<Session> {
  return apiFetch(settings, `/v1/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function getSessionMessages(settings: StoredSettings, sessionId: string): Promise<SessionMessage[]> {
  return apiFetch(settings, `/v1/sessions/${sessionId}/messages`);
}

export async function getModels(
  settings: StoredSettings,
  provider?: string,
  url?: string
): Promise<ModelInfo[]> {
  const params = new URLSearchParams();
  if (provider) params.set("provider", provider);
  if (url) params.set("url", url);
  const query = params.toString();
  const resp = await apiFetch<{ models: ModelInfo[] }>(settings, `/v1/models${query ? `?${query}` : ""}`);
  return resp.models;
}

export async function getModelStatus(settings: StoredSettings): Promise<ModelStatus> {
  return apiFetch(settings, "/v1/models/status");
}

export async function switchModel(settings: StoredSettings, payload: Record<string, unknown>) {
  return apiFetch(settings, "/v1/models/switch", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listAgents(settings: StoredSettings, workspaceId?: string): Promise<Agent[]> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return apiFetch(settings, `/v1/agents${query}`);
}

export async function createAgent(settings: StoredSettings, payload: Record<string, unknown>): Promise<Agent> {
  return apiFetch(settings, "/v1/agents", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateAgent(settings: StoredSettings, agentId: string, payload: Record<string, unknown>): Promise<Agent> {
  return apiFetch(settings, `/v1/agents/${agentId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function listAgentVersions(settings: StoredSettings, agentId: string): Promise<AgentVersion[]> {
  return apiFetch(settings, `/v1/agents/${agentId}/versions`);
}

export async function createAgentVersion(settings: StoredSettings, agentId: string, payload: Record<string, unknown>): Promise<AgentVersion> {
  return apiFetch(settings, `/v1/agents/${agentId}/versions`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function buildAgentConfig(settings: StoredSettings, description: string, baseConfig: Record<string, unknown>) {
  return apiFetch<{ config: Record<string, unknown>; raw?: string }>(settings, "/v1/agents/build", {
    method: "POST",
    body: JSON.stringify({ description, base_config: baseConfig })
  });
}

export async function searchSessions(settings: StoredSettings, workspaceId: string, query: string): Promise<SearchResult[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId, query });
  return apiFetch(settings, `/v1/search/sessions?${params.toString()}`);
}

export async function searchMessages(settings: StoredSettings, workspaceId: string, query: string): Promise<MessageSearchResult[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId, query });
  return apiFetch(settings, `/v1/search/messages?${params.toString()}`);
}

export async function listUploads(
  settings: StoredSettings,
  workspaceId: string,
  sessionId?: string,
  purpose?: string
): Promise<UploadAttachment[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (sessionId) params.set("session_id", sessionId);
  if (purpose) params.set("purpose", purpose);
  const resp = await apiFetch<{ attachments: UploadAttachment[] }>(settings, `/v1/uploads?${params.toString()}`);
  return resp.attachments;
}

export async function uploadFile(
  settings: StoredSettings,
  file: File,
  payload: Record<string, string | boolean | number | undefined>
) {
  const base = settings.serverUrl.replace(/\/$/, "");
  const url = `${base}/v1/uploads`;
  const form = new FormData();
  form.append("file", file);
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      form.append(key, String(value));
    }
  });

  const headers: Record<string, string> = {};
  if (settings.token) {
    headers["Authorization"] = `Bearer ${settings.token}`;
  }

  const resp = await fetch(url, {
    method: "POST",
    body: form,
    headers
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Upload failed: ${resp.status}`);
  }

  return resp.json() as Promise<Record<string, unknown>>;
}

export async function getKnowledgeStats(
  settings: StoredSettings,
  moduleId: string
): Promise<KnowledgeStats> {
  return apiFetch<KnowledgeStats>(settings, `/v1/knowledge/${moduleId}/stats`);
}

export async function listKnowledgeItems(
  settings: StoredSettings,
  moduleId: string,
  limit = 200,
  offset?: string | null
) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (offset) params.set("offset", offset);
  return apiFetch<{
    success: boolean;
    module_id: string;
    collection: string;
    items: KnowledgeItem[];
    next_offset?: string | null;
  }>(settings, `/v1/knowledge/${moduleId}/items?${params.toString()}`);
}

export async function getAceMetrics(settings: StoredSettings, moduleId: string): Promise<AceMetrics> {
  return apiFetch<AceMetrics>(settings, `/v1/ace/${moduleId}/metrics`);
}

export async function listAceBullets(settings: StoredSettings, moduleId: string) {
  return apiFetch<{ success: boolean; bullets: AceBullet[] }>(settings, `/v1/ace/${moduleId}/bullets`);
}

export async function updateFolder(
  settings: StoredSettings,
  folderId: string,
  payload: Record<string, unknown>
) {
  return apiFetch<Folder>(settings, `/v1/folders/${folderId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function deleteFolder(settings: StoredSettings, folderId: string) {
  return apiFetch(settings, `/v1/folders/${folderId}`, { method: "DELETE" });
}

export async function deleteSession(settings: StoredSettings, sessionId: string) {
  return apiFetch(settings, `/v1/sessions/${sessionId}`, { method: "DELETE" });
}

export async function getSessionTrace(settings: StoredSettings, sessionId: string) {
  return apiFetch<SessionTrace>(settings, `/v1/exports/sessions/${sessionId}/trace?format=json`);
}
