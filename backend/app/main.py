"""
LoCo Agent Local - Main Server Entry Point
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager, contextmanager
import asyncio
import structlog
import logging
from typing import Optional
import secrets
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import init_db, async_session_maker
from app.core.config import settings

# Configure logging - silence noisy libraries
logging.basicConfig(level=logging.INFO)  # Set root logger to INFO
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Silence HTTP request logs

# Configure structlog for clean output (INFO and above only)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Set structlog minimum level to INFO (hide debug messages)
logging.getLogger().setLevel(logging.INFO)
from app.core.workspace_paths import resolve_workspace_path, paths_equal
from app.core import runtime
from app.core.qdrant_manager import QdrantManager
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.auto_knowledge_loader import ensure_shared_knowledge
from app.indexing.remote_docs_loader import ensure_remote_docs
from app.indexing.training_data_loader import ensure_3d_gen_training_data
from app.indexing.vscode_docs_loader import ensure_vscode_docs
from app.core.model_manager import ModelManager, ModelConfig
from app.api import workspaces, sessions, models as models_api, knowledge, ace
from app.api import agents as agents_api, folders as folders_api, uploads as uploads_api
from app.api import search as search_api, exports as exports_api
from app.core.auth import verify_token
from app.agent import Agent
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Store active agents per session
active_agents = {}
active_agents_lock = asyncio.Lock()

UI_ROUTE_PREFIX = "/app"


def _accepts_html(scope: dict) -> bool:
    headers = scope.get("headers") or []
    for key, value in headers:
        if key == b"accept" and b"text/html" in value:
            return True
    return False


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict):
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response
        if not _accepts_html(scope):
            return response
        index_path, _ = self.lookup_path("index.html")
        if index_path:
            return FileResponse(index_path)
        return response


def _mount_ui(app: FastAPI) -> None:
    ui_dist_path = settings.UI_DIST_PATH
    if not ui_dist_path:
        return
    dist_path = Path(ui_dist_path)
    if not dist_path.is_dir():
        logger.warning("ui_dist_missing", path=ui_dist_path)
        return

    app.mount(UI_ROUTE_PREFIX, SPAStaticFiles(directory=dist_path, html=True), name="ui")

    async def ui_root():
        return RedirectResponse(f"{UI_ROUTE_PREFIX}/")

    app.add_api_route("/", ui_root, include_in_schema=False)
    logger.info("ui_mounted", path=str(dist_path), route=UI_ROUTE_PREFIX)


async def _store_session_message(
    session_id: str,
    role: str,
    content: str,
    context: Optional[dict] = None,
    metadata: Optional[dict] = None
) -> None:
    if not content:
        return
    now = datetime.now(timezone.utc).isoformat()
    context_json = json.dumps(context, ensure_ascii=True) if context else None
    metadata_json = json.dumps(metadata, ensure_ascii=True) if metadata else None

    async with async_session_maker() as db:
        result = await db.execute(text("""
            INSERT INTO session_messages (
                session_id, role, content, context_json, metadata_json, created_at
            )
            VALUES (
                :session_id, :role, :content, :context_json, :metadata_json, :created_at
            )
        """), {
            "session_id": session_id,
            "role": role,
            "content": content,
            "context_json": context_json,
            "metadata_json": metadata_json,
            "created_at": now
        })

        message_id = getattr(result, "lastrowid", None)
        if message_id is None:
            id_result = await db.execute(text("SELECT last_insert_rowid()"))
            message_id = id_result.scalar()

        try:
            await db.execute(text("""
                INSERT INTO session_messages_fts (rowid, session_id, role, content, created_at)
                VALUES (:rowid, :session_id, :role, :content, :created_at)
            """), {
                "rowid": message_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "created_at": now
            })
        except Exception as exc:
            logger.warning("fts_insert_failed", error=str(exc), session_id=session_id)

        await db.execute(text("""
            UPDATE sessions
            SET updated_at = :updated_at,
                total_messages = COALESCE(total_messages, 0) + 1
            WHERE id = :session_id
        """), {"updated_at": now, "session_id": session_id})

        if role == "user":
            title = content.strip().splitlines()[0][:80]
            await db.execute(text("""
                UPDATE sessions
                SET title = COALESCE(title, :title)
                WHERE id = :session_id
            """), {"title": title, "session_id": session_id})

        await db.commit()


@contextmanager
def _suppress_boot_indexing_logs():
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        root_logger.setLevel(previous_level)


async def _resolve_workspace_path_for_session(
    db: AsyncSession,
    workspace_id: str,
    stored_path: str,
    workspace_name: Optional[str]
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""

    logger.info("server_starting", version=settings.VERSION)

    # Initialize database
    await init_db()

    # Start Qdrant if not running (only if not in Docker)
    qdrant_available = False
    if settings.QDRANT_HOST == "localhost":
        qdrant_manager = QdrantManager(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        qdrant_available = await qdrant_manager.ensure_running()

        if not qdrant_available:
            logger.warning("qdrant_unavailable",
                         message="Vector search will be disabled. Start Qdrant manually with: docker compose up -d qdrant")
    else:
        logger.info("qdrant_external", host=settings.QDRANT_HOST)
        qdrant_available = True  # Assume external Qdrant is available

    # Initialize RAG components (only if Qdrant is available)
    if qdrant_available:
        try:
            logger.info("loading_embedding_model", model=settings.EMBEDDING_MODEL)
            runtime.embedding_manager = EmbeddingManager(
                model_name=settings.EMBEDDING_MODEL
            )

            logger.info("connecting_to_vector_store",
                       host=settings.QDRANT_HOST,
                       port=settings.QDRANT_PORT)
            runtime.vector_store = VectorStore(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT
            )

            logger.info("rag_components_ready",
                       embedding_model=runtime.embedding_manager.get_model_name(),
                       embedding_dimensions=runtime.embedding_manager.get_dimensions())

            ace_modules = ["vscode", "android", "3d-gen"]
            logger.info("initializing_ace_collections", modules=ace_modules)
            for module_id in ace_modules:
                collection_name = f"loco_ace_{module_id}"
                try:
                    runtime.vector_store.create_collection(
                        collection_name=collection_name,
                        vector_size=runtime.embedding_manager.get_dimensions()
                    )
                except Exception as e:
                    logger.error("ace_collection_init_failed",
                                module_id=module_id,
                                error=str(e))

            with _suppress_boot_indexing_logs():
                try:
                    training_status = await ensure_3d_gen_training_data(
                        embedding_manager=runtime.embedding_manager,
                        vector_store=runtime.vector_store
                    )
                    logger.info("training_data_loader_complete", status=training_status)
                except Exception as e:
                    logger.error("training_data_loader_failed", error=str(e))

                try:
                    vscode_docs_status = await ensure_vscode_docs(
                        embedding_manager=runtime.embedding_manager,
                        vector_store=runtime.vector_store
                    )
                    logger.info("vscode_docs_loader_complete", status=vscode_docs_status)
                except Exception as e:
                    logger.error("vscode_docs_loader_failed", error=str(e))

                try:
                    if settings.REMOTE_DOCS_ENABLED:
                        remote_docs_status = await ensure_remote_docs(
                            refresh_hours=settings.REMOTE_DOCS_REFRESH_HOURS
                        )
                        logger.info("remote_docs_loader_complete", status=remote_docs_status)

                    shared_knowledge_status = await ensure_shared_knowledge(
                        embedding_manager=runtime.embedding_manager,
                        vector_store=runtime.vector_store
                    )
                    logger.info("shared_knowledge_loader_complete", status=shared_knowledge_status)
                except Exception as e:
                    logger.error("shared_knowledge_loader_failed", error=str(e))
        except Exception as e:
            logger.error("rag_initialization_failed",
                        error=str(e),
                        message="Vector search will be disabled")
            runtime.embedding_manager = None
            runtime.vector_store = None
    else:
        logger.info("rag_disabled", reason="Qdrant not available")

    # Initialize model manager
    logger.info("initializing_model_manager")
    runtime.model_manager = ModelManager()

    # Load default model
    try:
        logger.info("loading_default_model",
                   provider=settings.MODEL_PROVIDER,
                   model=settings.MODEL_NAME,
                   url=settings.MODEL_URL)

        default_model = await runtime.model_manager.switch_model(
            provider=settings.MODEL_PROVIDER,
            model_name=settings.MODEL_NAME,
            url=settings.MODEL_URL,
            context_window=settings.MAX_CONTEXT_TOKENS
        )

        logger.info("default_model_loaded",
                   provider=settings.MODEL_PROVIDER,
                   model=settings.MODEL_NAME)
    except Exception as e:
        logger.error("default_model_load_failed",
                    error=str(e),
                    message="Chat will not work until a model is loaded")

    logger.info("server_ready",
               embedding_model=runtime.embedding_manager.get_model_name() if runtime.embedding_manager else None,
               model_manager="initialized",
               llm_model=f"{settings.MODEL_PROVIDER}:{settings.MODEL_NAME}" if runtime.model_manager.is_model_loaded() else "none")
    yield

    logger.info("server_shutting_down")

    # Shutdown model manager
    if runtime.model_manager:
        await runtime.model_manager.shutdown()

    # Cleanup resources


app = FastAPI(
    title="LoCo Agent Server",
    description="Local-first coding agent with agentic RAG and ACE",
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to extension origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_mount_ui(app)


# Dependency injection helpers for RAG components
def get_embedding_manager() -> EmbeddingManager:
    """Get the global embedding manager instance"""
    return runtime.get_embedding_manager()


def get_vector_store() -> VectorStore:
    """Get the global vector store instance"""
    return runtime.get_vector_store()


# Health check
@app.get("/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "protocol_version": settings.PROTOCOL_VERSION
    }


# Include routers
app.include_router(workspaces.router, prefix="/v1/workspaces", tags=["workspaces"])
app.include_router(sessions.router, prefix="/v1/sessions", tags=["sessions"])
app.include_router(models_api.router, prefix="/v1/models", tags=["models"])
app.include_router(knowledge.router, prefix="/v1/knowledge", tags=["knowledge"])
app.include_router(ace.router, prefix="/v1/ace", tags=["ace"])
app.include_router(agents_api.router, prefix="/v1/agents", tags=["agents"])
app.include_router(folders_api.router, prefix="/v1/folders", tags=["folders"])
app.include_router(uploads_api.router, prefix="/v1/uploads", tags=["uploads"])
app.include_router(search_api.router, prefix="/v1/search", tags=["search"])
app.include_router(exports_api.router, prefix="/v1/exports", tags=["exports"])


# WebSocket handler for streaming agent interactions
@app.websocket("/v1/sessions/{session_id}/stream")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    WebSocket endpoint for streaming agent interactions
    """
    # Verify token if auth is enabled
    if settings.AUTH_ENABLED:
        token = None
        if authorization:
            token = authorization.replace("Bearer ", "")
        else:
            token = websocket.query_params.get("token")

        if not token or not verify_token(token):
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()

    logger.info("websocket_connected", session_id=session_id)

    send_queue = asyncio.Queue()
    processing_lock = asyncio.Lock()
    agent_tasks = set()

    async def send_loop() -> None:
        try:
            while True:
                message = await send_queue.get()
                if message is None:
                    break
                await websocket.send_json(message)
        except Exception as exc:
            logger.error("websocket_send_error", error=str(exc), session_id=session_id)

    async def enqueue(message: dict) -> None:
        await send_queue.put(message)

    async def send_error(code: str, message_text: str) -> None:
        await enqueue({
            "type": "server.error",
            "error": {
                "code": code,
                "message": message_text
            }
        })

    async def get_or_create_agent(context: dict) -> Optional[Agent]:
        async with async_session_maker() as db:
            session_query = text("""
                SELECT workspace_id, agent_id, model_provider, model_name, model_url,
                       context_window, temperature
                FROM sessions
                WHERE id = :session_id AND deleted_at IS NULL
            """)
            session_result = await db.execute(session_query, {"session_id": session_id})
            session_row = session_result.fetchone()

            if not session_row:
                await send_error("session_not_found", "Session not found")
                return None

            workspace_id = session_row[0]
            agent_id = session_row[1]
            model_provider = session_row[2] or settings.MODEL_PROVIDER
            model_name = session_row[3] or settings.MODEL_NAME
            model_url = session_row[4] or settings.MODEL_URL
            context_window = session_row[5] or settings.MAX_CONTEXT_TOKENS
            temperature = session_row[6] if session_row[6] is not None else 0.7

            if model_url == "":
                model_url = settings.MODEL_URL
            if model_name == "":
                model_name = settings.MODEL_NAME

            workspace_query = text("""
                SELECT path, name FROM workspaces WHERE id = :workspace_id
            """)
            workspace_result = await db.execute(workspace_query, {"workspace_id": workspace_id})
            workspace_row = workspace_result.fetchone()

            if not workspace_row:
                await send_error("workspace_not_found", "Workspace not found")
                return None

            workspace_path = await _resolve_workspace_path_for_session(
                db=db,
                workspace_id=workspace_id,
                stored_path=workspace_row[0],
                workspace_name=workspace_row[1]
            )

            agent_config = None
            if agent_id:
                agent_row = await db.execute(text("""
                    SELECT a.active_version_id, v.config_json
                    FROM agents a
                    LEFT JOIN agent_versions v ON v.id = a.active_version_id
                    WHERE a.id = :agent_id AND a.deleted_at IS NULL
                """), {"agent_id": agent_id})
                agent_data = agent_row.fetchone()
                if agent_data:
                    config_json = agent_data[1]
                    if not config_json:
                        fallback_row = await db.execute(text("""
                            SELECT config_json
                            FROM agent_versions
                            WHERE agent_id = :agent_id
                            ORDER BY version DESC
                            LIMIT 1
                        """), {"agent_id": agent_id})
                        fallback = fallback_row.fetchone()
                        if fallback:
                            config_json = fallback[0]
                    if config_json:
                        try:
                            agent_config = json.loads(config_json)
                        except json.JSONDecodeError:
                            agent_config = None

        if runtime.model_manager:
            await runtime.model_manager.ensure_model_loaded(
                ModelConfig(
                    provider=model_provider,
                    model_name=model_name,
                    url=model_url,
                    context_window=context_window,
                    temperature=temperature
                )
            )

        # Support legacy "frontend_id" context key.
        module_id = context.get("module_id") or context.get("frontend_id", "vscode")

        async with active_agents_lock:
            if session_id in active_agents:
                return active_agents[session_id]

            agent = Agent(
                workspace_path=workspace_path,
                module_id=module_id,
                workspace_id=workspace_id,
                session_id=session_id,
                db_session_maker=async_session_maker,
                model_manager=runtime.model_manager,
                embedding_manager=runtime.embedding_manager,
                vector_store=runtime.vector_store,
                agent_config=agent_config
            )
            active_agents[session_id] = agent
            logger.info("agent_created",
                       session_id=session_id,
                       workspace_path=workspace_path,
                       module_id=module_id,
                       rag_enabled=agent.retriever is not None)

        return agent

    async def run_agent_message(user_msg: str, context: dict) -> None:
        assistant_parts = []
        final_message = None
        final_metadata = None
        try:
            await _store_session_message(
                session_id=session_id,
                role="user",
                content=user_msg,
                context=context
            )
            agent = await get_or_create_agent(context)
            if not agent:
                return
            async with processing_lock:
                async for event in agent.process_message(user_msg, context):
                    if event.get("type") == "assistant.message_delta":
                        assistant_parts.append(event.get("delta", ""))
                    elif event.get("type") == "assistant.message_final":
                        final_message = event.get("message")
                        final_metadata = event.get("metadata")
                    await enqueue(event)
        except Exception as exc:
            logger.error("agent_processing_error", error=str(exc), session_id=session_id)
            await send_error("agent_error", f"Agent processing failed: {str(exc)}")
        finally:
            if final_message is None and assistant_parts:
                final_message = "".join(assistant_parts).strip()
            if final_message:
                await _store_session_message(
                    session_id=session_id,
                    role="assistant",
                    content=final_message,
                    metadata=final_metadata
                )

    send_task = asyncio.create_task(send_loop())

    try:
        # Send server hello
        await enqueue({
            "type": "server.hello",
            "protocol_version": settings.PROTOCOL_VERSION,
            "server_info": {
                "version": settings.VERSION,
                "model": {
                    "provider": settings.MODEL_PROVIDER,
                    "model_name": settings.MODEL_NAME,
                    "capabilities": ["chat", "code_completion", "refactor"]
                },
                "capabilities": ["agentic_rag", "ace", "multi_file_edit"]
            }
        })

        # Message loop
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            message_type = message.get("type")
            logger.info("websocket_message_received", session_id=session_id, message_type=message_type, message=message)

            if message_type == "client.hello":
                logger.info("client_hello_received", client_info=message.get("client_info"))
                # Already sent server.hello above

            elif message_type == "client.ping":
                await enqueue({
                    "type": "server.pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            elif message_type == "client.user_message":
                # Handle user message
                user_msg = message.get("message")
                context = message.get("context", {})
                if not isinstance(context, dict):
                    context = {}

                logger.info("user_message_received",
                          message=user_msg,
                          session_id=session_id)

                task = asyncio.create_task(run_agent_message(user_msg, context))
                agent_tasks.add(task)
                task.add_done_callback(agent_tasks.discard)

            elif message_type == "client.cancel":
                logger.info("client_cancelled", session_id=session_id)
                break

            elif message_type == "client.approval_response":
                logger.info("approval_received",
                          request_id=message.get("request_id"),
                          approved=message.get("approved"))
                request_id = message.get("request_id")
                approved = bool(message.get("approved"))
                agent = active_agents.get(session_id)
                if agent and request_id:
                    agent.resolve_approval(request_id, approved)

            else:
                logger.warning("unknown_message_type", type=message_type)

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("websocket_error", error=str(e), session_id=session_id)
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        for task in list(agent_tasks):
            task.cancel()
        await asyncio.gather(*agent_tasks, return_exceptions=True)

        await send_queue.put(None)
        await asyncio.gather(send_task, return_exceptions=True)

        async with active_agents_lock:
            if session_id in active_agents:
                del active_agents[session_id]
                logger.info("agent_cleaned_up", session_id=session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
