import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import Button from "../components/Button";
import Input from "../components/Input";
import Select from "../components/Select";
import Textarea from "../components/Textarea";
import Modal from "../components/Modal";
import Pill from "../components/Pill";
import { useAppContext } from "../lib/appContext";
import { NAV_ITEMS } from "../lib/navItems";
import {
  createSession,
  createFolder,
  deleteFolder,
  deleteSession,
  getSessionMessages,
  listSessions,
  listUploads,
  updateFolder,
  updateSession,
  uploadFile
} from "../lib/api";
import type { ChatItem, Session, UploadAttachment } from "../lib/types";
import { getWsUrl } from "../lib/ws";

const ChatPage: React.FC = () => {
  const { settings, updateSettings, folders, agents, workspaces, refreshFolders } = useAppContext();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [chatItems, setChatItems] = useState<ChatItem[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [attachments, setAttachments] = useState<UploadAttachment[]>([]);
  const [statusText, setStatusText] = useState("Ready");
  const [actionError, setActionError] = useState<string | null>(null);
  const [showFolderModal, setShowFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renameFolderId, setRenameFolderId] = useState<string | null>(null);
  const [renameFolderName, setRenameFolderName] = useState("");
  const [showRenameFolderModal, setShowRenameFolderModal] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [pendingDeleteType, setPendingDeleteType] = useState<"session" | "folder" | null>(null);
  const [showSessionModal, setShowSessionModal] = useState(false);
  const [sessionModelName, setSessionModelName] = useState(settings.modelName || "");
  const [sessionModelProvider, setSessionModelProvider] = useState(settings.modelProvider || "ollama");
  const [sessionModelUrl, setSessionModelUrl] = useState(settings.modelUrl || "");
  const [sessionContextWindow, setSessionContextWindow] = useState(settings.contextWindow || 16384);
  const [sessionTemperature, setSessionTemperature] = useState(settings.temperature || 0.7);
  const [sessionTitleInput, setSessionTitleInput] = useState("");
  const [contextMenu, setContextMenu] = useState<{
    type: "session" | "folder";
    id: string;
    x: number;
    y: number;
  } | null>(null);
  const [approval, setApproval] = useState<{
    requestId: string;
    tool: string;
    message?: string;
    args?: Record<string, unknown>;
  } | null>(null);
  const [showEmptySessions, setShowEmptySessions] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const streamingIdRef = useRef<string | null>(null);

  const activeSession = sessions.find((session) => session.id === activeSessionId) || null;
  const emptySessionsCount = useMemo(
    () => sessions.filter((session) => !session.title?.trim()).length,
    [sessions]
  );
  const hiddenEmptySessionsCount = useMemo(
    () => sessions.filter((session) => !session.title?.trim() && session.id !== activeSessionId).length,
    [sessions, activeSessionId]
  );
  const showEmptyToggle = showEmptySessions ? emptySessionsCount > 0 : hiddenEmptySessionsCount > 0;
  const visibleSessions = useMemo(() => {
    if (showEmptySessions) {
      return sessions;
    }
    return sessions.filter(
      (session) => session.id === activeSessionId || !!session.title?.trim()
    );
  }, [sessions, showEmptySessions, activeSessionId]);

  const loadSessions = useCallback(async () => {
    if (!settings.workspaceId) {
      setSessions([]);
      setActiveSessionId(null);
      return;
    }
    const data = await listSessions(settings, settings.workspaceId, settings.folderId);
    setSessions(data);
    if (data.length === 0) {
      setActiveSessionId(null);
      return;
    }
    if (!activeSessionId || !data.some((session) => session.id === activeSessionId)) {
      const preferred = data.find((session) => session.title?.trim()) || data[0];
      setActiveSessionId(preferred.id);
    }
  }, [settings, activeSessionId]);

  const loadMessages = useCallback(
    async (sessionId: string) => {
      const data = await getSessionMessages(settings, sessionId);
      const items = data.map((msg) => ({
        kind: "message" as const,
        id: crypto.randomUUID(),
        role: msg.role,
        content: msg.content,
        timestamp: msg.created_at
      }));
      setChatItems(items);
      streamingIdRef.current = null;
    },
    [settings]
  );

  const loadAttachments = useCallback(
    async (sessionId: string) => {
      if (!settings.workspaceId) {
        setAttachments([]);
        return;
      }
      const data = await listUploads(settings, settings.workspaceId, sessionId, "attachment");
      setAttachments(data);
    },
    [settings]
  );

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (activeSessionId) {
      loadMessages(activeSessionId);
      loadAttachments(activeSessionId);
    }
  }, [activeSessionId, loadMessages, loadAttachments]);

  useEffect(() => {
    const handleDismiss = () => setContextMenu(null);
    window.addEventListener("click", handleDismiss);
    return () => {
      window.removeEventListener("click", handleDismiss);
    };
  }, []);

  useEffect(() => {
    if (!activeSession) return;
    setSessionModelName(activeSession.model_name || "");
    setSessionModelProvider(activeSession.model_provider || "ollama");
    setSessionModelUrl(activeSession.model_url || settings.modelUrl || "");
    setSessionContextWindow(activeSession.context_window || 16384);
    setSessionTemperature(activeSession.temperature ?? 0.7);
    setSessionTitleInput(activeSession.title || "");
  }, [activeSession, settings.modelUrl]);

  const sendHello = useCallback((ws: WebSocket) => {
    ws.send(
      JSON.stringify({
        type: "client.hello",
        client_info: {
          name: "agent-ui",
          version: "0.1.0",
          capabilities: ["approvals", "streaming", "uploads"]
        }
      })
    );
  }, []);

  const handleDelta = useCallback((delta: string) => {
    setChatItems((prev) => {
      if (!streamingIdRef.current) {
        const id = crypto.randomUUID();
        streamingIdRef.current = id;
        return [
          ...prev,
          { kind: "message", id, role: "assistant", content: delta }
        ];
      }
      return prev.map((item) => {
        if (item.id !== streamingIdRef.current || item.kind !== "message") {
          return item;
        }
        return { ...item, content: `${item.content}${delta}` };
      });
    });
  }, []);

  const handleFinal = useCallback((message: string) => {
    setChatItems((prev) =>
      prev.map((item) => {
        if (item.id !== streamingIdRef.current || item.kind !== "message") {
          return item;
        }
        return { ...item, content: message };
      })
    );
    streamingIdRef.current = null;
    setStatusText("Ready");
  }, []);

  const connectWs = useCallback(
    (sessionId: string) => {
      if (!settings.serverUrl) return;
      wsRef.current?.close();

      const tokenParam = settings.token ? `?token=${encodeURIComponent(settings.token)}` : "";
      const wsUrl = getWsUrl(settings, `/v1/sessions/${sessionId}/stream${tokenParam}`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatusText("Connected");
        sendHello(ws);
      };
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const type = payload.type;

          if (type === "assistant.message_delta") {
            handleDelta(payload.delta || "");
          } else if (type === "assistant.message_final") {
            handleFinal(payload.message || "");
          } else if (type === "assistant.thinking") {
            setStatusText(payload.message || "Thinking");
          } else if (type === "assistant.tool_use") {
            setChatItems((prev) => [
              ...prev,
              {
                kind: "tool",
                id: crypto.randomUUID(),
                tool: payload.tool || "tool",
                content: JSON.stringify(payload.arguments || {})
              }
            ]);
          } else if (type === "assistant.tool_result") {
            setChatItems((prev) => [
              ...prev,
              {
                kind: "tool",
                id: crypto.randomUUID(),
                tool: payload.tool || "tool",
                content: JSON.stringify(payload.result || {})
              }
            ]);
          } else if (type === "tool.request_approval" || type === "command.request_approval") {
            setApproval({
              requestId: payload.request_id,
              tool: payload.tool || payload.tool_name || "tool",
              message: payload.message,
              args: payload.arguments || payload.args
            });
          } else if (type === "server.error") {
            setChatItems((prev) => [
              ...prev,
              {
                kind: "error",
                id: crypto.randomUUID(),
                label: payload.error?.code || "error",
                detail: payload.error?.message
              }
            ]);
          }
        } catch {
          setChatItems((prev) => [
            ...prev,
            { kind: "error", id: crypto.randomUUID(), label: "parse_error" }
          ]);
        }
      };
      ws.onerror = () => {
        setStatusText("Disconnected");
      };
      ws.onclose = () => {
        setStatusText("Disconnected");
      };
    },
    [settings, handleDelta, handleFinal, sendHello]
  );

  useEffect(() => {
    if (activeSessionId) {
      connectWs(activeSessionId);
    }
    return () => {
      wsRef.current?.close();
    };
  }, [activeSessionId, connectWs]);

  const handleSendMessage = useCallback(async () => {
    const trimmedMessage = messageInput.trim();
    if (!trimmedMessage || !settings.workspaceId) return;
    let sessionId = activeSessionId;

    if (!sessionId) {
      const newSession = await createSession(settings, {
        workspace_id: settings.workspaceId,
        folder_id: settings.folderId,
        agent_id: settings.agentId,
        title: null,
        model_provider: settings.modelProvider,
        model_name: settings.modelName,
        model_url: settings.modelUrl,
        context_window: settings.contextWindow,
        temperature: settings.temperature
      });
      sessionId = newSession.id;
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      connectWs(newSession.id);
    }

    setChatItems((prev) => [
      ...prev,
      {
        kind: "message",
        id: crypto.randomUUID(),
        role: "user",
        content: trimmedMessage
      }
    ]);

    const derivedTitle = trimmedMessage.split(/\r?\n/)[0].slice(0, 80);
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id !== sessionId) return session;
        if (session.title?.trim()) return session;
        return { ...session, title: derivedTitle };
      })
    );

    wsRef.current?.send(
      JSON.stringify({
        type: "client.user_message",
        message: trimmedMessage,
        context: {
          module_id: settings.moduleId || "vscode",
          command: ""
        }
      })
    );
    setMessageInput("");
  }, [messageInput, activeSessionId, settings, connectWs]);

  const handleApprove = useCallback(
    (approved: boolean) => {
      if (!approval || !wsRef.current) return;
      wsRef.current.send(
        JSON.stringify({
          type: "client.approval_response",
          request_id: approval.requestId,
          approved
        })
      );
      setApproval(null);
    },
    [approval]
  );

  const handleUpload = useCallback(
    async (file: File) => {
      if (!activeSessionId || !settings.workspaceId) return;
      await uploadFile(settings, file, {
        workspace_id: settings.workspaceId,
        session_id: activeSessionId,
        purpose: "attachment"
      });
      await loadAttachments(activeSessionId);
    },
    [settings, activeSessionId, loadAttachments]
  );

  const openContextMenu = useCallback(
    (event: React.MouseEvent, type: "session" | "folder", id: string) => {
      event.preventDefault();
      setContextMenu({ type, id, x: event.clientX, y: event.clientY });
    },
    []
  );

  const requestDelete = useCallback((type: "session" | "folder", id: string) => {
    setPendingDeleteType(type);
    setPendingDeleteId(id);
    setContextMenu(null);
  }, []);

  const handleDelete = useCallback(async () => {
    if (!pendingDeleteId || !pendingDeleteType) return;
    setActionError(null);
    try {
      if (pendingDeleteType === "session") {
        await deleteSession(settings, pendingDeleteId);
        setSessions((prev) => prev.filter((session) => session.id !== pendingDeleteId));
        if (activeSessionId === pendingDeleteId) {
          setActiveSessionId(null);
        }
      } else {
        await deleteFolder(settings, pendingDeleteId);
        await refreshFolders(settings.workspaceId);
        if (settings.folderId === pendingDeleteId) {
          updateSettings({ folderId: undefined });
        }
      }
      setPendingDeleteId(null);
      setPendingDeleteType(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Delete failed.");
    }
  }, [pendingDeleteId, pendingDeleteType, settings, activeSessionId, refreshFolders, updateSettings]);

  const handleRenameFolder = useCallback(async () => {
    if (!renameFolderId || !renameFolderName.trim()) return;
    setActionError(null);
    try {
      await updateFolder(settings, renameFolderId, { name: renameFolderName.trim() });
      await refreshFolders(settings.workspaceId);
      setShowRenameFolderModal(false);
      setRenameFolderId(null);
      setRenameFolderName("");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Rename failed.");
    }
  }, [renameFolderId, renameFolderName, settings, refreshFolders]);

  const sessionTitle = useMemo(() => {
    if (!activeSession) return "New Session";
    return activeSession.title || "Untitled Session";
  }, [activeSession]);

  const exportBase = settings.serverUrl.replace(/\/$/, "");
  const pendingSession = sessions.find((session) => session.id === pendingDeleteId) || null;
  const pendingFolder = folders.find((folder) => folder.id === pendingDeleteId) || null;
  const deleteTargetName =
    pendingDeleteType === "session"
      ? pendingSession?.title || "Untitled session"
      : pendingFolder?.name || "Folder";

  return (
    <div className="chat-layout">
      <section className="chat-sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">LoCo</span>
          <span className="brand-sub">Agent Studio</span>
        </div>
        <div className="connection sidebar-connection">
          <span className="status-dot" />
          <span className="connection-text">{settings.serverUrl}</span>
        </div>
        <Select
          label="Workspace"
          value={settings.workspaceId ?? ""}
          onChange={(event) => updateSettings({ workspaceId: event.target.value })}
        >
          <option value="" disabled>
            Workspace
          </option>
          {workspaces.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name}
            </option>
          ))}
        </Select>

        <div className="sidebar-section">
          <div className="sidebar-section-header">
            <span className="field-label">Navigation</span>
          </div>
          <nav className="sidebar-nav">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-header">
            <span className="field-label">Agent</span>
          </div>
          <Select
            label="Agent"
            value={settings.agentId ?? ""}
            onChange={(event) => updateSettings({ agentId: event.target.value || undefined })}
          >
            <option value="">Default agent</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </Select>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-header">
            <span className="field-label">Folders</span>
            <div className="sidebar-actions">
              <Button variant="ghost" size="sm" onClick={() => setShowFolderModal(true)}>
                New
              </Button>
            </div>
          </div>
          <div className="sidebar-section-body">
            <button
              className={`folder-item ${!settings.folderId ? "active" : ""}`}
              onClick={() => updateSettings({ folderId: undefined })}
            >
              All Sessions
            </button>
            {folders.map((folder) => (
              <button
                key={folder.id}
                className={`folder-item ${settings.folderId === folder.id ? "active" : ""}`}
                onClick={() => updateSettings({ folderId: folder.id })}
                onContextMenu={(event) => openContextMenu(event, "folder", folder.id)}
              >
                {folder.name}
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-section sidebar-section-grow">
          <div className="sidebar-section-header">
            <span className="field-label">Recent Chats</span>
            <div className="sidebar-actions">
              {showEmptyToggle ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowEmptySessions((prev) => !prev)}
                >
                  {showEmptySessions ? "Hide empty" : `Show empty (${hiddenEmptySessionsCount})`}
                </Button>
              ) : null}
              <Button variant="ghost" size="sm" onClick={() => setActiveSessionId(null)}>
                New
              </Button>
            </div>
          </div>
          {actionError ? <p className="muted error-text">{actionError}</p> : null}
          <div className="sidebar-section-body sidebar-section-body--grow chat-session-list">
            {visibleSessions.map((session) => (
              <button
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? "active" : ""}`}
                onClick={() => setActiveSessionId(session.id)}
                onContextMenu={(event) => openContextMenu(event, "session", session.id)}
              >
                <div className="session-title">{session.title || "Untitled"}</div>
                <div className="session-meta">
                  <span>{session.model_name}</span>
                  <span>{new Date(session.created_at).toLocaleDateString()}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="chat-main">
        <div className="chat-header">
          <div>
            <h2>{sessionTitle}</h2>
            <div className="chat-header-meta">
              <Pill label={statusText} tone="accent" />
              {activeSession?.model_name ? (
                <Pill label={activeSession.model_name} tone="neutral" />
              ) : null}
            </div>
          </div>
          {activeSessionId ? (
            <div className="chat-header-actions">
              <Button variant="outline" size="sm" onClick={() => setShowSessionModal(true)}>
                Session Settings
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  window.open(`${exportBase}/v1/exports/sessions/${activeSessionId}?format=md`, "_blank")
                }
              >
                Export MD
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  window.open(`${exportBase}/v1/exports/sessions/${activeSessionId}?format=json`, "_blank")
                }
              >
                Export JSON
              </Button>
            </div>
          ) : null}
        </div>

        <div className="chat-thread">
          {chatItems.length === 0 ? (
            <div className="empty-state">
              <h3>Start a new session</h3>
              <p>Choose an agent, drop a file, and send a prompt.</p>
            </div>
          ) : (
            chatItems.map((item) => {
              if (item.kind === "message") {
                return (
                  <div key={item.id} className={`chat-bubble ${item.role}`}>
                    <div className="chat-role">{item.role}</div>
                    <div className="chat-content">{item.content}</div>
                  </div>
                );
              }
              if (item.kind === "tool") {
                return (
                  <div key={item.id} className="chat-tool">
                    <div className="chat-role">Tool: {item.tool}</div>
                    <pre>{item.content}</pre>
                  </div>
                );
              }
              if (item.kind === "error") {
                return (
                  <div key={item.id} className="chat-error">
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                  </div>
                );
              }
              return null;
            })
          )}
        </div>

        <div className="chat-composer">
          <div className="composer-row">
            <Textarea
              label="Message"
              placeholder="Ask your agent to plan, build, or debug..."
              value={messageInput}
              onChange={(event) => setMessageInput(event.target.value)}
            />
            <div className="composer-actions">
              <Button onClick={handleSendMessage}>Send</Button>
              <label className="upload-button">
                Attach
                <input
                  type="file"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      handleUpload(file);
                    }
                    event.target.value = "";
                  }}
                />
              </label>
            </div>
          </div>
          {attachments.length > 0 ? (
            <div className="attachments">
              {attachments.map((attachment) => (
                <div key={attachment.id} className="attachment">
                  <a
                    href={`${exportBase}/v1/uploads/${attachment.id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {attachment.file_name}
                  </a>
                  <span className="muted">{Math.round(attachment.size_bytes / 1024)} KB</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      {contextMenu ? (
        <div
          className="context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
        >
          <button
            className="context-menu-item"
            onClick={() => {
              if (contextMenu.type === "session") {
                setActiveSessionId(contextMenu.id);
                setShowSessionModal(true);
              } else {
                const folder = folders.find((item) => item.id === contextMenu.id);
                setRenameFolderId(contextMenu.id);
                setRenameFolderName(folder?.name || "");
                setShowRenameFolderModal(true);
              }
              setContextMenu(null);
            }}
          >
            Rename
          </button>
          <button
            className="context-menu-item danger"
            onClick={() => requestDelete(contextMenu.type, contextMenu.id)}
          >
            Delete
          </button>
        </div>
      ) : null}

      <Modal
        open={showRenameFolderModal}
        title="Rename Folder"
        onClose={() => setShowRenameFolderModal(false)}
        actions={
          <div className="approval-actions">
            <Button variant="outline" onClick={() => setShowRenameFolderModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleRenameFolder}>Save</Button>
          </div>
        }
      >
        <Input
          label="Folder name"
          value={renameFolderName}
          onChange={(event) => setRenameFolderName(event.target.value)}
        />
      </Modal>

      <Modal
        open={pendingDeleteId !== null}
        title={`Delete ${pendingDeleteType === "session" ? "Session" : "Folder"}`}
        onClose={() => {
          setPendingDeleteId(null);
          setPendingDeleteType(null);
        }}
        actions={
          <div className="approval-actions">
            <Button
              variant="outline"
              onClick={() => {
                setPendingDeleteId(null);
                setPendingDeleteType(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete}>
              Delete
            </Button>
          </div>
        }
      >
        <p>
          {pendingDeleteType === "session"
            ? `Delete "${deleteTargetName}"? This removes the session history.`
            : `Delete "${deleteTargetName}"? Sessions will be moved back to All Sessions.`}
        </p>
      </Modal>

      <Modal
        open={!!approval}
        title="Approval Required"
        onClose={() => setApproval(null)}
        actions={
          <div className="approval-actions">
            <Button variant="outline" onClick={() => handleApprove(false)}>
              Deny
            </Button>
            <Button onClick={() => handleApprove(true)}>Approve</Button>
          </div>
        }
      >
        <p>{approval?.message || "This action needs your approval."}</p>
        {approval?.tool ? <p className="muted">Tool: {approval.tool}</p> : null}
        {approval?.args ? (
          <pre className="code-block">{JSON.stringify(approval.args, null, 2)}</pre>
        ) : null}
      </Modal>
      <Modal
        open={showFolderModal}
        title="Create Folder"
        onClose={() => setShowFolderModal(false)}
        actions={
          <div className="approval-actions">
            <Button variant="outline" onClick={() => setShowFolderModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={async () => {
                if (!settings.workspaceId || !newFolderName.trim()) return;
                setActionError(null);
                try {
                  await createFolder(settings, settings.workspaceId, newFolderName.trim());
                  await refreshFolders(settings.workspaceId);
                  setNewFolderName("");
                  setShowFolderModal(false);
                } catch (error) {
                  setActionError(error instanceof Error ? error.message : "Folder creation failed.");
                }
              }}
            >
              Create
            </Button>
          </div>
        }
      >
        <Input
          label="Folder name"
          value={newFolderName}
          onChange={(event) => setNewFolderName(event.target.value)}
        />
      </Modal>
      <Modal
        open={showSessionModal}
        title="Session Settings"
        onClose={() => setShowSessionModal(false)}
        actions={
          <div className="approval-actions">
            <Button variant="outline" onClick={() => setShowSessionModal(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (!activeSessionId) return;
                requestDelete("session", activeSessionId);
                setShowSessionModal(false);
              }}
            >
              Delete
            </Button>
            <Button
              onClick={async () => {
                if (!activeSessionId) return;
                setActionError(null);
                try {
                  const updated = await updateSession(settings, activeSessionId, {
                    title: sessionTitleInput || null,
                    model_provider: sessionModelProvider,
                    model_name: sessionModelName,
                    model_url: sessionModelUrl.trim() ? sessionModelUrl.trim() : null,
                    context_window: sessionContextWindow,
                    temperature: sessionTemperature
                  });
                  setSessions((prev) =>
                    prev.map((session) => (session.id === updated.id ? updated : session))
                  );
                  setShowSessionModal(false);
                } catch (error) {
                  setActionError(error instanceof Error ? error.message : "Session update failed.");
                }
              }}
            >
              Save
            </Button>
          </div>
        }
      >
        <Select
          label="Provider"
          value={sessionModelProvider}
          onChange={(event) => setSessionModelProvider(event.target.value)}
        >
          <option value="ollama">ollama</option>
          <option value="vllm">vllm</option>
          <option value="llamacpp">llamacpp</option>
        </Select>
        <Input
          label="Title"
          value={sessionTitleInput}
          onChange={(event) => setSessionTitleInput(event.target.value)}
        />
        <Input
          label="Model name"
          value={sessionModelName}
          onChange={(event) => setSessionModelName(event.target.value)}
        />
        <Input
          label="Model URL"
          value={sessionModelUrl}
          onChange={(event) => setSessionModelUrl(event.target.value)}
          hint="Leave blank to use the server default."
        />
        <Input
          label="Context window"
          type="number"
          value={sessionContextWindow.toString()}
          onChange={(event) => setSessionContextWindow(Number(event.target.value))}
        />
        <Input
          label="Temperature"
          type="number"
          step="0.1"
          value={sessionTemperature.toString()}
          onChange={(event) => setSessionTemperature(Number(event.target.value))}
        />
        <Select
          label="Folder"
          value={activeSession?.folder_id ?? ""}
          onChange={(event) => {
            if (!activeSessionId) return;
            updateSession(settings, activeSessionId, {
              folder_id: event.target.value || null
            })
              .then((updated) => {
                setSessions((prev) =>
                  prev.map((session) =>
                    session.id === updated.id ? updated : session
                  )
                );
              })
              .catch((error) => {
                setActionError(error instanceof Error ? error.message : "Folder update failed.");
              });
          }}
        >
          <option value="">No folder</option>
          {folders.map((folder) => (
            <option key={folder.id} value={folder.id}>
              {folder.name}
            </option>
          ))}
        </Select>
      </Modal>
    </div>
  );
};

export default ChatPage;
