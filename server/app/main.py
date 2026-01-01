"""
LoCo Agent Local - Main Server Entry Point
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog
from typing import Optional
import secrets
import json

from app.core.database import init_db, get_db, async_session_maker
from app.core.config import settings
from app.core.qdrant_manager import QdrantManager
from app.api import workspaces, sessions, models as models_api
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

    # TODO: Load embedding model

    logger.info("server_ready")
    yield

    logger.info("server_shutting_down")
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
    # Verify token
    if authorization:
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

                    # Create agent for this session
                    agent = Agent(workspace_path=workspace_path)
                    active_agents[session_id] = agent
                    logger.info("agent_created", session_id=session_id, workspace_path=workspace_path)
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
                # TODO: Handle approval

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
