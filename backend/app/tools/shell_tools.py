"""
Shell/command execution tools
"""

import asyncio
from typing import Dict, Any
import structlog

from app.tools.base import Tool

logger = structlog.get_logger()


class RunCommandTool(Tool):
    """Tool for running shell commands"""

    name = "run_command"
    description = "Execute a shell command in the workspace directory"
    requires_approval = True
    approval_scope = "command"
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute"
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (default: 30)",
                "default": 30
            }
        },
        "required": ["command"]
    }

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def approval_prompt(self, arguments: Dict[str, Any]) -> str:
        command = arguments.get("command", "")
        return f"Approve command execution: {command}"

    async def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute shell command"""
        try:
            logger.info("running_command", command=command, workspace=self.workspace_path)

            # Run command in workspace directory
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout} seconds"
                }

            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""
            return_code = process.returncode

            return {
                "success": return_code == 0,
                "return_code": return_code,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "command": command
            }

        except Exception as e:
            logger.error("command_execution_error", command=command, error=str(e))
            return {
                "success": False,
                "error": f"Failed to execute command: {str(e)}"
            }


class RunTestsTool(RunCommandTool):
    """Tool for running tests with optional rerun loops."""

    name = "run_tests"
    description = "Run a test command in the workspace directory"
    requires_approval = True
    approval_scope = "command"
