import React, { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { Agent, Folder, Workspace } from "./types";
import { loadSettings, saveSettings } from "./storage";
import type { StoredSettings } from "./storage";
import { getFolders, getWorkspaces, listAgents } from "./api";

export type AppContextValue = {
  settings: StoredSettings;
  updateSettings: (updates: Partial<StoredSettings>) => void;
  workspaces: Workspace[];
  folders: Folder[];
  agents: Agent[];
  refreshWorkspaces: () => Promise<void>;
  refreshFolders: (workspaceId?: string) => Promise<void>;
  refreshAgents: (workspaceId?: string) => Promise<void>;
};

const AppContext = createContext<AppContextValue | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<StoredSettings>(loadSettings());
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);

  const updateSettings = useCallback((updates: Partial<StoredSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...updates };
      saveSettings(next);
      return next;
    });
  }, []);

  const refreshWorkspaces = useCallback(async () => {
    const data = await getWorkspaces(settings);
    setWorkspaces(data);
    if (!settings.workspaceId && data[0]) {
      updateSettings({ workspaceId: data[0].id });
    }
  }, [settings, updateSettings]);

  const refreshFolders = useCallback(
    async (workspaceId?: string) => {
      if (!workspaceId && !settings.workspaceId) {
        setFolders([]);
        return;
      }
      const data = await getFolders(settings, workspaceId ?? settings.workspaceId);
      setFolders(data);
    },
    [settings]
  );

  const refreshAgents = useCallback(
    async (workspaceId?: string) => {
      if (!workspaceId && !settings.workspaceId) {
        setAgents([]);
        return;
      }
      const data = await listAgents(settings, workspaceId ?? settings.workspaceId);
      setAgents(data);
      if (!settings.agentId && data[0]) {
        updateSettings({ agentId: data[0].id });
      }
    },
    [settings, updateSettings]
  );

  const value = useMemo(
    () => ({
      settings,
      updateSettings,
      workspaces,
      folders,
      agents,
      refreshWorkspaces,
      refreshFolders,
      refreshAgents
    }),
    [settings, updateSettings, workspaces, folders, agents, refreshWorkspaces, refreshFolders, refreshAgents]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useAppContext must be used within AppProvider");
  }
  return ctx;
}
