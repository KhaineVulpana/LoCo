"""
LoCo Agent Local - Main Server Entry Point
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog
from typing import Optional
import secrets
import json

from app.core.database import init_db, async_session_maker
from app.core.config import settings
from app.core import runtime
from app.core.qdrant_manager import QdrantManager
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.auto_knowledge_loader import ensure_shared_knowledge
from app.indexing.remote_docs_loader import ensure_remote_docs
from app.indexing.training_data_loader import ensure_3d_gen_training_data
from app.indexing.vscode_docs_loader import ensure_vscode_docs
from app.core.model_manager import ModelManager
from app.api import workspaces, sessions, models as models_api, knowledge, ace
from app.core.auth import verify_token
from app.agent import Agent
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Store active agents per session
active_agents = {}


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

            ace_frontends = ["vscode", "android", "3d-gen"]
            logger.info("initializing_ace_collections", frontends=ace_frontends)
            for frontend_id in ace_frontends:
                collection_name = f"loco_ace_{frontend_id}"
                try:
                    runtime.vector_store.create_collection(
                        collection_name=collection_name,
                        vector_size=runtime.embedding_manager.get_dimensions()
                    )
                except Exception as e:
                    logger.error("ace_collection_init_failed",
                                frontend_id=frontend_id,
                                error=str(e))

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

    logger.info("server_ready",
               embedding_model=runtime.embedding_manager.get_model_name() if runtime.embedding_manager else None,
               model_manager="initialized")
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
        if not authorization:
            await websocket.close(code=1008, reason="Unauthorized")
            return

        token = authorization.replace("Bearer ", "")
        if not verify_token(token):
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()

    logger.info("websocket_connected", session_id=session_id)

    try:
        # Send server hello
        await websocket.send_json({
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

            if message_type == "client.hello":
                logger.info("client_hello_received", client_info=message.get("client_info"))
                # Already sent server.hello above

            elif message_type == "client.user_message":
                # Handle user message
                user_msg = message.get("message")
                context = message.get("context", {})

                logger.info("user_message_received",
                          message=user_msg,
                          session_id=session_id)

                # Get or create agent for this session
                if session_id not in active_agents:
                    # Fetch session and workspace info from database
                    async with async_session_maker() as db:
                        # Get session's workspace_id
                        session_query = text("""
                            SELECT workspace_id FROM sessions WHERE id = :session_id
                        """)
                        session_result = await db.execute(session_query, {"session_id": session_id})
                        session_row = session_result.fetchone()

                        if not session_row:
                            await websocket.send_json({
                                "type": "server.error",
                                "error": {
                                    "code": "session_not_found",
                                    "message": "Session not found"
                                }
                            })
                            continue

                        workspace_id = session_row[0]

                        # Get workspace path
                        workspace_query = text("""
                            SELECT path FROM workspaces WHERE id = :workspace_id
                        """)
                        workspace_result = await db.execute(workspace_query, {"workspace_id": workspace_id})
                        workspace_row = workspace_result.fetchone()

                        if not workspace_row:
                            await websocket.send_json({
                                "type": "server.error",
                                "error": {
                                    "code": "workspace_not_found",
                                    "message": "Workspace not found"
                                }
                            })
                            continue

                        workspace_path = workspace_row[0]

                    # Determine frontend_id from context (default to vscode for now)
                    # TODO: Get frontend_id from client_info in handshake
                    frontend_id = context.get("frontend_id", "vscode")

                    # Create agent for this session with RAG components and model manager
                    agent = Agent(
                        workspace_path=workspace_path,
                        frontend_id=frontend_id,
                        workspace_id=workspace_id,
                        db_session_maker=async_session_maker,
                        model_manager=runtime.model_manager,
                        embedding_manager=runtime.embedding_manager,
                        vector_store=runtime.vector_store
                    )
                    active_agents[session_id] = agent
                    logger.info("agent_created",
                               session_id=session_id,
                               workspace_path=workspace_path,
                               frontend_id=frontend_id,
                               rag_enabled=agent.retriever is not None)
                else:
                    agent = active_agents[session_id]

                # Process message through agent
                try:
                    async for event in agent.process_message(user_msg, context):
                        await websocket.send_json(event)
                except Exception as e:
                    logger.error("agent_processing_error", error=str(e), session_id=session_id)
                    await websocket.send_json({
                        "type": "server.error",
                        "error": {
                            "code": "agent_error",
                            "message": f"Agent processing failed: {str(e)}"
                        }
                    })

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
        # Clean up agent
        if session_id in active_agents:
            del active_agents[session_id]
            logger.info("agent_cleaned_up", session_id=session_id)
    except Exception as e:
        logger.error("websocket_error", error=str(e), session_id=session_id)
        # Clean up agent
        if session_id in active_agents:
            del active_agents[session_id]
        await websocket.close(code=1011, reason="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
