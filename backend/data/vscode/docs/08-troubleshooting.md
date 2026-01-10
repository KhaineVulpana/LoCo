# Troubleshooting (VS Code)

Connection issues
- Verify server URL and auth toggle.
- Confirm the server is running and reachable on port 3199.

Indexing issues
- Ensure Qdrant is running for vector search.
- Check watch mode if incremental updates are missing.

Diff apply failures
- Conflicts occur when the file changed since proposal.
- Regenerate the patch or accept manually.

Approvals stuck
- If approval dialogs do not appear, check VS Code focus.
- Ensure policy rules are not blocking the tool silently.

Performance
- Reduce workspace RAG if prompts are too large.
- Prefer smaller diffs and scoped requests.
