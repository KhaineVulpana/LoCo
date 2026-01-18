"""
Export API endpoints
"""

from typing import Any, Dict, List
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter()


def _parse_json(value: str) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _format_markdown(session: Dict[str, Any], messages: List[Dict[str, Any]]) -> str:
    title = session.get("title") or "Chat Session"
    lines = [f"# {title}", "", f"Session ID: {session['id']}", ""]
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"## {role.capitalize()}")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def _format_trace_markdown(trace: Dict[str, Any]) -> str:
    session = trace.get("session") or {}
    title = session.get("title") or "Chat Session"
    prompt = trace.get("prompt") or {}
    assistant = trace.get("assistant") or {}
    tool_events = trace.get("tool_events") or []

    lines = [f"# Trace: {title}", "", f"Session ID: {session.get('id', '')}", ""]

    if prompt:
        lines.append("## Latest Prompt")
        lines.append("")
        lines.append(prompt.get("content", ""))
        lines.append("")
        lines.append(f"_Sent: {prompt.get('created_at', '')}_")
        lines.append("")

    if tool_events:
        lines.append("## Tool Actions")
        lines.append("")
        for event in tool_events:
            lines.append(f"### {event.get('tool_name', 'tool')} ({event.get('status', 'unknown')})")
            lines.append("")
            args_json = event.get("args") or {}
            lines.append("Args:")
            lines.append("```json")
            lines.append(json.dumps(args_json, indent=2, ensure_ascii=True))
            lines.append("```")
            result = event.get("result")
            error = event.get("error")
            if result is not None:
                lines.append("Result:")
                lines.append("```json")
                lines.append(json.dumps(result, indent=2, ensure_ascii=True))
                lines.append("```")
            if error is not None:
                lines.append("Error:")
                lines.append("```json")
                lines.append(json.dumps(error, indent=2, ensure_ascii=True))
                lines.append("```")
            if event.get("duration_ms") is not None:
                lines.append(f"_Duration: {event.get('duration_ms')} ms_")
            lines.append("")
    else:
        lines.append("## Tool Actions")
        lines.append("")
        lines.append("_No tool actions recorded for the latest prompt._")
        lines.append("")

    if assistant:
        lines.append("## Assistant Response")
        lines.append("")
        lines.append(assistant.get("content", ""))
        lines.append("")
        lines.append(f"_Received: {assistant.get('created_at', '')}_")
        lines.append("")

    return "\n".join(lines)


@router.get("/sessions/{session_id}")
async def export_session(
    session_id: str,
    format: str = "json",
    db: AsyncSession = Depends(get_db)
):
    session_result = await db.execute(text("""
        SELECT id, workspace_id, title, model_provider, model_name, model_url,
               context_window, temperature, created_at, updated_at
        FROM sessions
        WHERE id = :session_id AND deleted_at IS NULL
    """), {"session_id": session_id})
    session_row = session_result.fetchone()

    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found")

    messages_result = await db.execute(text("""
        SELECT role, content, created_at, metadata_json
        FROM session_messages
        WHERE session_id = :session_id
        ORDER BY created_at ASC
    """), {"session_id": session_id})

    messages = [
        {
            "role": row[0],
            "content": row[1],
            "created_at": row[2],
            "metadata": json.loads(row[3]) if row[3] else None
        }
        for row in messages_result.fetchall()
    ]

    session = {
        "id": session_row[0],
        "workspace_id": session_row[1],
        "title": session_row[2],
        "model_provider": session_row[3],
        "model_name": session_row[4],
        "model_url": session_row[5],
        "context_window": session_row[6],
        "temperature": session_row[7],
        "created_at": session_row[8],
        "updated_at": session_row[9]
    }

    if format == "md":
        markdown = _format_markdown(session, messages)
        return PlainTextResponse(markdown, media_type="text/markdown")

    if format != "json":
        raise HTTPException(status_code=400, detail="Invalid format")

    return JSONResponse({
        "session": session,
        "messages": messages
    })


@router.get("/sessions/{session_id}/trace")
async def export_session_trace(
    session_id: str,
    format: str = "json",
    db: AsyncSession = Depends(get_db)
):
    session_result = await db.execute(text("""
        SELECT id, workspace_id, title, model_provider, model_name, model_url,
               context_window, temperature, created_at, updated_at
        FROM sessions
        WHERE id = :session_id AND deleted_at IS NULL
    """), {"session_id": session_id})
    session_row = session_result.fetchone()

    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found")

    session = {
        "id": session_row[0],
        "workspace_id": session_row[1],
        "title": session_row[2],
        "model_provider": session_row[3],
        "model_name": session_row[4],
        "model_url": session_row[5],
        "context_window": session_row[6],
        "temperature": session_row[7],
        "created_at": session_row[8],
        "updated_at": session_row[9]
    }

    prompt_row = None
    prompt_result = await db.execute(text("""
        SELECT role, content, created_at, metadata_json
        FROM session_messages
        WHERE session_id = :session_id AND role = 'user'
        ORDER BY created_at DESC
        LIMIT 1
    """), {"session_id": session_id})
    prompt_row = prompt_result.fetchone()

    prompt = None
    since = None
    if prompt_row:
        since = prompt_row[2]
        prompt = {
            "role": prompt_row[0],
            "content": prompt_row[1],
            "created_at": prompt_row[2],
            "metadata": _parse_json(prompt_row[3])
        }

    assistant = None
    if since:
        assistant_result = await db.execute(text("""
            SELECT role, content, created_at, metadata_json
            FROM session_messages
            WHERE session_id = :session_id
              AND role = 'assistant'
              AND created_at >= :since
            ORDER BY created_at ASC
            LIMIT 1
        """), {"session_id": session_id, "since": since})
        assistant_row = assistant_result.fetchone()
        if assistant_row:
            assistant = {
                "role": assistant_row[0],
                "content": assistant_row[1],
                "created_at": assistant_row[2],
                "metadata": _parse_json(assistant_row[3])
            }

    tool_events: List[Dict[str, Any]] = []
    if since:
        tool_result = await db.execute(text("""
            SELECT tool_name, args_json, result_json, error_json, status,
                   duration_ms, requires_approval, approval_status, created_at
            FROM tool_events
            WHERE session_id = :session_id
              AND created_at >= :since
            ORDER BY created_at ASC
        """), {"session_id": session_id, "since": since})
        for row in tool_result.fetchall():
            tool_events.append({
                "tool_name": row[0],
                "args": _parse_json(row[1]),
                "result": _parse_json(row[2]),
                "error": _parse_json(row[3]),
                "status": row[4],
                "duration_ms": row[5],
                "requires_approval": bool(row[6]),
                "approval_status": row[7],
                "created_at": row[8]
            })

    trace = {
        "session": session,
        "prompt": prompt,
        "assistant": assistant,
        "tool_events": tool_events
    }

    if format == "md":
        markdown = _format_trace_markdown(trace)
        return PlainTextResponse(markdown, media_type="text/markdown")

    if format != "json":
        raise HTTPException(status_code=400, detail="Invalid format")

    return JSONResponse(trace)
