"""
Workspace API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid
from datetime import datetime
from pathlib import Path

from app.core.database import get_db
import structlog

logger = structlog.get_logger()

router = APIRouter()


class WorkspaceCreate(BaseModel):
    path: str
    name: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    path: str
    name: str
    created_at: str
    index_status: str
    total_files: int
    indexed_files: int


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
        SELECT id, path, name, created_at, index_status, total_files, indexed_files
        FROM workspaces
        WHERE path = :path AND deleted_at IS NULL
    """)

    result = await db.execute(check_query, {"path": workspace.path})
    existing = result.fetchone()

    if existing:
        logger.info("workspace_already_exists", path=workspace.path, id=existing[0])
        return WorkspaceResponse(
            id=existing[0],
            path=existing[1],
            name=existing[2],
            created_at=existing[3],
            index_status=existing[4],
            total_files=existing[5] or 0,
            indexed_files=existing[6] or 0
        )

    # Insert new workspace
    workspace_id = str(uuid.uuid4())
    insert_query = text("""
        INSERT INTO workspaces (id, path, name, created_at, updated_at, index_status, total_files, indexed_files)
        VALUES (:id, :path, :name, :created_at, :updated_at, :status, 0, 0)
    """)

    now = datetime.utcnow().isoformat()

    await db.execute(insert_query, {
        "id": workspace_id,
        "path": workspace.path,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "status": "pending"
    })

    await db.commit()

    return WorkspaceResponse(
        id=workspace_id,
        path=workspace.path,
        name=name,
        created_at=now,
        index_status="pending",
        total_files=0,
        indexed_files=0
    )


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    """List all registered workspaces"""
    query = text("""
        SELECT id, path, name, created_at, index_status, total_files, indexed_files
        FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
    """)

    result = await db.execute(query)
    rows = result.fetchall()

    return [
        WorkspaceResponse(
            id=row[0],
            path=row[1],
            name=row[2],
            created_at=row[3],
            index_status=row[4],
            total_files=row[5] or 0,
            indexed_files=row[6] or 0
        )
        for row in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get workspace by ID"""
    query = text("""
        SELECT id, path, name, created_at, index_status, total_files, indexed_files
        FROM workspaces
        WHERE id = :workspace_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"workspace_id": workspace_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return WorkspaceResponse(
        id=row[0],
        path=row[1],
        name=row[2],
        created_at=row[3],
        index_status=row[4],
        total_files=row[5] or 0,
        indexed_files=row[6] or 0
    )
