export type StoredSettings = {
  serverUrl: string;
  token?: string;
  workspaceId?: string;
  agentId?: string;
  folderId?: string;
  moduleId?: string;
  modelProvider?: string;
  modelName?: string;
  modelUrl?: string;
  contextWindow?: number;
  temperature?: number;
};

const STORAGE_KEY = "loco.agent.settings";

export const defaultSettings: StoredSettings = {
  serverUrl: window.location.origin,
  moduleId: "vscode",
  modelProvider: "ollama",
  modelName: "",
  modelUrl: "",
  contextWindow: 16384,
  temperature: 0.7
};

export function loadSettings(): StoredSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { ...defaultSettings };
    }
    const parsed = JSON.parse(raw) as StoredSettings;
    return { ...defaultSettings, ...parsed };
  } catch {
    return { ...defaultSettings };
  }
}

export function saveSettings(settings: StoredSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
