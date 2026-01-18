"""
Search API endpoints for sessions and messages
"""

from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db

logger = structlog.get_logger()

router = APIRouter()


class MessageSearchResult(BaseModel):
    session_id: str
    session_title: Optional[str]
    role: str
    content: str
    created_at: str


class SessionSearchResult(BaseModel):
    session_id: str
    title: Optional[str]
    last_message_at: Optional[str]
    snippet: Optional[str]


def _fallback_like_query(query: str) -> str:
    return f"%{query}%"


@router.get("/messages", response_model=List[MessageSearchResult])
async def search_messages(
    workspace_id: str,
    query: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query required")

    params: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "query": query,
        "limit": limit
    }

    try:
        result = await db.execute(text("""
            SELECT f.session_id, s.title, f.role, f.content, f.created_at
            FROM session_messages_fts f
            JOIN sessions s ON s.id = f.session_id
            WHERE session_messages_fts MATCH :query
              AND s.workspace_id = :workspace_id
              AND s.deleted_at IS NULL
            ORDER BY f.created_at DESC
            LIMIT :limit
        """), params)
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("fts_search_failed", error=str(exc))
        like_query = _fallback_like_query(query)
        result = await db.execute(text("""
            SELECT m.session_id, s.title, m.role, m.content, m.created_at
            FROM session_messages m
            JOIN sessions s ON s.id = m.session_id
            WHERE s.workspace_id = :workspace_id
              AND s.deleted_at IS NULL
              AND m.content LIKE :like_query
            ORDER BY m.created_at DESC
            LIMIT :limit
        """), {
            "workspace_id": workspace_id,
            "like_query": like_query,
            "limit": limit
        })
        rows = result.fetchall()

    return [
        MessageSearchResult(
            session_id=row[0],
            session_title=row[1],
            role=row[2],
            content=row[3],
            created_at=row[4]
        )
        for row in rows
    ]


@router.get("/sessions", response_model=List[SessionSearchResult])
async def search_sessions(
    workspace_id: str,
    query: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query required")

    params: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "query": query,
        "limit": limit
    }

    try:
        result = await db.execute(text("""
            SELECT f.session_id,
                   s.title,
                   MAX(f.created_at) AS last_message_at,
                   substr(f.content, 1, 200) AS snippet
            FROM session_messages_fts f
            JOIN sessions s ON s.id = f.session_id
            WHERE session_messages_fts MATCH :query
              AND s.workspace_id = :workspace_id
              AND s.deleted_at IS NULL
            GROUP BY f.session_id, s.title
            ORDER BY last_message_at DESC
            LIMIT :limit
        """), params)
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("fts_search_failed", error=str(exc))
        like_query = _fallback_like_query(query)
        result = await db.execute(text("""
            SELECT m.session_id,
                   s.title,
                   MAX(m.created_at) AS last_message_at,
                   substr(MAX(m.content), 1, 200) AS snippet
            FROM session_messages m
            JOIN sessions s ON s.id = m.session_id
            WHERE s.workspace_id = :workspace_id
              AND s.deleted_at IS NULL
              AND (m.content LIKE :like_query OR s.title LIKE :like_query)
            GROUP BY m.session_id, s.title
            ORDER BY last_message_at DESC
            LIMIT :limit
        """), {
            "workspace_id": workspace_id,
            "like_query": like_query,
            "limit": limit
        })
        rows = result.fetchall()

    return [
        SessionSearchResult(
            session_id=row[0],
            title=row[1],
            last_message_at=row[2],
            snippet=row[3]
        )
        for row in rows
    ]
