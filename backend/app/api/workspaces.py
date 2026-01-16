"""
Workspace API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import get_db
from app.core.database import async_session_maker
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.indexer import FileIndexer
from app.indexing.file_watcher import WorkspaceFileWatcher, is_watchdog_available
from app.core.runtime import get_embedding_manager, get_vector_store
from app.core.workspace_paths import resolve_workspace_path, paths_equal
import structlog

logger = structlog.get_logger()

router = APIRouter()
indexing_tasks = {}
indexing_tasks_lock = asyncio.Lock()
workspace_watchers = {}
workspace_watchers_lock = asyncio.Lock()


class WorkspaceCreate(BaseModel):
    path: str
    name: Optional[str] = None
    module_id: str = "vscode"
    auto_index: bool = False
    auto_watch: bool = False
    use_polling: bool = False


class WorkspaceResponse(BaseModel):
    id: str
    path: str
    name: str
    created_at: str
    last_indexed_at: Optional[str]
    index_status: str
    index_progress: float
    total_files: int
    indexed_files: int
    total_chunks: int


class WorkspaceIndexRequest(BaseModel):
    module_id: str = "vscode"
    watch: bool = False
    use_polling: bool = False


class WorkspaceWatchRequest(BaseModel):
    module_id: str = "vscode"
    use_polling: bool = False


class WorkspacePolicy(BaseModel):
    allowed_read_globs: List[str]
    allowed_write_globs: List[str]
    blocked_globs: List[str]
    command_approval: Literal["always", "never", "prompt"]
    allowed_commands: List[str]
    blocked_commands: List[str]
    network_enabled: bool
    auto_approve_simple_changes: bool
    auto_approve_tests: bool
    auto_approve_tools: List[str]


class WorkspacePolicyUpdate(BaseModel):
    allowed_read_globs: Optional[List[str]] = None
    allowed_write_globs: Optional[List[str]] = None
    blocked_globs: Optional[List[str]] = None
    command_approval: Optional[Literal["always", "never", "prompt"]] = None
    allowed_commands: Optional[List[str]] = None
    blocked_commands: Optional[List[str]] = None
    network_enabled: Optional[bool] = None
    auto_approve_simple_changes: Optional[bool] = None
    auto_approve_tests: Optional[bool] = None
    auto_approve_tools: Optional[List[str]] = None


DEFAULT_POLICY: Dict[str, Any] = {
    "allowed_read_globs": ["**/*"],
    "allowed_write_globs": ["**/*"],
    "blocked_globs": [".git/**", "node_modules/**"],
    "command_approval": "prompt",
    "allowed_commands": [],
    "blocked_commands": [],
    "network_enabled": False,
    "auto_approve_simple_changes": False,
    "auto_approve_tests": False,
    "auto_approve_tools": []
}


async def _schedule_workspace_index(
    workspace_id: str,
    workspace_path: str,
    module_id: str,
    embedding_manager: EmbeddingManager,
    vector_store: VectorStore,
    auto_watch: bool = False,
    use_polling: bool = False
) -> None:
    """Start workspace indexing in a background task."""
    async with indexing_tasks_lock:
        existing = indexing_tasks.get(workspace_id)
        if existing and not existing.done():
            return

        async def _run_index():
            async with async_session_maker() as session:
                indexer = FileIndexer(
                    workspace_id=workspace_id,
                    module_id=module_id,
                    workspace_path=workspace_path,
                    embedding_manager=embedding_manager,
                    vector_store=vector_store,
                    db_session=session
                )
                await indexer.index_workspace()

        task = asyncio.create_task(_run_index())
        indexing_tasks[workspace_id] = task

        # Cleanup callback needs lock too
        async def _cleanup_task(_):
            async with indexing_tasks_lock:
                indexing_tasks.pop(workspace_id, None)

        task.add_done_callback(lambda t: asyncio.create_task(_cleanup_task(t)))
    if auto_watch:
        def _start_watch(_):
            asyncio.create_task(
                _start_workspace_watch_safe(
                    workspace_id=workspace_id,
                    workspace_path=workspace_path,
                    module_id=module_id,
                    embedding_manager=embedding_manager,
                    vector_store=vector_store,
                    use_polling=use_polling
                )
            )
        task.add_done_callback(_start_watch)


def _validate_workspace_path(workspace_id: str, workspace_path: str) -> None:
    path = Path(workspace_path)
    if not path.exists():
        logger.warning(
            "workspace_path_missing",
            workspace_id=workspace_id,
            path=workspace_path
        )
        raise FileNotFoundError(f"Workspace path not found: {workspace_path}")
    if not path.is_dir():
        logger.warning(
            "workspace_path_not_directory",
            workspace_id=workspace_id,
            path=workspace_path
        )
        raise NotADirectoryError(f"Workspace path is not a directory: {workspace_path}")


async def _resolve_workspace_path_in_db(
    db: AsyncSession,
    workspace_id: str,
    stored_path: str,
    workspace_name: Optional[str] = None
) -> str:
    resolved_path, source = resolve_workspace_path(stored_path, workspace_name)
    if source == "missing":
        logger.warning(
            "workspace_path_unresolved",
            workspace_id=workspace_id,
            path=stored_path
        )
        return resolved_path

    if not paths_equal(stored_path, resolved_path):
        now = datetime.now(timezone.utc).isoformat()
        try:
            await db.execute(text("""
                UPDATE workspaces
                SET path = :path,
                    updated_at = :updated_at
                WHERE id = :workspace_id
            """), {
                "workspace_id": workspace_id,
                "path": resolved_path,
                "updated_at": now
            })
            await db.commit()
        except Exception as exc:
            logger.warning(
                "workspace_path_update_failed",
                workspace_id=workspace_id,
                path=resolved_path,
                error=str(exc)
            )
        else:
            logger.info(
                "workspace_path_updated",
                workspace_id=workspace_id,
                path=resolved_path,
                source=source
            )

    return resolved_path


async def _start_workspace_watch(
    workspace_id: str,
    workspace_path: str,
    module_id: str,
    embedding_manager: EmbeddingManager,
    vector_store: VectorStore,
    use_polling: bool = False
) -> WorkspaceFileWatcher:
    if not is_watchdog_available():
        raise RuntimeError("watchdog_not_available")

    async with workspace_watchers_lock:
        existing = workspace_watchers.get(workspace_id)
        if existing:
            if existing.module_id != module_id or existing.use_polling != use_polling:
                await existing.stop()
                workspace_watchers.pop(workspace_id, None)
            elif existing.is_running():
                return existing

        _validate_workspace_path(workspace_id, workspace_path)

        watcher = WorkspaceFileWatcher(
            workspace_id=workspace_id,
            module_id=module_id,
            workspace_path=workspace_path,
            embedding_manager=embedding_manager,
            vector_store=vector_store,
            db_session_maker=async_session_maker,
            use_polling=use_polling
        )
        workspace_watchers[workspace_id] = watcher
        try:
            await watcher.start()
        except Exception:
            workspace_watchers.pop(workspace_id, None)
            raise
        return watcher


async def _start_workspace_watch_safe(
    workspace_id: str,
    workspace_path: str,
    module_id: str,
    embedding_manager: EmbeddingManager,
    vector_store: VectorStore,
    use_polling: bool = False
) -> None:
    try:
        await _start_workspace_watch(
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            module_id=module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store,
            use_polling=use_polling
        )
    except (FileNotFoundError, NotADirectoryError) as exc:
        logger.warning(
            "workspace_watch_start_failed",
            workspace_id=workspace_id,
            path=workspace_path,
            error=str(exc)
        )
    except Exception as exc:
        logger.exception(
            "workspace_watch_start_failed",
            workspace_id=workspace_id,
            path=workspace_path,
            error=str(exc)
        )


async def _stop_workspace_watch(workspace_id: str) -> bool:
    async with workspace_watchers_lock:
        watcher = workspace_watchers.get(workspace_id)
        if not watcher:
            return False
        await watcher.stop()
        workspace_watchers.pop(workspace_id, None)
        return True


def _parse_list(value: Optional[str], fallback: List[str]) -> List[str]:
    if not value:
        return list(fallback)
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else list(fallback)
    except json.JSONDecodeError:
        return list(fallback)


def _policy_from_row(row: Optional[Any]) -> Dict[str, Any]:
    if not row:
        return {**DEFAULT_POLICY}

    (
        allowed_read_globs,
        allowed_write_globs,
        blocked_globs,
        command_approval,
        allowed_commands,
        blocked_commands,
        network_enabled,
        auto_simple,
        auto_tests,
        auto_tools
    ) = row

    return {
        "allowed_read_globs": _parse_list(allowed_read_globs, DEFAULT_POLICY["allowed_read_globs"]),
        "allowed_write_globs": _parse_list(allowed_write_globs, DEFAULT_POLICY["allowed_write_globs"]),
        "blocked_globs": _parse_list(blocked_globs, DEFAULT_POLICY["blocked_globs"]),
        "command_approval": (command_approval or DEFAULT_POLICY["command_approval"]),
        "allowed_commands": _parse_list(allowed_commands, DEFAULT_POLICY["allowed_commands"]),
        "blocked_commands": _parse_list(blocked_commands, DEFAULT_POLICY["blocked_commands"]),
        "network_enabled": bool(network_enabled),
        "auto_approve_simple_changes": bool(auto_simple),
        "auto_approve_tests": bool(auto_tests),
        "auto_approve_tools": _parse_list(auto_tools, DEFAULT_POLICY["auto_approve_tools"])
    }


@router.post("/register", response_model=WorkspaceResponse)
async def register_workspace(
    workspace: WorkspaceCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new workspace or return existing"""
    name = workspace.name or Path(workspace.path).name

    logger.info("registering_workspace", path=workspace.path, name=name)

    # Check if workspace already exists
    check_query = text("""
        SELECT id, path, name, created_at, last_indexed_at,
               index_status, index_progress, total_files, indexed_files, total_chunks
        FROM workspaces
        WHERE path = :path AND deleted_at IS NULL
    """)

    result = await db.execute(check_query, {"path": workspace.path})
    existing = result.fetchone()

    if existing:
        logger.info("workspace_already_exists", path=workspace.path, id=existing[0])
        resolved_path = await _resolve_workspace_path_in_db(
            db=db,
            workspace_id=existing[0],
            stored_path=existing[1],
            workspace_name=existing[2]
        )
        if workspace.auto_index or workspace.auto_watch:
            try:
                embedding_manager = get_embedding_manager()
                vector_store = get_vector_store()
                await _schedule_workspace_index(
                    workspace_id=existing[0],
                    workspace_path=resolved_path,
                    module_id=workspace.module_id,
                    embedding_manager=embedding_manager,
                    vector_store=vector_store,
                    auto_watch=workspace.auto_watch,
                    use_polling=workspace.use_polling
                )
            except Exception as e:
                logger.warning("workspace_auto_index_failed",
                               workspace_id=existing[0],
                               error=str(e))
        return WorkspaceResponse(
            id=existing[0],
            path=resolved_path,
            name=existing[2],
            created_at=existing[3],
            last_indexed_at=existing[4],
            index_status=existing[5],
            index_progress=existing[6] or 0.0,
            total_files=existing[7] or 0,
            indexed_files=existing[8] or 0,
            total_chunks=existing[9] or 0
        )

    # Insert new workspace
    workspace_id = str(uuid.uuid4())
    insert_query = text("""
        INSERT INTO workspaces (
            id, path, name, created_at, updated_at, index_status,
            index_progress, total_files, indexed_files, total_chunks
        )
        VALUES (
            :id, :path, :name, :created_at, :updated_at, :status,
            0.0, 0, 0, 0
        )
    """)

    now = datetime.now(timezone.utc).isoformat()

    await db.execute(insert_query, {
        "id": workspace_id,
        "path": workspace.path,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "status": "pending"
    })

    await db.execute(text("""
        INSERT OR IGNORE INTO workspace_policies (workspace_id, created_at, updated_at)
        VALUES (:workspace_id, :created_at, :updated_at)
    """), {
        "workspace_id": workspace_id,
        "created_at": now,
        "updated_at": now
    })

    await db.commit()

    if workspace.auto_index or workspace.auto_watch:
        try:
            embedding_manager = get_embedding_manager()
            vector_store = get_vector_store()
            await _schedule_workspace_index(
                workspace_id=workspace_id,
                workspace_path=workspace.path,
                module_id=workspace.module_id,
                embedding_manager=embedding_manager,
                vector_store=vector_store,
                auto_watch=workspace.auto_watch,
                use_polling=workspace.use_polling
            )
        except Exception as e:
            logger.warning("workspace_auto_index_failed",
                           workspace_id=workspace_id,
                           error=str(e))

    return WorkspaceResponse(
        id=workspace_id,
        path=workspace.path,
        name=name,
        created_at=now,
        last_indexed_at=None,
        index_status="pending",
        index_progress=0.0,
        total_files=0,
        indexed_files=0,
        total_chunks=0
    )


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    """List all registered workspaces"""
    query = text("""
        SELECT id, path, name, created_at, last_indexed_at,
               index_status, index_progress, total_files, indexed_files, total_chunks
        FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
    """)

    result = await db.execute(query)
    rows = result.fetchall()

    responses: List[WorkspaceResponse] = []
    for row in rows:
        resolved_path = await _resolve_workspace_path_in_db(
            db=db,
            workspace_id=row[0],
            stored_path=row[1],
            workspace_name=row[2]
        )
        responses.append(WorkspaceResponse(
            id=row[0],
            path=resolved_path,
            name=row[2],
            created_at=row[3],
            last_indexed_at=row[4],
            index_status=row[5],
            index_progress=row[6] or 0.0,
            total_files=row[7] or 0,
            indexed_files=row[8] or 0,
            total_chunks=row[9] or 0
        ))

    return responses


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get workspace by ID"""
    query = text("""
        SELECT id, path, name, created_at, last_indexed_at,
               index_status, index_progress, total_files, indexed_files, total_chunks
        FROM workspaces
        WHERE id = :workspace_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"workspace_id": workspace_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")

    resolved_path = await _resolve_workspace_path_in_db(
        db=db,
        workspace_id=row[0],
        stored_path=row[1],
        workspace_name=row[2]
    )

    return WorkspaceResponse(
        id=row[0],
        path=resolved_path,
        name=row[2],
        created_at=row[3],
        last_indexed_at=row[4],
        index_status=row[5],
        index_progress=row[6] or 0.0,
        total_files=row[7] or 0,
        indexed_files=row[8] or 0,
        total_chunks=row[9] or 0
    )


