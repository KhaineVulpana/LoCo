import React, { useCallback, useEffect, useMemo, useState } from "react";
import Button from "../components/Button";
import Select from "../components/Select";
import { useAppContext } from "../lib/appContext";
import { getAceMetrics, getKnowledgeStats, listAceBullets, listKnowledgeItems, uploadFile } from "../lib/api";
import type { AceBullet, AceMetrics, KnowledgeItem, KnowledgeStats } from "../lib/types";

const moduleOptions = [
  { id: "vscode", label: "VS Code" },
  { id: "android", label: "Android" },
  { id: "3d-gen", label: "3D Gen" }
];

const KnowledgePage: React.FC = () => {
  const { settings } = useAppContext();
  const [moduleId, setModuleId] = useState("vscode");
  const [stats, setStats] = useState<KnowledgeStats["stats"] | null>(null);
  const [aceMetrics, setAceMetrics] = useState<AceMetrics | null>(null);
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [knowledgeOffset, setKnowledgeOffset] = useState<string | null>(null);
  const [aceBullets, setAceBullets] = useState<AceBullet[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refreshStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [knowledge, ace, items, bullets] = await Promise.all([
        getKnowledgeStats(settings, moduleId),
        getAceMetrics(settings, moduleId),
        listKnowledgeItems(settings, moduleId, 120),
        listAceBullets(settings, moduleId)
      ]);
      setStats(knowledge.stats);
      setAceMetrics(ace);
      setKnowledgeItems(items.items || []);
      setKnowledgeOffset(items.next_offset ?? null);
      setAceBullets(bullets.bullets || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load knowledge.");
    } finally {
      setLoading(false);
    }
  }, [settings, moduleId]);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  const handleUpload = useCallback(
    async (file: File) => {
      if (!settings.workspaceId) return;
      setUploading(true);
      await uploadFile(settings, file, {
        workspace_id: settings.workspaceId,
        purpose: "knowledge",
        module_id: moduleId,
        index: true
      });
      setUploading(false);
      refreshStats();
    },
    [settings, moduleId, refreshStats]
  );

  const moduleLabel = useMemo(
    () => moduleOptions.find((option) => option.id === moduleId)?.label || moduleId,
    [moduleId]
  );

  const aceGroups = useMemo(() => {
    const groups: Array<{
      section: string;
      bullets: AceBullet[];
      helpful: number;
      harmful: number;
    }> = [];
    const index = new Map<string, number>();

    aceBullets.forEach((bullet) => {
      const section = bullet.section || "general";
      const existingIndex = index.get(section);
      if (existingIndex === undefined) {
        index.set(section, groups.length);
        groups.push({ section, bullets: [bullet], helpful: bullet.helpful_count, harmful: bullet.harmful_count });
      } else {
        const group = groups[existingIndex];
        group.bullets.push(bullet);
        group.helpful += bullet.helpful_count;
        group.harmful += bullet.harmful_count;
      }
    });

    return groups;
  }, [aceBullets]);

  const formatSection = useCallback((section: string) => section.replace(/_/g, " "), []);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <h1>Knowledge Base</h1>
          <p className="muted">Ingest documents for RAG and review ACE insights.</p>
        </div>
        <div className="header-actions">
          <Select label="Module" value={moduleId} onChange={(event) => setModuleId(event.target.value)}>
            {moduleOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </Select>
          <label className="upload-button">
            {uploading ? "Uploading" : "Upload"}
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
      </header>

      {error ? <p className="muted error-text">{error}</p> : null}

      <div className="knowledge-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>RAG Knowledge</h2>
              <p className="muted">Indexed chunks for {moduleLabel}.</p>
            </div>
            <Button variant="outline" size="sm" onClick={refreshStats} disabled={loading}>
              {loading ? "Refreshing" : "Refresh"}
            </Button>
          </div>
          {stats ? (
            <div className="stats-grid">
              <div>
                <span className="muted">Chunks</span>
                <strong>{String(stats.rag_chunks ?? "-")}</strong>
              </div>
              <div>
                <span className="muted">Status</span>
                <strong>{String(stats.rag_status ?? "-")}</strong>
              </div>
              <div>
                <span className="muted">Collection</span>
                <strong>{String(stats.rag_collection ?? "-")}</strong>
              </div>
            </div>
          ) : (
            <p className="muted">No stats available.</p>
          )}
          <div className="knowledge-list">
            {knowledgeItems.length === 0 ? (
              <p className="muted">No knowledge chunks yet.</p>
            ) : (
              knowledgeItems.map((item) => {
                const payload = item.payload || {};
                const content = typeof payload.content === "string" ? payload.content : "";
                const preview = content.length > 240 ? `${content.slice(0, 240)}...` : content;
                return (
                  <details key={item.id} className="knowledge-item">
                    <summary>
                      <span>{String(payload.source || payload.full_path || "chunk")}</span>
                      <span className="muted">{String(payload.type || "chunk")}</span>
                    </summary>
                    <div className="knowledge-item-body">
                      {preview ? <p className="muted">{preview}</p> : null}
                      {content ? <pre className="code-block">{content}</pre> : null}
                      {payload.full_path ? (
                        <span className="muted">Path: {String(payload.full_path)}</span>
                      ) : null}
                    </div>
                  </details>
                );
              })
            )}
          </div>
          {knowledgeOffset ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                try {
                  const next = await listKnowledgeItems(settings, moduleId, 120, knowledgeOffset);
                  setKnowledgeItems((prev) => [...prev, ...(next.items || [])]);
                  setKnowledgeOffset(next.next_offset ?? null);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Failed to load more knowledge.");
                }
              }}
            >
              Load More
            </Button>
          ) : null}
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>ACE Playbook</h2>
              <p className="muted">Learned bullets and metrics.</p>
            </div>
          </div>
          {aceMetrics ? (
            <div className="stats-grid">
              <div>
                <span className="muted">Bullets</span>
                <strong>{String(aceMetrics.total_bullets ?? "-")}</strong>
              </div>
              <div>
                <span className="muted">Helpful</span>
                <strong>{String(aceMetrics.helpful_total ?? "-")}</strong>
              </div>
              <div>
                <span className="muted">Harmful</span>
                <strong>{String(aceMetrics.harmful_total ?? "-")}</strong>
              </div>
            </div>
          ) : (
            <p className="muted">No ACE data yet.</p>
          )}
          <div className="knowledge-list">
            {aceGroups.length === 0 ? (
              <p className="muted">No ACE bullets yet.</p>
            ) : (
              aceGroups.map((group) => (
                <details key={group.section} className="knowledge-item">
                  <summary>
                    <span>{formatSection(group.section)}</span>
                    <span className="muted">
                      {group.bullets.length} bullets | {group.helpful} helpful / {group.harmful} harmful
                    </span>
                  </summary>
                  <div className="knowledge-item-body ace-bullet-list">
                    {group.bullets.map((bullet) => (
                      <div key={bullet.id} className="ace-bullet">
                        <pre className="code-block">{bullet.content}</pre>
                        <div className="ace-bullet-meta">
                          <span className="muted">
                            {bullet.helpful_count} helpful / {bullet.harmful_count} harmful
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default KnowledgePage;
