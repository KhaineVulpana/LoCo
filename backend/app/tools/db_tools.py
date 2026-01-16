"""
Read-only database tools.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path

import aiosqlite
import structlog
from sqlalchemy.engine.url import make_url

from app.tools.base import Tool
from app.core.config import settings

logger = structlog.get_logger()


_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|pragma|attach|detach|vacuum|replace|truncate|begin|commit|rollback)\b",
    re.IGNORECASE
)


class ReadOnlySqlTool(Tool):
    """Run read-only SQL against the local SQLite database."""

    name = "read_only_sql"
    description = "Execute a read-only SQL query against the local SQLite database."
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Read-only SQL query (SELECT only)"
            },
            "params": {
                "type": "object",
                "description": "Optional named parameters"
            },
            "limit": {
                "type": "number",
                "description": "Max rows to return",
                "default": 100
            }
        },
        "required": ["query"]
    }

    def approval_prompt(self, arguments: Dict[str, Any]) -> str:
        return "Approve read-only SQL query"

    def _resolve_db_path(self) -> Optional[Path]:
        try:
            url = make_url(settings.DATABASE_URL)
        except Exception as exc:
            logger.error("db_url_parse_failed", error=str(exc))
            return None

        if not url.drivername.startswith("sqlite"):
            return None

        database = url.database or ""
        if not database or database == ":memory:":
            return None

        path = Path(database)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return path

    def _validate_query(self, query: str) -> Optional[str]:
        if not query or not query.strip():
            return "Query is empty."

        if ";" in query.strip().rstrip(";"):
            return "Multiple statements are not allowed."

        lowered = query.strip().lower()
        if not (lowered.startswith("select") or lowered.startswith("with")):
            return "Only SELECT queries are allowed."

        if _WRITE_KEYWORDS.search(query):
            return "Query contains write keywords."

        return None

    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        error = self._validate_query(query)
        if error:
            return {"success": False, "error": error}

        db_path = self._resolve_db_path()
        if not db_path or not db_path.exists():
            return {"success": False, "error": "Database file not found."}

        limit = max(int(limit), 1)
        uri = f"file:{db_path.as_posix()}?mode=ro"

        try:
            async with aiosqlite.connect(uri, uri=True) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(query, params or {}) as cursor:
                    rows = await cursor.fetchmany(limit + 1)
                    truncated = len(rows) > limit
                    rows = rows[:limit]
                    columns = [col[0] for col in cursor.description or []]
                    result_rows = [dict(row) for row in rows]

            return {
                "success": True,
                "columns": columns,
                "rows": result_rows,
                "row_count": len(result_rows),
                "truncated": truncated
            }
        except Exception as exc:
            logger.error("read_only_sql_failed", error=str(exc))
            return {"success": False, "error": f"Query failed: {str(exc)}"}
