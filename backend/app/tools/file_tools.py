"""
File system tools for the agent
"""

import os
import re
import aiofiles
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import structlog

from app.tools.base import Tool

logger = structlog.get_logger()


class ReadFileTool(Tool):
    """Tool for reading file contents"""

    name = "read_file"
    description = "Read the contents of a file from the workspace"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read, relative to workspace root"
            }
        },
        "required": ["file_path"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(self, file_path: str) -> Dict[str, Any]:
        """Read file contents"""
        try:
            full_path = os.path.join(self.workspace_path, file_path)

            # Security check: prevent directory traversal
            if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_path)):
                return {
                    "success": False,
                    "error": "Access denied: path outside workspace"
                }

            if not os.path.exists(full_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }

            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                content = await f.read()

            return {
                "success": True,
                "file_path": file_path,
                "content": content,
                "size": len(content)
            }

        except Exception as e:
            logger.error("read_file_error", file_path=file_path, error=str(e))
            return {
                "success": False,
                "error": f"Failed to read file: {str(e)}"
            }


class WriteFileTool(Tool):
    """Tool for writing file contents"""

    name = "write_file"
    description = "Write or create a file in the workspace"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write, relative to workspace root"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["file_path", "content"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(self, file_path: str, content: str) -> Dict[str, Any]:
        """Write file contents"""
        try:
            full_path = os.path.join(self.workspace_path, file_path)

            # Security check
            if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_path)):
                return {
                    "success": False,
                    "error": "Access denied: path outside workspace"
                }

            # Create parent directories if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            return {
                "success": True,
                "file_path": file_path,
                "bytes_written": len(content)
            }

        except Exception as e:
            logger.error("write_file_error", file_path=file_path, error=str(e))
            return {
                "success": False,
                "error": f"Failed to write file: {str(e)}"
            }


class ListFilesTool(Tool):
    """Tool for listing files in a directory"""

    name = "list_files"
    description = "List files and directories in the workspace"
    parameters = {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path to list, relative to workspace root. Use '.' for root."
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list files recursively",
                "default": False
            }
        },
        "required": ["directory"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(self, directory: str = ".", recursive: bool = False) -> Dict[str, Any]:
        """List files in directory"""
        try:
            full_path = os.path.join(self.workspace_path, directory)

            # Security check
            if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_path)):
                return {
                    "success": False,
                    "error": "Access denied: path outside workspace"
                }

            if not os.path.exists(full_path):
                return {
                    "success": False,
                    "error": f"Directory not found: {directory}"
                }

            if not os.path.isdir(full_path):
                return {
                    "success": False,
                    "error": f"Not a directory: {directory}"
                }

            files = []
            directories = []

            if recursive:
                for root, dirs, filenames in os.walk(full_path):
                    rel_root = os.path.relpath(root, self.workspace_path)
                    for filename in filenames:
                        file_path = os.path.join(rel_root, filename)
                        files.append(file_path)
            else:
                for item in os.listdir(full_path):
                    item_path = os.path.join(full_path, item)
                    rel_path = os.path.relpath(item_path, self.workspace_path)

                    if os.path.isfile(item_path):
                        files.append(rel_path)
                    elif os.path.isdir(item_path):
                        directories.append(rel_path)

            return {
                "success": True,
                "directory": directory,
                "files": sorted(files),
                "directories": sorted(directories),
                "total_files": len(files),
                "total_directories": len(directories)
            }

        except Exception as e:
            logger.error("list_files_error", directory=directory, error=str(e))
            return {
                "success": False,
                "error": f"Failed to list files: {str(e)}"
            }


class ApplyPatchTool(Tool):
    """Tool for applying unified diff patches"""

    name = "apply_patch"
    description = "Apply a unified diff patch to a file"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to patch"
            },
            "patch": {
                "type": "string",
                "description": "Unified diff patch content"
            }
        },
        "required": ["file_path", "patch"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(self, file_path: str, patch: str) -> Dict[str, Any]:
        """Apply patch to file"""
        try:
            full_path = os.path.join(self.workspace_path, file_path)

            # Security check
            if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_path)):
                return {
                    "success": False,
                    "error": "Access denied: path outside workspace"
                }

            if not os.path.exists(full_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }

            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                content = await f.read()

            patched = self._apply_unified_diff(content, patch)
            if patched is None:
                return {
                    "success": False,
                    "error": "Failed to apply patch: hunk mismatch"
                }

            async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:
                await f.write(patched)

            return {
                "success": True,
                "file_path": file_path,
                "bytes_written": len(patched)
            }

        except Exception as e:
            logger.error("apply_patch_error", file_path=file_path, error=str(e))
            return {
                "success": False,
                "error": f"Failed to apply patch: {str(e)}"
            }

    def _parse_hunks(self, diff_text: str) -> List[Tuple[int, int, List[str]]]:
        """Parse unified diff hunks."""
        hunks = []
        lines = diff_text.splitlines()
        i = 0
        hunk_header = re.compile(r"^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@")

        while i < len(lines):
            line = lines[i]
            match = hunk_header.match(line)
            if not match:
                i += 1
                continue

            old_start = int(match.group(1))
            old_len = int(match.group(2) or "1")
            i += 1
            hunk_lines = []
            while i < len(lines) and not lines[i].startswith('@@'):
                hunk_lines.append(lines[i])
                i += 1
            hunks.append((old_start, old_len, hunk_lines))

        return hunks

    def _apply_unified_diff(self, content: str, diff_text: str) -> Optional[str]:
        """Apply unified diff to content and return patched content."""
        original_lines = content.splitlines()
        output_lines = []
        cursor = 0

        hunks = self._parse_hunks(diff_text)
        if not hunks:
            return None

        for old_start, _old_len, hunk_lines in hunks:
            # Convert 1-based diff line numbers to 0-based index
            target_index = max(old_start - 1, 0)
            output_lines.extend(original_lines[cursor:target_index])
            cursor = target_index

            for hunk_line in hunk_lines:
                if hunk_line.startswith('@@'):
                    continue
                if hunk_line.startswith('---') or hunk_line.startswith('+++') or hunk_line.startswith('diff '):
                    continue
                if hunk_line.startswith('\\'):
                    continue  # "\ No newline at end of file"

                prefix = hunk_line[:1]
                text = hunk_line[1:]

                if prefix == ' ':
                    if cursor >= len(original_lines) or original_lines[cursor] != text:
                        return None
                    output_lines.append(text)
                    cursor += 1
                elif prefix == '-':
                    if cursor >= len(original_lines) or original_lines[cursor] != text:
                        return None
                    cursor += 1
                elif prefix == '+':
                    output_lines.append(text)

        output_lines.extend(original_lines[cursor:])
        return "\n".join(output_lines)
