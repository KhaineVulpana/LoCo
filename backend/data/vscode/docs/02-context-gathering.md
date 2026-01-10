# Context Gathering (VS Code)

Automatic context (when enabled)
- Active editor: file path, language, selection, visible range.
- Open editors: file list with dirty flags.
- Diagnostics: all workspace problems.
- Git context: branch, staged files, modified files.

Explicit context
- @mentions: include file content for explicit references.
- Slash commands: include special intent (ex: /fix, /test).

Mentions
- The extension resolves @file tokens and injects file contents into `context.mentions`.
- Mentions are truncated for safety.

Slash commands
- /fix: focus on diagnostics.
- /test: include tests and recent failures.
- /review: emphasize issues and risks.
- /doc: write documentation based on current file.

Workspace RAG toggle
- `include_workspace_rag` controls whether workspace indexing results are added to context.
- Use this when the task is codebase-specific.
