"""
Base tool definitions and registry
"""

from typing import Any, Dict, List, Callable, Optional
from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger()


class Tool(ABC):
    """Base class for all tools"""

    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """Registry for managing available tools"""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool"""
        self.tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name)

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI format"""
        return [tool.to_dict() for tool in self.tools.values()]

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with arguments"""
        tool = self.get(name)
        if not tool:
            logger.error("tool_not_found", name=name)
            return {
                "success": False,
                "error": f"Tool '{name}' not found"
            }

        try:
            logger.info("executing_tool", name=name, arguments=arguments)
            result = await tool.execute(**arguments)
            logger.info("tool_executed", name=name, success=True)
            return result
        except Exception as e:
            logger.error("tool_execution_error", name=name, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }


# Global tool registry
tool_registry = ToolRegistry()
