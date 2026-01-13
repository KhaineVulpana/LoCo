"""
Session API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
import structlog

logger = structlog.get_logger()

router = APIRouter()


class SessionCreate(BaseModel):
    workspace_id: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    context_window: Optional[int] = None


class SessionResponse(BaseModel):
    id: str
    workspace_id: str
    title: Optional[str]
    model_provider: str
    model_name: str
    context_window: int
    created_at: str
    status: str


@router.post("", response_model=SessionResponse)
async def create_session(
    session: SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session"""
    session_id = str(uuid.uuid4())

    # Use defaults from config if not provided
    model_provider = session.model_provider or settings.MODEL_PROVIDER
    model_name = session.model_name or settings.MODEL_NAME
    context_window = session.context_window or settings.MAX_CONTEXT_TOKENS

    logger.info("creating_session",
               workspace_id=session.workspace_id,
               model=model_name)

    query = text("""
        INSERT INTO sessions (
            id, workspace_id, model_provider, model_name, context_window,
            context_strategy, created_at, updated_at, status, current_step,
            total_steps, total_messages
        )
        VALUES (
            :id, :workspace_id, :provider, :model, :context_window,
            :strategy, :created_at, :updated_at, :status, 0, 0, 0
        )
    """)

    now = datetime.now(timezone.utc).isoformat()

    await db.execute(query, {
        "id": session_id,
        "workspace_id": session.workspace_id,
        "provider": model_provider,
        "model": model_name,
        "context_window": context_window,
        "strategy": "balanced",
        "created_at": now,
        "updated_at": now,
        "status": "active"
    })

    await db.commit()

    return SessionResponse(
        id=session_id,
        workspace_id=session.workspace_id,
        title=None,
        model_provider=model_provider,
        model_name=model_name,
        context_window=context_window,
        created_at=now,
        status="active"
    )


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    workspace_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List sessions, optionally filtered by workspace"""
    if workspace_id:
        query = text("""
            SELECT id, workspace_id, title, model_provider, model_name,
                   context_window, created_at, status
            FROM sessions
            WHERE workspace_id = :workspace_id AND deleted_at IS NULL
            ORDER BY updated_at DESC
        """)
        result = await db.execute(query, {"workspace_id": workspace_id})
    else:
        query = text("""
            SELECT id, workspace_id, title, model_provider, model_name,
                   context_window, created_at, status
            FROM sessions
            WHERE deleted_at IS NULL
            ORDER BY updated_at DESC
        """)
        result = await db.execute(query)

    rows = result.fetchall()

    return [
        SessionResponse(
            id=row[0],
            workspace_id=row[1],
            title=row[2],
            model_provider=row[3],
            model_name=row[4],
            context_window=row[5],
            created_at=row[6],
            status=row[7]
        )
        for row in rows
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get session by ID"""
    query = text("""
        SELECT id, workspace_id, title, model_provider, model_name,
               context_window, created_at, status
        FROM sessions
        WHERE id = :session_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"session_id": session_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=row[0],
        workspace_id=row[1],
        title=row[2],
        model_provider=row[3],
        model_name=row[4],
        context_window=row[5],
        created_at=row[6],
        status=row[7]
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a session"""
    query = text("""
        UPDATE sessions
        SET deleted_at = :deleted_at
        WHERE id = :session_id
    """)

    await db.execute(query, {
        "session_id": session_id,
        "deleted_at": datetime.now(timezone.utc).isoformat()
    })

    await db.commit()

    return {"success": True}


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a session"""
    query = text("""
        SELECT role, content, created_at
        FROM session_messages
        WHERE session_id = :session_id
        ORDER BY created_at ASC
    """)

    result = await db.execute(query, {"session_id": session_id})
    rows = result.fetchall()

    return [
        MessageResponse(
            role=row[0],
            content=row[1],
            created_at=row[2]
        )
        for row in rows
    ]
