import React, { useCallback, useMemo, useState } from "react";
import Button from "../components/Button";
import Input from "../components/Input";
import Select from "../components/Select";
import Textarea from "../components/Textarea";
import { useAppContext } from "../lib/appContext";
import { buildAgentConfig, createAgent } from "../lib/api";

const mergeDeep = (base: Record<string, unknown>, override: Record<string, unknown>) => {
  const result = { ...base };
  Object.entries(override).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      result[key] = mergeDeep((result[key] as Record<string, unknown>) || {}, value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  });
  return result;
};

const BuilderPage: React.FC = () => {
  const { settings, updateSettings } = useAppContext();
  const [goal, setGoal] = useState("");
  const [personality, setPersonality] = useState("");
  const [constraints, setConstraints] = useState("");
  const [outputFormat, setOutputFormat] = useState("");
  const [specializedKnowledge, setSpecializedKnowledge] = useState("");
  const [toolAllowlist, setToolAllowlist] = useState("");
  const [toolBlocklist, setToolBlocklist] = useState("");
  const [autoApproveTools, setAutoApproveTools] = useState("");
  const [commandApproval, setCommandApproval] = useState("prompt");
  const [networkEnabled, setNetworkEnabled] = useState(false);
  const [ragEnabled, setRagEnabled] = useState(true);
  const [ragLimit, setRagLimit] = useState(5);
  const [ragScore, setRagScore] = useState(0.6);
  const [aceEnabled, setAceEnabled] = useState(true);
  const [aceLimit, setAceLimit] = useState(5);
  const [aceScore, setAceScore] = useState(0.5);
  const [modelProvider, setModelProvider] = useState(settings.modelProvider || "ollama");
  const [modelName, setModelName] = useState(settings.modelName || "");
  const [modelUrl, setModelUrl] = useState(settings.modelUrl || "");
  const [contextWindow, setContextWindow] = useState(settings.contextWindow || 16384);
  const [temperature, setTemperature] = useState(settings.temperature || 0.7);
  const [baseConfig, setBaseConfig] = useState("");
  const [generated, setGenerated] = useState<Record<string, unknown> | null>(null);
  const [agentName, setAgentName] = useState("");
  const [agentDescription, setAgentDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parseList = useCallback((value: string) => {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }, []);

  const baseConfigFromForm = useMemo(() => {
    const systemParts = [
      personality ? `Personality: ${personality}` : "",
      goal ? `Goal: ${goal}` : "",
      constraints ? `Constraints: ${constraints}` : "",
      specializedKnowledge ? `Specialized knowledge: ${specializedKnowledge}` : "",
      outputFormat ? `Output format: ${outputFormat}` : ""
    ].filter(Boolean);

    return {
      system_prompt: systemParts.join("\n\n"),
      tools: {
        allowlist: parseList(toolAllowlist),
        blocklist: parseList(toolBlocklist),
        auto_approve_tools: parseList(autoApproveTools),
        command_approval: commandApproval,
        network_enabled: networkEnabled
      },
      rag: {
        enabled: ragEnabled,
        limit: ragLimit,
        score_threshold: ragScore
      },
      ace: {
        enabled: aceEnabled,
        limit: aceLimit,
        score_threshold: aceScore
      },
      model: {
        provider: modelProvider,
        model_name: modelName,
        url: modelUrl,
        context_window: contextWindow,
        temperature
      }
    };
  }, [
    personality,
    goal,
    constraints,
    specializedKnowledge,
    outputFormat,
    toolAllowlist,
    toolBlocklist,
    autoApproveTools,
    commandApproval,
    networkEnabled,
    ragEnabled,
    ragLimit,
    ragScore,
    aceEnabled,
    aceLimit,
    aceScore,
    modelProvider,
    modelName,
    modelUrl,
    contextWindow,
    temperature,
    parseList
  ]);

  const handleGenerate = useCallback(async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    let base = baseConfigFromForm as Record<string, unknown>;
    try {
      if (baseConfig.trim()) {
        const override = JSON.parse(baseConfig);
        base = mergeDeep(base, override);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid JSON override.");
      setLoading(false);
      return;
    }
    const description = [
      goal ? `Goal: ${goal}` : "",
      personality ? `Personality: ${personality}` : "",
      constraints ? `Constraints: ${constraints}` : "",
      specializedKnowledge ? `Specialized knowledge: ${specializedKnowledge}` : "",
      outputFormat ? `Output format: ${outputFormat}` : ""
    ]
      .filter(Boolean)
      .join("\n");
    try {
      const result = await buildAgentConfig(settings, description, base);
      setGenerated(result.config);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate config.");
    } finally {
      setLoading(false);
    }
  }, [
    goal,
    personality,
    constraints,
    specializedKnowledge,
    outputFormat,
    baseConfig,
    baseConfigFromForm,
    settings
  ]);

  const handleCreate = useCallback(async () => {
    if (!settings.workspaceId || !agentName.trim() || !generated) return;
    const agent = await createAgent(settings, {
      workspace_id: settings.workspaceId,
      name: agentName,
      description: agentDescription,
      config: generated
    });
    updateSettings({ agentId: agent.id });
    setAgentName("");
    setAgentDescription("");
    setGenerated(null);
  }, [settings, agentName, agentDescription, generated, updateSettings]);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <h1>Agent Builder</h1>
          <p className="muted">Describe the agent and generate a config draft with the model.</p>
        </div>
      </header>

      <section className="panel">
        <h2>Core Profile</h2>
        <Textarea
          label="Primary goal"
          placeholder="Example: Build a code review assistant specialized in Python security."
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
        />
        <Textarea
          label="Personality and voice"
          placeholder="Example: Precise, calm, and candid with concise explanations."
          value={personality}
          onChange={(event) => setPersonality(event.target.value)}
        />
        <Textarea
          label="Output format"
          placeholder="Example: Provide a numbered plan, then a concise summary and patches."
          value={outputFormat}
          onChange={(event) => setOutputFormat(event.target.value)}
        />
      </section>

      <section className="panel">
        <h2>Operating Rules</h2>
        <Textarea
          label="Constraints and boundaries"
          placeholder="Example: Do not modify production config, avoid destructive commands."
          value={constraints}
          onChange={(event) => setConstraints(event.target.value)}
        />
        <Textarea
          label="Specialized knowledge"
          placeholder="Example: Familiar with our internal API schemas and deployment workflow."
          value={specializedKnowledge}
          onChange={(event) => setSpecializedKnowledge(event.target.value)}
        />
      </section>

      <section className="panel">
        <h2>Tools and Approvals</h2>
        <div className="grid-two">
          <Input
            label="Tool allowlist (comma-separated)"
            value={toolAllowlist}
            onChange={(event) => setToolAllowlist(event.target.value)}
          />
          <Input
            label="Tool blocklist (comma-separated)"
            value={toolBlocklist}
            onChange={(event) => setToolBlocklist(event.target.value)}
          />
        </div>
        <Input
          label="Auto-approve tools (comma-separated)"
          value={autoApproveTools}
          onChange={(event) => setAutoApproveTools(event.target.value)}
        />
        <div className="grid-two">
          <Select
            label="Command approval"
            value={commandApproval}
            onChange={(event) => setCommandApproval(event.target.value)}
          >
            <option value="prompt">prompt</option>
            <option value="auto">auto</option>
            <option value="none">none</option>
          </Select>
          <label className="toggle">
            <input
              type="checkbox"
              checked={networkEnabled}
              onChange={(event) => setNetworkEnabled(event.target.checked)}
            />
            <span>Enable network tools</span>
          </label>
        </div>
      </section>

      <section className="panel">
        <h2>Retrieval and Memory</h2>
        <div className="grid-two">
          <label className="toggle">
            <input
              type="checkbox"
              checked={ragEnabled}
              onChange={(event) => setRagEnabled(event.target.checked)}
            />
            <span>Enable RAG</span>
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={aceEnabled}
              onChange={(event) => setAceEnabled(event.target.checked)}
            />
            <span>Enable ACE</span>
          </label>
        </div>
        <div className="grid-three">
          <Input
            label="RAG limit"
            type="number"
            value={ragLimit.toString()}
            onChange={(event) => setRagLimit(Number(event.target.value))}
          />
          <Input
            label="RAG score threshold"
            type="number"
            step="0.05"
            value={ragScore.toString()}
            onChange={(event) => setRagScore(Number(event.target.value))}
          />
          <Input
            label="ACE limit"
            type="number"
            value={aceLimit.toString()}
            onChange={(event) => setAceLimit(Number(event.target.value))}
          />
          <Input
            label="ACE score threshold"
            type="number"
            step="0.05"
            value={aceScore.toString()}
            onChange={(event) => setAceScore(Number(event.target.value))}
          />
        </div>
      </section>

      <section className="panel">
        <h2>Model Overrides</h2>
        <div className="grid-two">
          <Select
            label="Provider"
            value={modelProvider}
            onChange={(event) => setModelProvider(event.target.value)}
          >
            <option value="ollama">ollama</option>
            <option value="vllm">vllm</option>
            <option value="llamacpp">llamacpp</option>
          </Select>
          <Input
            label="Model name"
            value={modelName}
            onChange={(event) => setModelName(event.target.value)}
          />
        </div>
        <div className="grid-two">
          <Input
            label="Model URL"
            value={modelUrl}
            onChange={(event) => setModelUrl(event.target.value)}
            hint="Leave blank to use the server default."
          />
          <Input
            label="Context window"
            type="number"
            value={contextWindow.toString()}
            onChange={(event) => setContextWindow(Number(event.target.value))}
          />
        </div>
        <Input
          label="Temperature"
          type="number"
          step="0.1"
          value={temperature.toString()}
          onChange={(event) => setTemperature(Number(event.target.value))}
        />
      </section>

      <section className="panel">
        <h2>Advanced Overrides</h2>
        <Textarea
          label="Base config (optional JSON)"
          value={baseConfig}
          onChange={(event) => setBaseConfig(event.target.value)}
          placeholder='{"tools": {"allowlist": ["read_file"]}}'
        />
        {error ? <p className="muted error-text">{error}</p> : null}
        <Button onClick={handleGenerate} disabled={!goal.trim() || loading}>
          {loading ? "Generating" : "Generate Config"}
        </Button>
      </section>

      <section className="panel">
        <h2>Generated Config</h2>
        {generated ? (
          <pre className="code-block">{JSON.stringify(generated, null, 2)}</pre>
        ) : (
          <p className="muted">No config generated yet.</p>
        )}
      </section>

      <section className="panel">
        <h2>Save Agent</h2>
        <div className="grid-two">
          <Input
            label="Agent name"
            value={agentName}
            onChange={(event) => setAgentName(event.target.value)}
          />
          <Input
            label="Description"
            value={agentDescription}
            onChange={(event) => setAgentDescription(event.target.value)}
          />
        </div>
        <Button onClick={handleCreate} disabled={!agentName.trim() || !generated}>
          Create Agent
        </Button>
      </section>
    </div>
  );
};

export default BuilderPage;
