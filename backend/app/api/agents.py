"""
Agent profile API endpoints
"""

from typing import Any, Dict, List, Optional
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.runtime import get_model_manager

logger = structlog.get_logger()

router = APIRouter()


class AgentCreate(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    version_title: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active_version_id: Optional[str] = None
    is_archived: Optional[bool] = None


class AgentVersionCreate(BaseModel):
    title: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    activate: bool = True


class AgentVersionResponse(BaseModel):
    id: str
    version: int
    title: Optional[str]
    config: Dict[str, Any]
    created_at: str


class AgentResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    active_version_id: Optional[str]
    active_version: Optional[AgentVersionResponse]
    is_archived: bool
    created_at: str
    updated_at: str


class AgentBuildRequest(BaseModel):
    description: str
    base_config: Dict[str, Any] = Field(default_factory=dict)


class AgentBuildResponse(BaseModel):
    config: Dict[str, Any]
    raw: Optional[str] = None


def _parse_config(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _dump_config(config: Dict[str, Any]) -> str:
    return json.dumps(config, ensure_ascii=True)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start:end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None

    return None


@router.post("", response_model=AgentResponse)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db)
):
    agent_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    config_json = _dump_config(payload.config)

    await db.execute(text("""
        INSERT INTO agents (
            id, workspace_id, name, description, active_version_id,
            is_archived, created_at, updated_at
        )
        VALUES (
            :id, :workspace_id, :name, :description, :active_version_id,
            0, :created_at, :updated_at
        )
    """), {
        "id": agent_id,
        "workspace_id": payload.workspace_id,
        "name": payload.name,
        "description": payload.description,
        "active_version_id": version_id,
        "created_at": now,
        "updated_at": now
    })

    await db.execute(text("""
        INSERT INTO agent_versions (
            id, agent_id, version, title, config_json, created_at
        )
        VALUES (
            :id, :agent_id, :version, :title, :config_json, :created_at
        )
    """), {
        "id": version_id,
        "agent_id": agent_id,
        "version": 1,
        "title": payload.version_title,
        "config_json": config_json,
        "created_at": now
    })

    await db.commit()

    logger.info("agent_created", agent_id=agent_id, workspace_id=payload.workspace_id)

    active_version = AgentVersionResponse(
        id=version_id,
        version=1,
        title=payload.version_title,
        config=payload.config,
        created_at=now
    )

    return AgentResponse(
        id=agent_id,
        workspace_id=payload.workspace_id,
        name=payload.name,
        description=payload.description,
        active_version_id=version_id,
        active_version=active_version,
        is_archived=False,
        created_at=now,
        updated_at=now
    )


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    workspace_id: Optional[str] = None,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db)
):
    filters = ["a.deleted_at IS NULL"]
    params: Dict[str, Any] = {}
    if workspace_id:
        filters.append("a.workspace_id = :workspace_id")
        params["workspace_id"] = workspace_id
    if not include_archived:
        filters.append("a.is_archived = 0")

    where_clause = " AND ".join(filters)

    result = await db.execute(text(f"""
        SELECT a.id, a.workspace_id, a.name, a.description,
               a.active_version_id, a.is_archived, a.created_at, a.updated_at,
               v.id, v.version, v.title, v.config_json, v.created_at
        FROM agents a
        LEFT JOIN agent_versions v ON v.id = a.active_version_id
        WHERE {where_clause}
        ORDER BY a.updated_at DESC
    """), params)

    rows = result.fetchall()
    responses: List[AgentResponse] = []
    for row in rows:
        version = None
        if row[8]:
            version = AgentVersionResponse(
                id=row[8],
                version=row[9],
                title=row[10],
                config=_parse_config(row[11]),
                created_at=row[12]
            )

        responses.append(AgentResponse(
            id=row[0],
            workspace_id=row[1],
            name=row[2],
            description=row[3],
            active_version_id=row[4],
            active_version=version,
            is_archived=bool(row[5]),
            created_at=row[6],
            updated_at=row[7]
        ))

    return responses


