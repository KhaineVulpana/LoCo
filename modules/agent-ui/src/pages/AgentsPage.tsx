import React, { useCallback, useEffect, useState } from "react";
import Button from "../components/Button";
import Input from "../components/Input";
import Textarea from "../components/Textarea";
import { useAppContext } from "../lib/appContext";
import { createAgent, listAgents, updateAgent } from "../lib/api";
import type { Agent } from "../lib/types";

const AgentsPage: React.FC = () => {
  const { settings, updateSettings } = useAppContext();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [toolAllowlist, setToolAllowlist] = useState("");

  const refresh = useCallback(async () => {
    if (!settings.workspaceId) return;
    const data = await listAgents(settings, settings.workspaceId);
    setAgents(data);
  }, [settings]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCreate = useCallback(async () => {
    if (!settings.workspaceId || !name.trim()) return;
    const config = {
      system_prompt: systemPrompt,
      tools: {
        allowlist: toolAllowlist
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      },
      rag: { enabled: true, limit: 5, score_threshold: 0.6 },
      ace: { enabled: true, limit: 5, score_threshold: 0.5 },
      model: {
        provider: settings.modelProvider || "ollama",
        model_name: settings.modelName || "",
        url: settings.modelUrl || "",
        context_window: settings.contextWindow || 16384,
        temperature: settings.temperature || 0.7
      }
    };
    const newAgent = await createAgent(settings, {
      workspace_id: settings.workspaceId,
      name,
      description,
      config
    });
    setAgents((prev) => [newAgent, ...prev]);
    setName("");
    setDescription("");
    setSystemPrompt("");
    setToolAllowlist("");
    updateSettings({ agentId: newAgent.id });
  }, [settings, name, description, systemPrompt, toolAllowlist, updateSettings]);

  const archiveAgent = useCallback(
    async (agentId: string) => {
      const updated = await updateAgent(settings, agentId, { is_archived: true });
      setAgents((prev) => prev.map((agent) => (agent.id === agentId ? updated : agent)));
    },
    [settings]
  );

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <h1>Agents</h1>
          <p className="muted">Build reusable agents with dedicated tool policies.</p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          Refresh
        </Button>
      </header>

      <section className="panel">
        <h2>Create Agent</h2>
        <div className="grid-two">
          <Input label="Name" value={name} onChange={(event) => setName(event.target.value)} />
          <Input
            label="Description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        <Textarea
          label="System prompt"
          value={systemPrompt}
          onChange={(event) => setSystemPrompt(event.target.value)}
          placeholder="Define personality, constraints, and outputs."
        />
        <Input
          label="Tool allowlist (comma-separated)"
          value={toolAllowlist}
          onChange={(event) => setToolAllowlist(event.target.value)}
          placeholder="read_file, write_file, run_tests"
        />
        <Button onClick={handleCreate} disabled={!name.trim()}>
          Create Agent
        </Button>
      </section>

      <section className="panel">
        <h2>Agent Library</h2>
        {agents.length === 0 ? (
          <p className="muted">No agents yet.</p>
        ) : (
          <div className="list">
            {agents.map((agent) => (
              <div key={agent.id} className="list-item">
                <div>
                  <h3>{agent.name}</h3>
                  <p className="muted">{agent.description || "No description"}</p>
                  <p className="muted">Active version: {agent.active_version?.version ?? "-"}</p>
                </div>
                <div className="list-actions">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => updateSettings({ agentId: agent.id })}
                  >
                    Use
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => archiveAgent(agent.id)}>
                    Archive
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default AgentsPage;
