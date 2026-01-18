import React, { useCallback, useState } from "react";
import Button from "../components/Button";
import Input from "../components/Input";
import { useAppContext } from "../lib/appContext";
import { searchMessages, searchSessions } from "../lib/api";
import type { MessageSearchResult, SearchResult } from "../lib/types";

const HistoryPage: React.FC = () => {
  const { settings } = useAppContext();
  const [query, setQuery] = useState("");
  const [sessionResults, setSessionResults] = useState<SearchResult[]>([]);
  const [messageResults, setMessageResults] = useState<MessageSearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!settings.workspaceId || !query.trim()) return;
    setLoading(true);
    const [sessions, messages] = await Promise.all([
      searchSessions(settings, settings.workspaceId, query),
      searchMessages(settings, settings.workspaceId, query)
    ]);
    setSessionResults(sessions);
    setMessageResults(messages);
    setLoading(false);
  }, [settings, query]);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <h1>History and Search</h1>
          <p className="muted">Find past sessions, decisions, and tool runs.</p>
        </div>
        <div className="header-actions">
          <Input
            placeholder="Search conversations"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button onClick={handleSearch} disabled={!query.trim() || !settings.workspaceId}>
            {loading ? "Searching" : "Search"}
          </Button>
        </div>
      </header>

      <div className="grid-two">
        <section className="panel">
          <h2>Sessions</h2>
          {sessionResults.length === 0 ? (
            <p className="muted">No session matches yet.</p>
          ) : (
            <div className="list">
              {sessionResults.map((item) => (
                <div key={item.session_id} className="list-item">
                  <div>
                    <h3>{item.title || "Untitled session"}</h3>
                    <p className="muted">{item.snippet}</p>
                  </div>
                  <span className="muted">{item.last_message_at}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Messages</h2>
          {messageResults.length === 0 ? (
            <p className="muted">No message matches yet.</p>
          ) : (
            <div className="list">
              {messageResults.map((item) => (
                <div key={`${item.session_id}-${item.created_at}`} className="list-item">
                  <div>
                    <strong>{item.session_title || "Untitled"}</strong>
                    <p className="muted">{item.content.slice(0, 140)}</p>
                  </div>
                  <span className="pill pill-neutral">{item.role}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default HistoryPage;
