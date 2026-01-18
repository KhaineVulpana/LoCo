import React, { useCallback, useEffect, useMemo, useState } from "react";
import Button from "../components/Button";
import Select from "../components/Select";
import { useAppContext } from "../lib/appContext";
import { getSessionTrace, listSessions } from "../lib/api";
import type { Session, SessionTrace } from "../lib/types";

const TracePage: React.FC = () => {
  const { settings } = useAppContext();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [trace, setTrace] = useState<SessionTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportBase = useMemo(() => settings.serverUrl.replace(/\/$/, ""), [settings.serverUrl]);

  const loadSessions = useCallback(async () => {
    if (!settings.workspaceId) {
      setSessions([]);
      setSessionId("");
      return;
    }
    try {
      const data = await listSessions(settings, settings.workspaceId);
      setSessions(data);
      if (data.length === 0) {
        setSessionId("");
        setTrace(null);
      } else if (!data.some((session) => session.id === sessionId)) {
        setSessionId(data[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sessions.");
    }
  }, [settings, sessionId]);

  const loadTrace = useCallback(
    async (targetSessionId: string) => {
      if (!targetSessionId) {
        setTrace(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await getSessionTrace(settings, targetSessionId);
        setTrace(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load trace.");
      } finally {
        setLoading(false);
      }
    },
    [settings]
  );

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (sessionId) {
      loadTrace(sessionId);
    }
  }, [sessionId, loadTrace]);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <h1>Trace</h1>
          <p className="muted">Inspect the latest agent actions for a session.</p>
        </div>
        <div className="header-actions">
          <Select label="Session" value={sessionId} onChange={(event) => setSessionId(event.target.value)}>
            <option value="" disabled>
              Select session
            </option>
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.title || "Untitled"} - {session.model_name || "model"}
              </option>
            ))}
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadTrace(sessionId)}
            disabled={!sessionId || loading}
          >
            {loading ? "Refreshing" : "Refresh"}
          </Button>
          {sessionId ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  window.open(`${exportBase}/v1/exports/sessions/${sessionId}/trace?format=md`, "_blank")
                }
              >
                Export Trace MD
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  window.open(`${exportBase}/v1/exports/sessions/${sessionId}/trace?format=json`, "_blank")
                }
              >
                Export Trace JSON
              </Button>
            </>
          ) : null}
        </div>
      </header>

      {error ? <p className="muted error-text">{error}</p> : null}

      {sessionId ? (
        <section className="panel trace-panel">
          {loading ? (
            <p className="muted">Loading trace...</p>
          ) : trace ? (
            <div className="trace-grid">
              <div className="trace-block">
                <h4>Latest Prompt</h4>
                {trace.prompt?.content ? (
                  <div className="trace-text">{trace.prompt.content}</div>
                ) : (
                  <p className="muted">No prompt yet.</p>
                )}
              </div>
              <div className="trace-block">
                <h4>Tool Actions</h4>
                {trace.tool_events.length === 0 ? (
                  <p className="muted">No tool actions recorded.</p>
                ) : (
                  <div className="trace-list">
                    {trace.tool_events.map((event, index) => {
                      const tone =
                        event.status === "success"
                          ? "pill-accent"
                          : event.status === "denied" || event.status === "failed"
                            ? "pill-warning"
                            : "pill-neutral";
                      return (
                        <details key={`${event.tool_name}-${index}`} className="trace-item">
                          <summary>
                            <span>{event.tool_name}</span>
                            <span className={`pill ${tone}`}>{event.status}</span>
                          </summary>
                          <div className="trace-item-body">
                            <div className="trace-item-meta">
                              {event.duration_ms ? <span>Duration: {event.duration_ms} ms</span> : null}
                              {event.approval_status ? <span>Approval: {event.approval_status}</span> : null}
                            </div>
                            {event.args ? (
                              <pre className="code-block">{JSON.stringify(event.args, null, 2)}</pre>
                            ) : null}
                            {event.result ? (
                              <pre className="code-block">{JSON.stringify(event.result, null, 2)}</pre>
                            ) : null}
                            {event.error ? (
                              <pre className="code-block">{JSON.stringify(event.error, null, 2)}</pre>
                            ) : null}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="trace-block">
                <h4>Assistant Response</h4>
                {trace.assistant?.content ? (
                  <div className="trace-text">{trace.assistant.content}</div>
                ) : (
                  <p className="muted">No assistant response yet.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="muted">No trace data yet.</p>
          )}
        </section>
      ) : (
        <section className="panel">
          <p className="muted">No sessions available for tracing yet.</p>
        </section>
      )}
    </div>
  );
};

export default TracePage;
