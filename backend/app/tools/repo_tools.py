"""
Repository hosting tools for GitHub, GitLab, and Jira.
"""

from typing import Dict, Any, Optional, List
from urllib.parse import quote, urlparse

import aiohttp
import structlog

from app.tools.base import Tool
from app.core.config import settings

logger = structlog.get_logger()


def _trim_text(text: Optional[str], limit: int = 4000) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit]


def _normalize_repo(repo: str) -> str:
    if not repo:
        return ""
    repo = repo.strip()
    if repo.startswith("http://") or repo.startswith("https://"):
        parsed = urlparse(repo)
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path
    return repo


class RepoHostingTool(Tool):
    """Structured access to issues/PRs/releases for GitHub/GitLab/Jira."""

    name = "repo_hosting"
    description = "Fetch issues/PRs/releases from GitHub, GitLab, or Jira."
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "description": "Provider: github, gitlab, or jira"
            },
            "operation": {
                "type": "string",
                "description": "Operation (get_issue, get_pr, get_release, list_issues, list_prs, list_releases, search_issues)"
            },
            "repo": {
                "type": "string",
                "description": "Repo path (owner/name) or full URL for GitHub/GitLab"
            },
            "project": {
                "type": "string",
                "description": "Jira project key (for search_issues)"
            },
            "id": {
                "type": "string",
                "description": "Issue/PR/release ID or Jira issue key"
            },
            "tag": {
                "type": "string",
                "description": "Release tag name"
            },
            "query": {
                "type": "string",
                "description": "Search query (GitHub) or JQL (Jira)"
            },
            "state": {
                "type": "string",
                "description": "State filter (open/closed/all)"
            },
            "limit": {
                "type": "number",
                "description": "Max results to return",
                "default": 5
            }
        },
        "required": ["provider", "operation"]
    }

    def approval_prompt(self, arguments: Dict[str, Any]) -> str:
        provider = arguments.get("provider", "")
        operation = arguments.get("operation", "")
        return f"Approve repo API call: {provider} {operation}"

    async def execute(
        self,
        provider: str,
        operation: str,
        repo: Optional[str] = None,
        project: Optional[str] = None,
        id: Optional[str] = None,
        tag: Optional[str] = None,
        query: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        provider = (provider or "").lower().strip()
        operation = (operation or "").lower().strip()
        limit = max(int(limit), 1)

        if provider == "github":
            return await self._github(operation, repo, id, tag, query, state, limit)
        if provider == "gitlab":
            return await self._gitlab(operation, repo, id, tag, state, limit)
        if provider == "jira":
            return await self._jira(operation, project, id, query, limit)

        return {"success": False, "error": f"Unsupported provider: {provider}"}

    async def _github(
        self,
        operation: str,
        repo: Optional[str],
        item_id: Optional[str],
        tag: Optional[str],
        query: Optional[str],
        state: Optional[str],
        limit: int
    ) -> Dict[str, Any]:
        repo = _normalize_repo(repo or "")
        if not repo:
            return {"success": False, "error": "GitHub repo is required (owner/name)."}

        base_url = getattr(settings, "GITHUB_API_BASE_URL", "https://api.github.com")
        token = getattr(settings, "GITHUB_TOKEN", None)
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        def issue_payload(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": item.get("id"),
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "url": item.get("html_url"),
                "author": (item.get("user") or {}).get("login"),
                "labels": [label.get("name") for label in item.get("labels", [])],
                "comments": item.get("comments"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "body": _trim_text(item.get("body"))
            }

        def pr_payload(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": item.get("id"),
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "url": item.get("html_url"),
                "author": (item.get("user") or {}).get("login"),
                "draft": item.get("draft"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "merged_at": item.get("merged_at"),
                "body": _trim_text(item.get("body"))
            }

        def release_payload(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": item.get("id"),
                "name": item.get("name"),
                "tag": item.get("tag_name"),
                "url": item.get("html_url"),
                "created_at": item.get("created_at"),
                "published_at": item.get("published_at"),
                "body": _trim_text(item.get("body"))
            }

        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as session:
            try:
                if operation == "get_issue":
                    if not item_id:
                        return {"success": False, "error": "Issue id is required."}
                    url = f"{base_url}/repos/{repo}/issues/{item_id}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        return {"success": True, "issue": issue_payload(data)}

                if operation == "get_pr":
                    if not item_id:
                        return {"success": False, "error": "PR id is required."}
                    url = f"{base_url}/repos/{repo}/pulls/{item_id}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        return {"success": True, "pull_request": pr_payload(data)}

                if operation == "get_release":
                    if tag:
                        url = f"{base_url}/repos/{repo}/releases/tags/{tag}"
                    else:
                        if not item_id:
                            return {"success": False, "error": "Release id or tag is required."}
                        url = f"{base_url}/repos/{repo}/releases/{item_id}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        return {"success": True, "release": release_payload(data)}

                if operation == "list_releases":
                    url = f"{base_url}/repos/{repo}/releases"
                    async with session.get(url, params={"per_page": limit}) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        releases = [release_payload(item) for item in data][:limit]
                        return {"success": True, "releases": releases, "total": len(releases)}

                if operation == "list_issues":
                    url = f"{base_url}/repos/{repo}/issues"
                    params = {"state": state or "open", "per_page": limit}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        issues = [
                            issue_payload(item)
                            for item in data
                            if not item.get("pull_request")
                        ][:limit]
                        return {"success": True, "issues": issues, "total": len(issues)}

                if operation == "list_prs":
                    url = f"{base_url}/repos/{repo}/pulls"
                    params = {"state": state or "open", "per_page": limit}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        prs = [pr_payload(item) for item in data][:limit]
                        return {"success": True, "pull_requests": prs, "total": len(prs)}

                if operation == "search_issues":
                    if not query:
                        return {"success": False, "error": "Search query is required."}
                    q = f"repo:{repo} {query}"
                    url = f"{base_url}/search/issues"
                    async with session.get(url, params={"q": q, "per_page": limit}) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        items = data.get("items", [])
                        results = [issue_payload(item) for item in items][:limit]
                        return {"success": True, "issues": results, "total": len(results)}

                return {"success": False, "error": f"Unsupported operation: {operation}"}
            except Exception as exc:
                logger.error("github_request_failed", repo=repo, operation=operation, error=str(exc))
                return {"success": False, "error": f"GitHub request failed: {str(exc)}"}

    async def _gitlab(
        self,
        operation: str,
        repo: Optional[str],
        item_id: Optional[str],
        tag: Optional[str],
        state: Optional[str],
        limit: int
    ) -> Dict[str, Any]:
        repo = _normalize_repo(repo or "")
        if not repo:
            return {"success": False, "error": "GitLab repo is required (namespace/name)."}

        base_url = getattr(settings, "GITLAB_API_BASE_URL", "https://gitlab.com/api/v4")
        token = getattr(settings, "GITLAB_TOKEN", None)
        headers = {}
        if token:
            headers["Private-Token"] = token

        encoded_repo = quote(repo, safe="")

        def issue_payload(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": item.get("id"),
                "iid": item.get("iid"),
                "title": item.get("title"),
                "state": item.get("state"),
                "url": item.get("web_url"),
                "author": (item.get("author") or {}).get("username"),
                "labels": item.get("labels", []),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "description": _trim_text(item.get("description"))
            }

        def mr_payload(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": item.get("id"),
                "iid": item.get("iid"),
                "title": item.get("title"),
                "state": item.get("state"),
                "url": item.get("web_url"),
                "author": (item.get("author") or {}).get("username"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "merged_at": item.get("merged_at"),
                "description": _trim_text(item.get("description"))
            }

        def release_payload(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "name": item.get("name"),
                "tag": (item.get("tag_name") or item.get("tag")),
                "url": item.get("url"),
                "released_at": item.get("released_at"),
                "description": _trim_text(item.get("description"))
            }

        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as session:
            try:
                if operation == "get_issue":
                    if not item_id:
                        return {"success": False, "error": "Issue id is required."}
                    url = f"{base_url}/projects/{encoded_repo}/issues/{item_id}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        return {"success": True, "issue": issue_payload(data)}

                if operation == "get_pr":
                    if not item_id:
                        return {"success": False, "error": "Merge request id is required."}
                    url = f"{base_url}/projects/{encoded_repo}/merge_requests/{item_id}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        return {"success": True, "merge_request": mr_payload(data)}

                if operation == "get_release":
                    release_tag = tag or item_id
                    if not release_tag:
                        return {"success": False, "error": "Release tag is required."}
                    url = f"{base_url}/projects/{encoded_repo}/releases/{release_tag}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        return {"success": True, "release": release_payload(data)}

                if operation == "list_releases":
                    url = f"{base_url}/projects/{encoded_repo}/releases"
                    async with session.get(url, params={"per_page": limit}) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        releases = [release_payload(item) for item in data][:limit]
                        return {"success": True, "releases": releases, "total": len(releases)}

                if operation == "list_issues":
                    url = f"{base_url}/projects/{encoded_repo}/issues"
                    params = {"state": state or "opened", "per_page": limit}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        issues = [issue_payload(item) for item in data][:limit]
                        return {"success": True, "issues": issues, "total": len(issues)}

                if operation == "list_prs":
                    url = f"{base_url}/projects/{encoded_repo}/merge_requests"
                    params = {"state": state or "opened", "per_page": limit}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("message", "Request failed")}
                        mrs = [mr_payload(item) for item in data][:limit]
                        return {"success": True, "merge_requests": mrs, "total": len(mrs)}

                return {"success": False, "error": f"Unsupported operation: {operation}"}
            except Exception as exc:
                logger.error("gitlab_request_failed", repo=repo, operation=operation, error=str(exc))
                return {"success": False, "error": f"GitLab request failed: {str(exc)}"}

    async def _jira(
        self,
        operation: str,
        project: Optional[str],
        issue_key: Optional[str],
        jql: Optional[str],
        limit: int
    ) -> Dict[str, Any]:
        base_url = getattr(settings, "JIRA_BASE_URL", None)
        email = getattr(settings, "JIRA_EMAIL", None)
        token = getattr(settings, "JIRA_API_TOKEN", None)

        if not base_url:
            return {"success": False, "error": "JIRA_BASE_URL is not configured."}
        if not email or not token:
            return {"success": False, "error": "JIRA_EMAIL/JIRA_API_TOKEN not configured."}

        auth = aiohttp.BasicAuth(login=email, password=token)

        async with aiohttp.ClientSession(auth=auth, timeout=aiohttp.ClientTimeout(total=20)) as session:
            try:
                if operation == "get_issue":
                    if not issue_key:
                        return {"success": False, "error": "Jira issue key is required."}
                    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("errorMessages", "Request failed")}
                        fields = data.get("fields", {})
                        return {
                            "success": True,
                            "issue": {
                                "key": data.get("key"),
                                "summary": fields.get("summary"),
                                "status": (fields.get("status") or {}).get("name"),
                                "assignee": (fields.get("assignee") or {}).get("displayName"),
                                "reporter": (fields.get("reporter") or {}).get("displayName"),
                                "url": f"{base_url.rstrip('/')}/browse/{data.get('key')}",
                                "description": fields.get("description")
                            }
                        }

                if operation == "search_issues":
                    if not jql:
                        if not project:
                            return {"success": False, "error": "JQL or project key is required."}
                        jql = f"project={project} ORDER BY updated DESC"
                    url = f"{base_url.rstrip('/')}/rest/api/3/search"
                    params = {"jql": jql, "maxResults": limit}
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if resp.status >= 400:
                            return {"success": False, "error": data.get("errorMessages", "Request failed")}
                        issues = []
                        for item in data.get("issues", []):
                            fields = item.get("fields", {})
                            issues.append({
                                "key": item.get("key"),
                                "summary": fields.get("summary"),
                                "status": (fields.get("status") or {}).get("name"),
                                "url": f"{base_url.rstrip('/')}/browse/{item.get('key')}"
                            })
                        return {"success": True, "issues": issues, "total": len(issues)}

                return {"success": False, "error": f"Unsupported Jira operation: {operation}"}
            except Exception as exc:
                logger.error("jira_request_failed", operation=operation, error=str(exc))
                return {"success": False, "error": f"Jira request failed: {str(exc)}"}
