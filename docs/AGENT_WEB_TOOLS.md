---
title: Agent Web + Repo + DB Tools
---

# Agent Web + Repo + DB Tools

This document describes the web, repo, browser, and read-only SQL tools added to LoCo.
It lives under `docs/` and is indexed into the shared RAG collection (`loco_rag_shared`)
on server startup via `ensure_shared_knowledge`.

## Requirements

- Workspace policy must enable network for web-facing tools:
  - `network_enabled: true`
- Optional API keys:
  - `SERPAPI_API_KEY` for `web_search`
  - `GITHUB_TOKEN` / `GITLAB_TOKEN` for `repo_hosting`
  - `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` for Jira operations
- `headless_browser` requires Playwright browsers: `playwright install`

## Tools

### web_fetch
Fetches a URL, extracts readable text, and (optionally) ingests into RAG.

Inputs:
- `url` (required)
- `ingest` (bool, default false)
- `max_chars` (default 20000)
- `timeout_seconds` (default 20)

Notes:
- If `ingest: true`, content is chunked and embedded into `loco_rag_{module_id}`
  with `type: "web"` and `source: url`.

Example:
```json
{"tool": "web_fetch", "arguments": {"url": "https://example.com", "ingest": true}}
```

### web_search
Searches the web using SerpAPI.

Inputs:
- `query` (required)
- `limit` (default 5)
- `engine` (default `SERPAPI_ENGINE`)
- `location` (optional)

Example:
```json
{"tool": "web_search", "arguments": {"query": "fastapi websocket example", "limit": 5}}
```

### repo_hosting
Structured access to GitHub/GitLab/Jira issues, PRs/MRs, and releases.

Inputs:
- `provider` (github | gitlab | jira)
- `operation` (get_issue, get_pr, get_release, list_issues, list_prs, list_releases, search_issues)
- `repo` for GitHub/GitLab (owner/name or full URL)
- `project` for Jira searches
- `id` (issue/PR/release id or Jira issue key)
- `tag` (release tag)
- `query` (search query or JQL for Jira)
- `state` (open/closed/all)
- `limit` (default 5)

Examples:
```json
{"tool": "repo_hosting", "arguments": {"provider": "github", "operation": "get_issue", "repo": "octocat/hello-world", "id": "123"}}
```

```json
{"tool": "repo_hosting", "arguments": {"provider": "jira", "operation": "search_issues", "project": "ENG", "limit": 5}}
```

### headless_browser
Renders JS-heavy pages with Playwright to retrieve text or HTML.

Inputs:
- `url` (required)
- `wait_ms` (default 1000)
- `timeout_ms` (default 30000)
- `return_html` (default true)
- `return_text` (default true)
- `max_chars` (default 20000)

Example:
```json
{"tool": "headless_browser", "arguments": {"url": "https://example.com/app", "wait_ms": 2000}}
```

### read_only_sql
Executes read-only SQL against the local SQLite database (`loco_agent.db`).

Inputs:
- `query` (required, SELECT/CTE only)
- `params` (optional named parameters)
- `limit` (default 100)

Example:
```json
{"tool": "read_only_sql", "arguments": {"query": "SELECT id, name FROM workspaces ORDER BY created_at DESC", "limit": 10}}
```

## Policy Tip

To enable web tools for a workspace, update policy to set:
```json
{"network_enabled": true}
```

You can also add `web_fetch`, `web_search`, `repo_hosting`, `headless_browser`
to `auto_approve_tools` if you want to avoid per-call approval.