@router.post("/build", response_model=AgentBuildResponse)
async def build_agent_config(
    payload: AgentBuildRequest,
    model_manager = Depends(get_model_manager)
):
    client = model_manager.get_current_model()
    if not client:
        raise HTTPException(status_code=503, detail="No model loaded")

    base_config_json = _dump_config(payload.base_config) if payload.base_config else "{}"
    system_prompt = (
        "You are an agent configuration builder. "
        "Return a JSON object only. "
        "Schema:\\n"
        "{\\n"
        "  \"system_prompt\": \"string\",\\n"
        "  \"tools\": {\"allowlist\": [\"tool_name\"], \"blocklist\": [], \"auto_approve_tools\": []},\\n"
        "  \"rag\": {\"enabled\": true, \"limit\": 5, \"score_threshold\": 0.6},\\n"
        "  \"ace\": {\"enabled\": true, \"limit\": 5, \"score_threshold\": 0.5},\\n"
        "  \"model\": {\"provider\": \"ollama\", \"model_name\": \"\", \"url\": \"\", \"context_window\": 8192, \"temperature\": 0.7}\\n"
        "}\\n"
        "If a field is unknown, keep defaults.\\n"
        f"Base config (merge onto this): {base_config_json}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": payload.description}
    ]

    content = ""
    async for chunk in client.generate_stream(messages, response_format="json"):
        if chunk.get("type") == "content":
            content += chunk.get("content", "")

    config = _extract_json(content)
    if config is None:
        raise HTTPException(status_code=500, detail="Failed to parse agent config")

    return AgentBuildResponse(config=config, raw=content.strip() or None)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(text("""
        SELECT a.id, a.workspace_id, a.name, a.description,
               a.active_version_id, a.is_archived, a.created_at, a.updated_at,
               v.id, v.version, v.title, v.config_json, v.created_at
        FROM agents a
        LEFT JOIN agent_versions v ON v.id = a.active_version_id
        WHERE a.id = :agent_id AND a.deleted_at IS NULL
    """), {"agent_id": agent_id})

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    version = None
    if row[8]:
        version = AgentVersionResponse(
            id=row[8],
            version=row[9],
            title=row[10],
            config=_parse_config(row[11]),
            created_at=row[12]
        )

    return AgentResponse(
        id=row[0],
        workspace_id=row[1],
        name=row[2],
        description=row[3],
        active_version_id=row[4],
        active_version=version,
        is_archived=bool(row[5]),
        created_at=row[6],
        updated_at=row[7]
    )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(text("""
        SELECT active_version_id, workspace_id
        FROM agents
        WHERE id = :agent_id AND deleted_at IS NULL
    """), {"agent_id": agent_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.active_version_id:
        version_check = await db.execute(text("""
            SELECT 1 FROM agent_versions
            WHERE id = :version_id AND agent_id = :agent_id
        """), {"version_id": payload.active_version_id, "agent_id": agent_id})
        if not version_check.fetchone():
            raise HTTPException(status_code=400, detail="Version does not belong to agent")

    updates: Dict[str, Any] = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.active_version_id is not None:
        updates["active_version_id"] = payload.active_version_id
    if payload.is_archived is not None:
        updates["is_archived"] = 1 if payload.is_archived else 0

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join([f"{key} = :{key}" for key in updates.keys()])
        updates["agent_id"] = agent_id
        await db.execute(text(f"""
            UPDATE agents
            SET {set_clause}
            WHERE id = :agent_id
        """), updates)
        await db.commit()

    return await get_agent(agent_id, db)


@router.post("/{agent_id}/versions", response_model=AgentVersionResponse)
async def create_agent_version(
    agent_id: str,
    payload: AgentVersionCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(text("""
        SELECT 1 FROM agents WHERE id = :agent_id AND deleted_at IS NULL
    """), {"agent_id": agent_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Agent not found")

    version_row = await db.execute(text("""
        SELECT COALESCE(MAX(version), 0) + 1 FROM agent_versions
        WHERE agent_id = :agent_id
    """), {"agent_id": agent_id})
    next_version = version_row.scalar_one()

    version_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    config_json = _dump_config(payload.config)

    await db.execute(text("""
        INSERT INTO agent_versions (
            id, agent_id, version, title, config_json, created_at
        )
        VALUES (
            :id, :agent_id, :version, :title, :config_json, :created_at
        )
    """), {
        "id": version_id,
        "agent_id": agent_id,
        "version": next_version,
        "title": payload.title,
        "config_json": config_json,
        "created_at": now
    })

    if payload.activate:
        await db.execute(text("""
            UPDATE agents
            SET active_version_id = :version_id,
                updated_at = :updated_at
            WHERE id = :agent_id
        """), {
            "version_id": version_id,
            "updated_at": now,
            "agent_id": agent_id
        })

    await db.commit()

    return AgentVersionResponse(
        id=version_id,
        version=next_version,
        title=payload.title,
        config=payload.config,
        created_at=now
    )


@router.get("/{agent_id}/versions", response_model=List[AgentVersionResponse])
async def list_agent_versions(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(text("""
        SELECT id, version, title, config_json, created_at
        FROM agent_versions
        WHERE agent_id = :agent_id
        ORDER BY version DESC
    """), {"agent_id": agent_id})

    rows = result.fetchall()
    return [
        AgentVersionResponse(
            id=row[0],
            version=row[1],
            title=row[2],
            config=_parse_config(row[3]),
            created_at=row[4]
        )
        for row in rows
    ]


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc).isoformat()
    result = await db.execute(text("""
        UPDATE agents
        SET deleted_at = :deleted_at,
            updated_at = :updated_at
        WHERE id = :agent_id AND deleted_at IS NULL
    """), {"agent_id": agent_id, "deleted_at": now, "updated_at": now})

    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"success": True}
