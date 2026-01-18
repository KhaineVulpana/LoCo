"""
Upload API endpoints
"""

from typing import Any, Dict, Optional
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import settings
from app.indexing.domain_indexer import KnowledgeIndexer
from app.core import runtime

logger = structlog.get_logger()

router = APIRouter()


def _sanitize_filename(name: str) -> str:
    safe = []
    for ch in name:
        if ch.isalnum() or ch in (".", "_", "-"):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe) or "upload"


def _get_upload_dir() -> Path:
    base = Path(settings.UPLOADS_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _max_upload_bytes() -> int:
    return max(settings.MAX_UPLOAD_MB, 1) * 1024 * 1024


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    workspace_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    agent_id: Optional[str] = Form(None),
    purpose: str = Form("attachment"),
    module_id: Optional[str] = Form(None),
    index: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    upload_dir = _get_upload_dir()
    attachment_id = str(uuid.uuid4())
    safe_name = _sanitize_filename(file.filename)
    storage_path = upload_dir / f"{attachment_id}_{safe_name}"

    hasher = hashlib.sha256()
    size_bytes = 0
    max_bytes = _max_upload_bytes()

    try:
        async with aiofiles.open(storage_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(status_code=413, detail="Upload exceeds size limit")
                hasher.update(chunk)
                await out.write(chunk)
    except Exception:
        if storage_path.exists():
            storage_path.unlink()
        raise
    finally:
        await file.close()

    content_hash = hasher.hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(text("""
        INSERT INTO attachments (
            id, workspace_id, session_id, agent_id, file_name, mime_type,
            size_bytes, storage_path, content_hash, purpose, created_at
        )
        VALUES (
            :id, :workspace_id, :session_id, :agent_id, :file_name, :mime_type,
            :size_bytes, :storage_path, :content_hash, :purpose, :created_at
        )
    """), {
        "id": attachment_id,
        "workspace_id": workspace_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "file_name": file.filename,
        "mime_type": file.content_type,
        "size_bytes": size_bytes,
        "storage_path": str(storage_path),
        "content_hash": content_hash,
        "purpose": purpose,
        "created_at": now
    })

    await db.commit()

    index_stats: Optional[Dict[str, Any]] = None
    if index:
        if not module_id:
            raise HTTPException(status_code=400, detail="module_id is required for indexing")
        embedding_manager = runtime.get_embedding_manager()
        vector_store = runtime.get_vector_store()
        indexer = KnowledgeIndexer(
            module_id=module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )
        suffix = storage_path.suffix.lower()
        if suffix == ".jsonl":
            index_stats = await indexer.index_training_data(str(storage_path))
        else:
            index_stats = await indexer.index_files([str(storage_path)])

    return {
        "success": True,
        "attachment": {
            "id": attachment_id,
            "workspace_id": workspace_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "file_name": file.filename,
            "mime_type": file.content_type,
            "size_bytes": size_bytes,
            "storage_path": str(storage_path),
            "content_hash": content_hash,
            "purpose": purpose,
            "created_at": now
        },
        "indexed": bool(index_stats),
        "index_stats": index_stats
    }


@router.get("")
async def list_uploads(
    workspace_id: str,
    session_id: Optional[str] = None,
    purpose: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    filters = ["workspace_id = :workspace_id"]
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if session_id:
        filters.append("session_id = :session_id")
        params["session_id"] = session_id
    if purpose:
        filters.append("purpose = :purpose")
        params["purpose"] = purpose

    where_clause = " AND ".join(filters)
    result = await db.execute(text(f"""
        SELECT id, workspace_id, session_id, agent_id, file_name, mime_type,
               size_bytes, storage_path, content_hash, purpose, created_at
        FROM attachments
        WHERE {where_clause}
        ORDER BY created_at DESC
    """), params)

    rows = result.fetchall()
    return {
        "success": True,
        "attachments": [
            {
                "id": row[0],
                "workspace_id": row[1],
                "session_id": row[2],
                "agent_id": row[3],
                "file_name": row[4],
                "mime_type": row[5],
                "size_bytes": row[6],
                "storage_path": row[7],
                "content_hash": row[8],
                "purpose": row[9],
                "created_at": row[10]
            }
            for row in rows
        ]
    }


@router.get("/{attachment_id}")
async def download_upload(
    attachment_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(text("""
        SELECT file_name, storage_path, mime_type
        FROM attachments
        WHERE id = :attachment_id
    """), {"attachment_id": attachment_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_name, storage_path, mime_type = row
    path = Path(storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path, media_type=mime_type or "application/octet-stream", filename=file_name)
