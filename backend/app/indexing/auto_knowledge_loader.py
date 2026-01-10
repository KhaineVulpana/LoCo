"""
Auto-knowledge loader for shared coding docs.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import structlog

from app.indexing.domain_indexer import KnowledgeIndexer

logger = structlog.get_logger()

DEFAULT_DOC_DIRS = [
    Path("docs"),
    Path("backend") / "data" / "vscode" / "docs",
    Path("backend") / "data" / "remote-docs" / "content"
]

DEFAULT_DOC_FILES = [
    Path("README.md"),
    Path("QUICKSTART.md"),
    Path("FEATURES.md"),
    Path("ACE_README.md"),
    Path("BUILD_SUMMARY.md"),
    Path("packaging") / "README.md",
    Path("modules") / "vscode-extension" / "README.md",
    Path("modules") / "3d-gen-desktop" / "README.md",
    Path("modules") / "android-app" / "README.md"
]


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_paths(paths: List[Path], repo_root: Path) -> List[Path]:
    resolved = []
    for path in paths:
        if path.is_absolute():
            resolved.append(path)
        else:
            resolved.append(repo_root / path)
    return resolved


def resolve_sources(
    dir_overrides: Optional[List[str]] = None,
    file_overrides: Optional[List[str]] = None
) -> Tuple[List[Path], List[Path]]:
    repo_root = _resolve_repo_root()
    dir_paths = [Path(p) for p in (dir_overrides or DEFAULT_DOC_DIRS)]
    file_paths = [Path(p) for p in (file_overrides or DEFAULT_DOC_FILES)]

    resolved_dirs = [
        path for path in _resolve_paths(dir_paths, repo_root)
        if path.exists() and path.is_dir()
    ]
    resolved_files = [
        path for path in _resolve_paths(file_paths, repo_root)
        if path.exists() and path.is_file()
    ]

    return resolved_dirs, resolved_files


async def ensure_shared_knowledge(
    embedding_manager,
    vector_store,
    dir_overrides: Optional[List[str]] = None,
    file_overrides: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Ensure shared coding docs are indexed into loco_rag_shared.
    This collection is rebuilt each startup to avoid duplicates.
    """
    frontend_id = "shared"
    collection_name = f"loco_rag_{frontend_id}"
    docs_dirs, docs_files = resolve_sources(dir_overrides, file_overrides)

    try:
        vector_store.delete_collection(collection_name)
    except Exception:
        pass

    vector_store.create_collection(
        collection_name=collection_name,
        vector_size=embedding_manager.get_dimensions()
    )

    if not docs_dirs and not docs_files:
        logger.warning("shared_knowledge_sources_missing")
        return {
            "status": "no_sources",
            "collection": collection_name,
            "dirs": [],
            "files": []
        }

    indexer = KnowledgeIndexer(
        frontend_id=frontend_id,
        embedding_manager=embedding_manager,
        vector_store=vector_store
    )

    totals = {
        "total_files": 0,
        "indexed": 0,
        "failed": 0,
        "skipped": 0,
        "doc_roots": [str(path) for path in docs_dirs],
        "doc_files": [str(path) for path in docs_files]
    }

    for docs_dir in docs_dirs:
        stats = await indexer.index_documentation(str(docs_dir))
        totals["total_files"] += stats.get("total_files", 0)
        totals["indexed"] += stats.get("indexed", 0)
        totals["failed"] += stats.get("failed", 0)

    if docs_files:
        file_stats = await indexer.index_files([str(path) for path in docs_files])
        totals["total_files"] += file_stats.get("total_files", 0)
        totals["indexed"] += file_stats.get("indexed", 0)
        totals["failed"] += file_stats.get("failed", 0)
        totals["skipped"] += file_stats.get("skipped", 0)

    return {
        "status": "indexed",
        "collection": collection_name,
        "stats": totals
    }