@router.get("/{workspace_id}/policy", response_model=WorkspacePolicy)
async def get_workspace_policy(
    workspace_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get workspace policy."""
    workspace = await db.execute(text("""
        SELECT 1 FROM workspaces WHERE id = :workspace_id AND deleted_at IS NULL
    """), {"workspace_id": workspace_id})
    if not workspace.fetchone():
        raise HTTPException(status_code=404, detail="Workspace not found")

    result = await db.execute(text("""
        SELECT allowed_read_globs,
               allowed_write_globs,
               blocked_globs,
               command_approval,
               allowed_commands,
               blocked_commands,
               network_enabled,
               auto_approve_simple_changes,
               auto_approve_tests,
               auto_approve_tools
        FROM workspace_policies
        WHERE workspace_id = :workspace_id
    """), {"workspace_id": workspace_id})

    policy = _policy_from_row(result.fetchone())
    return WorkspacePolicy(**policy)


@router.put("/{workspace_id}/policy", response_model=WorkspacePolicy)
async def update_workspace_policy(
    workspace_id: str,
    update: WorkspacePolicyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update workspace policy."""
    workspace = await db.execute(text("""
        SELECT 1 FROM workspaces WHERE id = :workspace_id AND deleted_at IS NULL
    """), {"workspace_id": workspace_id})
    if not workspace.fetchone():
        raise HTTPException(status_code=404, detail="Workspace not found")

    result = await db.execute(text("""
        SELECT allowed_read_globs,
               allowed_write_globs,
               blocked_globs,
               command_approval,
               allowed_commands,
               blocked_commands,
               network_enabled,
               auto_approve_simple_changes,
               auto_approve_tests,
               auto_approve_tools
        FROM workspace_policies
        WHERE workspace_id = :workspace_id
    """), {"workspace_id": workspace_id})
    current = _policy_from_row(result.fetchone())

    payload = update.model_dump(exclude_unset=True)
    merged = {**current, **payload}

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(text("""
        INSERT OR IGNORE INTO workspace_policies (
            workspace_id, created_at, updated_at
        )
        VALUES (:workspace_id, :created_at, :updated_at)
    """), {
        "workspace_id": workspace_id,
        "created_at": now,
        "updated_at": now
    })

    await db.execute(text("""
        UPDATE workspace_policies
        SET allowed_read_globs = :allowed_read_globs,
            allowed_write_globs = :allowed_write_globs,
            blocked_globs = :blocked_globs,
            command_approval = :command_approval,
            allowed_commands = :allowed_commands,
            blocked_commands = :blocked_commands,
            network_enabled = :network_enabled,
            auto_approve_simple_changes = :auto_approve_simple_changes,
            auto_approve_tests = :auto_approve_tests,
            auto_approve_tools = :auto_approve_tools,
            updated_at = :updated_at
        WHERE workspace_id = :workspace_id
    """), {
        "workspace_id": workspace_id,
        "allowed_read_globs": json.dumps(merged["allowed_read_globs"]),
        "allowed_write_globs": json.dumps(merged["allowed_write_globs"]),
        "blocked_globs": json.dumps(merged["blocked_globs"]),
        "command_approval": merged["command_approval"],
        "allowed_commands": json.dumps(merged["allowed_commands"]),
        "blocked_commands": json.dumps(merged["blocked_commands"]),
        "network_enabled": 1 if merged["network_enabled"] else 0,
        "auto_approve_simple_changes": 1 if merged["auto_approve_simple_changes"] else 0,
        "auto_approve_tests": 1 if merged["auto_approve_tests"] else 0,
        "auto_approve_tools": json.dumps(merged["auto_approve_tools"]),
        "updated_at": now
    })

    await db.commit()

    return WorkspacePolicy(**merged)


@router.post("/{workspace_id}/index")
async def index_workspace(
    workspace_id: str,
    request: WorkspaceIndexRequest,
    db: AsyncSession = Depends(get_db),
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Index a workspace for RAG retrieval."""
    query = text("""
        SELECT path, name FROM workspaces
        WHERE id = :workspace_id AND deleted_at IS NULL
    """)
    result = await db.execute(query, {"workspace_id": workspace_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")

    workspace_path = await _resolve_workspace_path_in_db(
        db=db,
        workspace_id=workspace_id,
        stored_path=row[0],
        workspace_name=row[1]
    )

    indexer = FileIndexer(
        workspace_id=workspace_id,
        module_id=request.module_id,
        workspace_path=workspace_path,
        embedding_manager=embedding_manager,
        vector_store=vector_store,
        db_session=db
    )

    stats = await indexer.index_workspace()
    if request.watch:
        try:
            await _start_workspace_watch(
                workspace_id=workspace_id,
                workspace_path=workspace_path,
                module_id=request.module_id,
                embedding_manager=embedding_manager,
                vector_store=vector_store,
                use_polling=request.use_polling
            )
        except Exception as e:
            logger.warning("workspace_watch_start_failed",
                           workspace_id=workspace_id,
                           error=str(e))

    return {
        "success": True,
        "workspace_id": workspace_id,
        "module_id": request.module_id,
        "stats": stats
    }


@router.get("/{workspace_id}/index/stream")
async def stream_index_progress(
    workspace_id: str,
    module_id: str = "vscode",
    auto_start: bool = False,
    auto_watch: bool = False,
    use_polling: bool = False
):
    """Stream workspace indexing progress via SSE."""

    async def event_generator():
        if auto_start:
            try:
                embedding_manager = get_embedding_manager()
                vector_store = get_vector_store()
                await _schedule_workspace_index(
                    workspace_id=workspace_id,
                    workspace_path=workspace_path,
                    module_id=module_id,
                    embedding_manager=embedding_manager,
                    vector_store=vector_store,
                    auto_watch=auto_watch,
                    use_polling=use_polling
                )
            except Exception as e:
                payload = {"error": str(e)}
                yield f"data: {json.dumps(payload)}\n\n"
                return

        async with async_session_maker() as session:
            while True:
                result = await session.execute(text("""
                    SELECT index_status, index_progress, total_files, indexed_files,
                           total_chunks, last_indexed_at
                    FROM workspaces
                    WHERE id = :workspace_id AND deleted_at IS NULL
                """), {"workspace_id": workspace_id})
                row = result.fetchone()
                if not row:
                    payload = {"error": "workspace_not_found"}
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

                payload = {
                    "workspace_id": workspace_id,
                    "index_status": row[0],
                    "index_progress": row[1] or 0.0,
                    "total_files": row[2] or 0,
                    "indexed_files": row[3] or 0,
                    "total_chunks": row[4] or 0,
                    "last_indexed_at": row[5]
                }

                yield f"data: {json.dumps(payload)}\n\n"

                if row[0] in ("complete", "partial", "failed"):
                    return

                await asyncio.sleep(0.5)

    workspace_path = None
    async with async_session_maker() as session:
        result = await session.execute(text("""
            SELECT path, name FROM workspaces
            WHERE id = :workspace_id AND deleted_at IS NULL
        """), {"workspace_id": workspace_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace_path = await _resolve_workspace_path_in_db(
            db=session,
            workspace_id=workspace_id,
            stored_path=row[0],
            workspace_name=row[1]
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{workspace_id}/watch/start")
async def start_workspace_watch(
    workspace_id: str,
    request: WorkspaceWatchRequest,
    db: AsyncSession = Depends(get_db),
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Start file watcher for incremental indexing."""
    if not is_watchdog_available():
        raise HTTPException(status_code=503, detail="File watcher not available")

    result = await db.execute(text("""
        SELECT path, name FROM workspaces
        WHERE id = :workspace_id AND deleted_at IS NULL
    """), {"workspace_id": workspace_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")

    workspace_path = await _resolve_workspace_path_in_db(
        db=db,
        workspace_id=workspace_id,
        stored_path=row[0],
        workspace_name=row[1]
    )
    try:
        await _start_workspace_watch(
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            module_id=request.module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store,
            use_polling=request.use_polling
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path not found: {workspace_path}"
        )
    except NotADirectoryError:
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path is not a directory: {workspace_path}"
        )

    return {"success": True, "running": True}


@router.post("/{workspace_id}/watch/stop")
async def stop_workspace_watch(workspace_id: str):
    """Stop file watcher for incremental indexing."""
    stopped = await _stop_workspace_watch(workspace_id)
    return {"success": True, "running": False, "stopped": stopped}


@router.get("/{workspace_id}/watch/status")
async def workspace_watch_status(workspace_id: str):
    """Check whether a workspace watcher is running."""
    async with workspace_watchers_lock:
        watcher = workspace_watchers.get(workspace_id)
        return {
            "running": bool(watcher and watcher.is_running()),
            "module_id": watcher.module_id if watcher else None
        }
