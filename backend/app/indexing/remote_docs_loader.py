"""
Remote documentation loader for shared RAG knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import time
import structlog
import aiohttp

logger = structlog.get_logger()

DEFAULT_SOURCES_PATH = Path("backend") / "data" / "remote-docs" / "sources.json"
DEFAULT_CONTENT_DIR = Path("backend") / "data" / "remote-docs" / "content"
DEFAULT_METADATA_PATH = Path("backend") / "data" / "remote-docs" / "metadata.json"
DEFAULT_REFRESH_HOURS = 24
DEFAULT_MAX_FILE_BYTES = 1_000_000
DEFAULT_MAX_FILES_PER_SOURCE = 300
DEFAULT_EXTENSIONS = [".md", ".rst", ".txt"]


@dataclass
class RemoteSource:
    source_id: str
    source_type: str
    repo: Optional[str] = None
    branch: Optional[str] = None
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    extensions: Optional[List[str]] = None
    max_files: Optional[int] = None
    urls: Optional[List[str]] = None


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return _resolve_repo_root() / path


def _normalize_prefixes(prefixes: Optional[List[str]]) -> List[str]:
    if not prefixes:
        return []
    return [prefix.strip("/").replace("\\", "/") for prefix in prefixes if prefix]


def _path_included(path: str, include_paths: List[str], exclude_paths: List[str]) -> bool:
    normalized = path.replace("\\", "/")
    if include_paths:
        if not any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in include_paths
        ):
            return False
    if exclude_paths:
        if any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in exclude_paths
        ):
            return False
    return True


def _extension_allowed(path: str, extensions: List[str]) -> bool:
    return any(path.lower().endswith(ext) for ext in extensions)


def _load_metadata(metadata_path: Path) -> Dict[str, Any]:
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_metadata(metadata_path: Path, metadata: Dict[str, Any]) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _refresh_due(metadata: Dict[str, Any], refresh_hours: int) -> bool:
    last_refreshed = metadata.get("last_refreshed_at")
    if not last_refreshed:
        return True
    return (time.time() - float(last_refreshed)) >= (refresh_hours * 3600)


def _parse_sources(sources_path: Path) -> List[RemoteSource]:
    if not sources_path.exists():
        logger.warning("remote_sources_missing", path=str(sources_path))
        return []

    try:
        data = json.loads(sources_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("remote_sources_parse_failed", error=str(e))
        return []

    sources: List[RemoteSource] = []
    for entry in data.get("sources", []):
        source = RemoteSource(
            source_id=entry.get("id") or entry.get("source_id") or "unknown",
            source_type=entry.get("type") or "github_repo",
            repo=entry.get("repo"),
            branch=entry.get("branch"),
            include_paths=entry.get("include_paths"),
            exclude_paths=entry.get("exclude_paths"),
            extensions=entry.get("extensions"),
            max_files=entry.get("max_files"),
            urls=entry.get("urls")
        )
        sources.append(source)
    return sources


async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
    try:
        async with session.get(url) as response:
            if response.status != 200:
                logger.warning("remote_fetch_failed", url=url, status=response.status)
                return None
            return await response.json()
    except Exception as e:
        logger.warning("remote_fetch_exception", url=url, error=str(e))
        return None


async def _fetch_bytes(
    session: aiohttp.ClientSession,
    url: str,
    max_bytes: int
) -> Optional[bytes]:
    try:
        async with session.get(url) as response:
            if response.status != 200:
                logger.warning("remote_file_failed", url=url, status=response.status)
                return None
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                logger.warning("remote_file_too_large", url=url, size=int(content_length))
                return None
            data = await response.read()
            if len(data) > max_bytes:
                logger.warning("remote_file_too_large", url=url, size=len(data))
                return None
            return data
    except Exception as e:
        logger.warning("remote_file_exception", url=url, error=str(e))
        return None


async def _download_github_source(
    session: aiohttp.ClientSession,
    source: RemoteSource,
    target_root: Path,
    max_bytes: int,
    default_max_files: int
) -> Dict[str, Any]:
    if not source.repo:
        return {"downloaded": 0, "failed": 0, "skipped": 0}

    repo = source.repo
    include_paths = _normalize_prefixes(source.include_paths)
    exclude_paths = _normalize_prefixes(source.exclude_paths)
    extensions = source.extensions or DEFAULT_EXTENSIONS
    max_files = source.max_files or default_max_files

    repo_api = f"https://api.github.com/repos/{repo}"
    repo_info = await _fetch_json(session, repo_api)
    if not repo_info:
        return {"downloaded": 0, "failed": 0, "skipped": 0}

    branch = source.branch or repo_info.get("default_branch", "main")
    tree_api = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    tree_info = await _fetch_json(session, tree_api)
    if not tree_info:
        return {"downloaded": 0, "failed": 0, "skipped": 0}

    tree = tree_info.get("tree", [])
    candidates = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if not _path_included(path, include_paths, exclude_paths):
            continue
        if not _extension_allowed(path, extensions):
            continue
        candidates.append(path)

    candidates = sorted(candidates)[:max_files]

    downloaded = 0
    failed = 0
    skipped = 0

    for path in candidates:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        data = await _fetch_bytes(session, raw_url, max_bytes=max_bytes)
        if data is None:
            failed += 1
            continue
        if not data:
            skipped += 1
            continue

        dest_path = target_root / source.source_id / path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest_path.write_bytes(data)
            downloaded += 1
        except Exception as e:
            logger.warning("remote_file_write_failed", path=str(dest_path), error=str(e))
            failed += 1

    return {"downloaded": downloaded, "failed": failed, "skipped": skipped}


async def _download_url_source(
    session: aiohttp.ClientSession,
    source: RemoteSource,
    target_root: Path,
    max_bytes: int
) -> Dict[str, Any]:
    urls = source.urls or []
    downloaded = 0
    failed = 0
    skipped = 0

    for idx, url in enumerate(urls, 1):
        data = await _fetch_bytes(session, url, max_bytes=max_bytes)
        if data is None:
            failed += 1
            continue
        if not data:
            skipped += 1
            continue

        file_name = f"url_{idx}.txt"
        dest_path = target_root / source.source_id / file_name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest_path.write_bytes(data)
            downloaded += 1
        except Exception as e:
            logger.warning("remote_file_write_failed", path=str(dest_path), error=str(e))
            failed += 1

    return {"downloaded": downloaded, "failed": failed, "skipped": skipped}


async def ensure_remote_docs(
    refresh_hours: int = DEFAULT_REFRESH_HOURS,
    sources_path: Optional[str] = None,
    content_dir: Optional[str] = None,
    metadata_path: Optional[str] = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_files_per_source: int = DEFAULT_MAX_FILES_PER_SOURCE,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Download remote documentation sources to the local cache directory.
    """
    sources_path = _resolve_path(Path(sources_path) if sources_path else DEFAULT_SOURCES_PATH)
    content_dir = _resolve_path(Path(content_dir) if content_dir else DEFAULT_CONTENT_DIR)
    metadata_path = _resolve_path(Path(metadata_path) if metadata_path else DEFAULT_METADATA_PATH)

    sources = _parse_sources(sources_path)
    if not sources:
        return {
            "status": "no_sources",
            "content_dir": str(content_dir),
            "sources_path": str(sources_path)
        }

    metadata = _load_metadata(metadata_path)
    if not force_refresh and not _refresh_due(metadata, refresh_hours):
        return {
            "status": "fresh",
            "content_dir": str(content_dir),
            "last_refreshed_at": metadata.get("last_refreshed_at"),
            "sources": metadata.get("sources", [])
        }

    if content_dir.exists():
        for item in content_dir.iterdir():
            if item.is_dir():
                for sub in item.rglob("*"):
                    if sub.is_file():
                        sub.unlink(missing_ok=True)
                for sub in sorted(item.rglob("*"), reverse=True):
                    if sub.is_dir():
                        sub.rmdir()
                item.rmdir()
            elif item.is_file():
                item.unlink(missing_ok=True)

    content_dir.mkdir(parents=True, exist_ok=True)

    timeout = aiohttp.ClientTimeout(total=60)
    headers = {"User-Agent": "LoCo-RAG/0.1"}

    stats = []
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for source in sources:
            if source.source_type == "url_list":
                source_stats = await _download_url_source(
                    session,
                    source,
                    target_root=content_dir,
                    max_bytes=max_file_bytes
                )
            else:
                source_stats = await _download_github_source(
                    session,
                    source,
                    target_root=content_dir,
                    max_bytes=max_file_bytes,
                    default_max_files=max_files_per_source
                )
            stats.append({
                "id": source.source_id,
                "type": source.source_type,
                **source_stats
            })

    metadata = {
        "last_refreshed_at": time.time(),
        "sources": stats
    }
    _write_metadata(metadata_path, metadata)

    total_downloaded = sum(item.get("downloaded", 0) for item in stats)
    total_failed = sum(item.get("failed", 0) for item in stats)

    return {
        "status": "refreshed",
        "content_dir": str(content_dir),
        "total_downloaded": total_downloaded,
        "total_failed": total_failed,
        "sources": stats
    }
