# Workspace Indexing and Retrieval

Indexing
- The server indexes workspace files into SQLite + Qdrant.
- Chunking uses AST when possible, fallback to text.
- Symbols are extracted for name-based lookup.

Watchers
- File watcher emits incremental updates after changes.
- Polling watcher is available for unreliable filesystems.

Retrieval strategy
- Hybrid: vector search + symbol search + text search.
- Ripgrep/regex search is used when needed.
- Reranking produces a compact context pack.

Context budgets
- Separate budgets exist for RAG, workspace, and ACE.
- The agent truncates when the budget is exceeded.

Frontend scope
- Use `frontend_id = "vscode"` for extension sessions.
- Knowledge collection: `loco_rag_vscode`.
