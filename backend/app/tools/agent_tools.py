"""
Agent-facing tools for reporting plans and proposing patches.
"""

import hashlib
import os
import uuid
import difflib
from typing import Any, Dict, List, Optional
import structlog

from app.tools.base import Tool

logger = structlog.get_logger()


class ReportPlanTool(Tool):
    """Tool for reporting structured plans to the client UI"""

    name = "report_plan"
    description = "Report a step-by-step plan to the client UI"
    parameters = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of plan steps"
            },
            "rationale": {
                "type": "string",
                "description": "Optional short rationale for the plan"
            }
        },
        "required": ["steps"]
    }

    async def execute(self, steps: List[str], rationale: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": True,
            "steps": steps,
            "rationale": rationale
        }


class ProposePatchTool(Tool):
    """Tool for proposing unified diff patches to the client UI"""

    name = "propose_patch"
    description = "Propose a unified diff patch for a file without applying it"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to patch (relative to workspace root)"
            },
            "diff": {
                "type": "string",
                "description": "Unified diff patch content for the file"
            },
            "rationale": {
                "type": "string",
                "description": "Short description of the proposed change"
            }
        },
        "required": ["file_path", "diff"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        file_path: str,
        diff: str,
        rationale: Optional[str] = None
    ) -> Dict[str, Any]:
        if not diff.strip():
            return {
                "success": False,
                "error": "Diff content is empty"
            }

        full_path = os.path.join(self.workspace_path, file_path)
        base_hash = None

        try:
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    base_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning("base_hash_compute_failed",
                           file_path=file_path,
                           error=str(e))

        patch_id = str(uuid.uuid4())

        return {
            "success": True,
            "id": patch_id,
            "file_path": file_path,
            "diff": diff,
            "base_hash": base_hash,
            "rationale": rationale
        }


class ProposeDiffTool(Tool):
    """Tool for generating unified diffs from new content."""

    name = "propose_diff"
    description = "Generate a unified diff patch from updated file content"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to patch (relative to workspace root)"
            },
            "new_content": {
                "type": "string",
                "description": "Updated file content to diff against current file"
            },
            "context_lines": {
                "type": "number",
                "description": "Number of context lines in the diff",
                "default": 3
            },
            "rationale": {
                "type": "string",
                "description": "Short description of the proposed change"
            }
        },
        "required": ["file_path", "new_content"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        file_path: str,
        new_content: str,
        context_lines: int = 3,
        rationale: Optional[str] = None
    ) -> Dict[str, Any]:
        full_path = os.path.join(self.workspace_path, file_path)
        base_hash = None

        if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_path)):
            return {
                "success": False,
                "error": "Access denied: path outside workspace"
            }

        try:
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    original_bytes = f.read()
                base_hash = hashlib.sha256(original_bytes).hexdigest()
                original_content = original_bytes.decode("utf-8", errors="ignore")
            else:
                original_content = ""

            diff_lines = list(difflib.unified_diff(
                original_content.splitlines(),
                new_content.splitlines(),
                fromfile=file_path,
                tofile=file_path,
                lineterm="",
                n=max(int(context_lines), 0)
            ))
            diff_text = "\n".join(diff_lines)
            if diff_text:
                diff_text = diff_text + "\n"

            if not diff_text.strip():
                return {
                    "success": False,
                    "error": "No changes detected"
                }

        except Exception as e:
            logger.error("propose_diff_failed", file_path=file_path, error=str(e))
            return {
                "success": False,
                "error": f"Failed to generate diff: {str(e)}"
            }

        return {
            "success": True,
            "id": str(uuid.uuid4()),
            "file_path": file_path,
            "diff": diff_text,
            "base_hash": base_hash,
            "rationale": rationale
        }
