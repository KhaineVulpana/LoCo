"""
VS Code extension documentation loader for RAG indexing.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import structlog

from app.indexing.domain_indexer import KnowledgeIndexer

logger = structlog.get_logger()

DEFAULT_DOCS_PATH = Path("backend") / "data" / "vscode" / "docs"


def resolve_docs_path(path_override: Optional[str] = None) -> Path:
    """Resolve docs path relative to repo root when needed."""
    if path_override:
        path = Path(path_override)
    else:
        path = DEFAULT_DOCS_PATH

    if path.is_absolute():
        return path

    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / path


async def ensure_vscode_docs(
    embedding_manager,
    vector_store,
    path_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ensure VS Code extension docs are indexed into loco_rag_vscode.
    """
    frontend_id = "vscode"
    collection_name = f"loco_rag_{frontend_id}"
    docs_path = resolve_docs_path(path_override)

    vector_store.create_collection(
        collection_name=collection_name,
        vector_size=embedding_manager.get_dimensions()
    )

    try:
        info = vector_store.get_collection_info(collection_name)
        points_count = info.get("points_count", 0)
    except Exception:
        points_count = 0

    if points_count > 0:
        logger.info("vscode_docs_already_indexed",
                   frontend_id=frontend_id,
                   points=points_count)
        return {
            "status": "already_indexed",
            "points": points_count,
            "path": str(docs_path)
        }

    if not docs_path.exists():
        logger.error("vscode_docs_missing",
                    frontend_id=frontend_id,
                    path=str(docs_path))
        return {
            "status": "missing",
            "path": str(docs_path)
        }

    indexer = KnowledgeIndexer(
        frontend_id=frontend_id,
        embedding_manager=embedding_manager,
        vector_store=vector_store
    )

    stats = await indexer.index_documentation(str(docs_path))
    return {
        "status": "indexed",
        "stats": stats,
        "path": str(docs_path)
    }
