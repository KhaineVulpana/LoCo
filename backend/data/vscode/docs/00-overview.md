# LoCo VS Code RAG Overview

This folder contains operational knowledge for the VS Code frontend. The goal is to prepopulate the `loco_rag_vscode` collection so the agent can retrieve high-signal guidance during coding tasks.

Key concepts
- Frontends (not domains): the system scopes knowledge and ACE by `frontend_id`.
- VS Code collection names:
  - RAG: `loco_rag_vscode`
  - ACE: `loco_ace_vscode`
- The VS Code extension is a rich client; the backend is authoritative.

System architecture (high level)
1) Extension gathers context (editor, diagnostics, git, mentions).
2) Server receives the user message and context.
3) Retriever performs hybrid search (vector + symbol + text) plus rerank.
4) Context pack is built within token budgets.
5) Agent proposes changes via `propose_diff` and tool calls.
6) Extension renders diffs and requests approvals.

Why this knowledge set exists
- Provide consistent guardrails for diff workflows.
- Explain approval and policy rules.
- Document context gathering behavior and settings.
- Provide troubleshooting guidance for common failure modes.
