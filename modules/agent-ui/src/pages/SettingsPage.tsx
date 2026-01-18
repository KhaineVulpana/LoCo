import React, { useCallback, useEffect, useState } from "react";
import Button from "../components/Button";
import Input from "../components/Input";
import Select from "../components/Select";
import { useAppContext } from "../lib/appContext";
import {
  getModelStatus,
  getModels,
  getWorkspacePolicy,
  registerWorkspace,
  switchModel,
  updateWorkspacePolicy
} from "../lib/api";
import type { ModelInfo, ModelStatus } from "../lib/types";

const SettingsPage: React.FC = () => {
  const { settings, updateSettings, refreshWorkspaces } = useAppContext();
  const [serverUrl, setServerUrl] = useState(settings.serverUrl);
  const [token, setToken] = useState(settings.token || "");
  const [workspacePath, setWorkspacePath] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [policy, setPolicy] = useState<Record<string, unknown> | null>(null);

  const refreshModels = useCallback(async () => {
    try {
      const [list, status] = await Promise.all([
        getModels(settings, settings.modelProvider, settings.modelUrl || undefined),
        getModelStatus(settings)
      ]);
      setModels(list);
      setModelStatus(status);
      setModelError(null);
    } catch (error) {
      setModelError(error instanceof Error ? error.message : "Failed to load models.");
    }
  }, [settings]);

  useEffect(() => {
    refreshModels();
  }, [refreshModels]);

  useEffect(() => {
    if (!settings.workspaceId) return;
    getWorkspacePolicy(settings, settings.workspaceId).then(setPolicy).catch(() => setPolicy(null));
  }, [settings]);

  useEffect(() => {
    if (!modelStatus?.current_model?.url) return;
    if (!settings.modelUrl) {
      updateSettings({ modelUrl: modelStatus.current_model.url });
    }
  }, [modelStatus, settings.modelUrl, updateSettings]);

  const handleSave = useCallback(() => {
    updateSettings({
      serverUrl,
      token,
      moduleId: settings.moduleId,
      modelProvider: settings.modelProvider,
      modelName: settings.modelName,
      modelUrl: settings.modelUrl,
      contextWindow: settings.contextWindow,
      temperature: settings.temperature
    });
  }, [serverUrl, token, updateSettings, settings]);

  const handleRegisterWorkspace = useCallback(async () => {
    if (!workspacePath.trim()) return;
    await registerWorkspace(settings, workspacePath, workspaceName || undefined);
    await refreshWorkspaces();
    setWorkspacePath("");
    setWorkspaceName("");
  }, [settings, workspacePath, workspaceName, refreshWorkspaces]);

  const handleSwitchModel = useCallback(async () => {
    await switchModel(settings, {
      provider: settings.modelProvider,
      model_name: settings.modelName,
      url: settings.modelUrl,
      context_window: settings.contextWindow,
      temperature: settings.temperature
    });
    refreshModels();
  }, [settings, refreshModels]);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="muted">Connect devices, manage models, and register workspaces.</p>
        </div>
        <Button onClick={handleSave}>Save</Button>
      </header>

      <section className="panel">
        <h2>Connection</h2>
        <div className="grid-two">
          <Input
            label="Server URL"
            value={serverUrl}
            onChange={(event) => setServerUrl(event.target.value)}
          />
          <Input
            label="Access token"
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
        </div>
        <Select
          label="Default module"
          value={settings.moduleId || "vscode"}
          onChange={(event) => updateSettings({ moduleId: event.target.value })}
        >
          <option value="vscode">vscode</option>
          <option value="android">android</option>
          <option value="3d-gen">3d-gen</option>
        </Select>
      </section>

      <section className="panel">
        <h2>Workspaces</h2>
        <div className="grid-two">
          <Input
            label="Workspace path"
            value={workspacePath}
            onChange={(event) => setWorkspacePath(event.target.value)}
          />
          <Input
            label="Workspace name"
            value={workspaceName}
            onChange={(event) => setWorkspaceName(event.target.value)}
          />
        </div>
        <Button variant="outline" onClick={handleRegisterWorkspace}>
          Register Workspace
        </Button>
        {policy ? (
          <div className="policy-grid">
            <label className="toggle">
              <input
                type="checkbox"
                checked={Boolean(policy.network_enabled)}
                onChange={async (event) => {
                  if (!settings.workspaceId) return;
                  const updated = await updateWorkspacePolicy(settings, settings.workspaceId, {
                    network_enabled: event.target.checked
                  });
                  setPolicy(updated);
                }}
              />
              <span>Enable network tools</span>
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={Boolean(policy.auto_approve_tests)}
                onChange={async (event) => {
                  if (!settings.workspaceId) return;
                  const updated = await updateWorkspacePolicy(settings, settings.workspaceId, {
                    auto_approve_tests: event.target.checked
                  });
                  setPolicy(updated);
                }}
              />
              <span>Auto-approve tests</span>
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={Boolean(policy.auto_approve_simple_changes)}
                onChange={async (event) => {
                  if (!settings.workspaceId) return;
                  const updated = await updateWorkspacePolicy(settings, settings.workspaceId, {
                    auto_approve_simple_changes: event.target.checked
                  });
                  setPolicy(updated);
                }}
              />
              <span>Auto-approve simple changes</span>
            </label>
          </div>
        ) : (
          <p className="muted">Workspace policy not available.</p>
        )}
      </section>

      <section className="panel">
        <h2>Model Manager</h2>
        <div className="grid-two">
          <Select
            label="Provider"
            value={settings.modelProvider || "ollama"}
            onChange={(event) => updateSettings({ modelProvider: event.target.value })}
          >
            <option value="ollama">ollama</option>
            <option value="vllm">vllm</option>
            <option value="llamacpp">llamacpp</option>
          </Select>
          <Select
            label="Model"
            value={settings.modelName || ""}
            onChange={(event) => updateSettings({ modelName: event.target.value })}
          >
            <option value="">Select model</option>
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.display_name || model.id}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid-two">
          <Input
            label="Model URL"
            value={settings.modelUrl || ""}
            hint="Leave blank to use the server default."
            onChange={(event) => updateSettings({ modelUrl: event.target.value })}
          />
          <Input
            label="Context window"
            type="number"
            value={settings.contextWindow?.toString() || ""}
            onChange={(event) =>
              updateSettings({
                contextWindow: event.target.value ? Number(event.target.value) : undefined
              })
            }
          />
        </div>
        <Input
          label="Temperature"
          type="number"
          step="0.1"
          value={settings.temperature?.toString() || ""}
          onChange={(event) =>
            updateSettings({
              temperature: event.target.value ? Number(event.target.value) : undefined
            })
          }
        />
        {modelError ? <p className="muted">{modelError}</p> : null}
        <Button onClick={handleSwitchModel} disabled={!settings.modelName}>
          Switch Model
        </Button>
        {modelStatus ? (
          <div className="status-card">
            <strong>Status: {modelStatus.is_loaded ? "Loaded" : "Not loaded"}</strong>
            <p className="muted">Current: {modelStatus.current_model?.display_name}</p>
          </div>
        ) : null}
      </section>
    </div>
  );
};

export default SettingsPage;
