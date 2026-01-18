"""
Folder API endpoints for organizing sessions
"""

from typing import List, Optional
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db

logger = structlog.get_logger()

router = APIRouter()


class FolderCreate(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class FolderResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str


@router.post("", response_model=FolderResponse)
async def create_folder(
    payload: FolderCreate,
    db: AsyncSession = Depends(get_db)
):
    folder_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(text("""
        INSERT INTO folders (
            id, workspace_id, name, description, created_at, updated_at
        )
        VALUES (
            :id, :workspace_id, :name, :description, :created_at, :updated_at
        )
    """), {
        "id": folder_id,
        "workspace_id": payload.workspace_id,
        "name": payload.name,
        "description": payload.description,
        "created_at": now,
        "updated_at": now
    })

    await db.commit()

    logger.info("folder_created", folder_id=folder_id, workspace_id=payload.workspace_id)

    return FolderResponse(
        id=folder_id,
        workspace_id=payload.workspace_id,
        name=payload.name,
        description=payload.description,
        created_at=now,
        updated_at=now
    )


@router.get("", response_model=List[FolderResponse])
async def list_folders(
    workspace_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    filters = ["deleted_at IS NULL"]
    params = {}
    if workspace_id:
        filters.append("workspace_id = :workspace_id")
        params["workspace_id"] = workspace_id
    where_clause = " AND ".join(filters)

    result = await db.execute(text(f"""
        SELECT id, workspace_id, name, description, created_at, updated_at
        FROM folders
        WHERE {where_clause}
        ORDER BY updated_at DESC
    """), params)

    rows = result.fetchall()
    return [
        FolderResponse(
            id=row[0],
            workspace_id=row[1],
            name=row[2],
            description=row[3],
            created_at=row[4],
            updated_at=row[5]
        )
        for row in rows
    ]


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    payload: FolderUpdate,
    db: AsyncSession = Depends(get_db)
):
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join([f"{key} = :{key}" for key in updates.keys()])
        updates["folder_id"] = folder_id
        result = await db.execute(text(f"""
            UPDATE folders
            SET {set_clause}
            WHERE id = :folder_id AND deleted_at IS NULL
        """), updates)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Folder not found")

    result = await db.execute(text("""
        SELECT id, workspace_id, name, description, created_at, updated_at
        FROM folders
        WHERE id = :folder_id AND deleted_at IS NULL
    """), {"folder_id": folder_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Folder not found")

    return FolderResponse(
        id=row[0],
        workspace_id=row[1],
        name=row[2],
        description=row[3],
        created_at=row[4],
        updated_at=row[5]
    )


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc).isoformat()
    result = await db.execute(text("""
        UPDATE folders
        SET deleted_at = :deleted_at,
            updated_at = :updated_at
        WHERE id = :folder_id AND deleted_at IS NULL
    """), {"folder_id": folder_id, "deleted_at": now, "updated_at": now})

    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Folder not found")

    return {"success": True}
