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
import json

from app.core.database import get_db
from app.core.config import settings
import structlog

logger = structlog.get_logger()

router = APIRouter()


class SessionCreate(BaseModel):
    workspace_id: str
    folder_id: Optional[str] = None
    agent_id: Optional[str] = None
    title: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_url: Optional[str] = None
    context_window: Optional[int] = None
    temperature: Optional[float] = None


class SessionResponse(BaseModel):
    id: str
    workspace_id: str
    folder_id: Optional[str]
    agent_id: Optional[str]
    title: Optional[str]
    model_provider: str
    model_name: str
    model_url: Optional[str]
    context_window: int
    temperature: float
    created_at: str
    status: str


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    folder_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_url: Optional[str] = None
    context_window: Optional[int] = None
    temperature: Optional[float] = None


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
    model_url = session.model_url or settings.MODEL_URL
    context_window = session.context_window or settings.MAX_CONTEXT_TOKENS
    temperature = session.temperature if session.temperature is not None else 0.7

    logger.info("creating_session",
               workspace_id=session.workspace_id,
               model=model_name)

    query = text("""
        INSERT INTO sessions (
            id, workspace_id, folder_id, agent_id, title,
            model_provider, model_name, model_url, context_window, temperature,
            context_strategy, created_at, updated_at, status, current_step,
            total_steps, total_messages
        )
        VALUES (
            :id, :workspace_id, :folder_id, :agent_id, :title,
            :provider, :model, :model_url, :context_window, :temperature,
            :strategy, :created_at, :updated_at, :status, 0, 0, 0
        )
    """)

    now = datetime.now(timezone.utc).isoformat()

    await db.execute(query, {
        "id": session_id,
        "workspace_id": session.workspace_id,
        "folder_id": session.folder_id,
        "agent_id": session.agent_id,
        "title": session.title,
        "provider": model_provider,
        "model": model_name,
        "model_url": model_url,
        "context_window": context_window,
        "temperature": temperature,
        "strategy": "balanced",
        "created_at": now,
        "updated_at": now,
        "status": "active"
    })

    await db.commit()

    return SessionResponse(
        id=session_id,
        workspace_id=session.workspace_id,
        folder_id=session.folder_id,
        agent_id=session.agent_id,
        title=session.title,
        model_provider=model_provider,
        model_name=model_name,
        model_url=model_url,
        context_window=context_window,
        temperature=temperature,
        created_at=now,
        status="active"
    )


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    workspace_id: Optional[str] = None,
    folder_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List sessions, optionally filtered by workspace"""
    if workspace_id or folder_id:
        query = text("""
            SELECT id, workspace_id, folder_id, agent_id, title,
                   model_provider, model_name, model_url,
                   context_window, temperature, created_at, status
            FROM sessions
            WHERE deleted_at IS NULL
              AND (:workspace_id IS NULL OR workspace_id = :workspace_id)
              AND (:folder_id IS NULL OR folder_id = :folder_id)
            ORDER BY updated_at DESC
        """)
        result = await db.execute(query, {"workspace_id": workspace_id, "folder_id": folder_id})
    else:
        query = text("""
            SELECT id, workspace_id, folder_id, agent_id, title,
                   model_provider, model_name, model_url,
                   context_window, temperature, created_at, status
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
            folder_id=row[2],
            agent_id=row[3],
            title=row[4],
            model_provider=row[5],
            model_name=row[6],
            model_url=row[7],
            context_window=row[8],
            temperature=row[9],
            created_at=row[10],
            status=row[11]
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
        SELECT id, workspace_id, folder_id, agent_id, title,
               model_provider, model_name, model_url,
               context_window, temperature, created_at, status
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
        folder_id=row[2],
        agent_id=row[3],
        title=row[4],
        model_provider=row[5],
        model_name=row[6],
        model_url=row[7],
        context_window=row[8],
        temperature=row[9],
        created_at=row[10],
        status=row[11]
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


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    payload: SessionUpdate,
    db: AsyncSession = Depends(get_db)
):
    updates = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.folder_id is not None:
        updates["folder_id"] = payload.folder_id
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.agent_id is not None:
        updates["agent_id"] = payload.agent_id
    if payload.model_provider is not None:
        updates["model_provider"] = payload.model_provider
    if payload.model_name is not None:
        updates["model_name"] = payload.model_name
    if payload.model_url is not None:
        updates["model_url"] = payload.model_url
    if payload.context_window is not None:
        updates["context_window"] = payload.context_window
    if payload.temperature is not None:
        updates["temperature"] = payload.temperature

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join([f"{key} = :{key}" for key in updates.keys()])
        updates["session_id"] = session_id
        result = await db.execute(text(f"""
            UPDATE sessions
            SET {set_clause}
            WHERE id = :session_id AND deleted_at IS NULL
        """), updates)
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")

    return await get_session(session_id, db)


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str
    metadata: Optional[dict] = None


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a session"""
    query = text("""
        SELECT role, content, created_at, metadata_json
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
            created_at=row[2],
            metadata=json.loads(row[3]) if row[3] else None
        )
        for row in rows
    ]
