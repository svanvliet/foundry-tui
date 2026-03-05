"""Tool registry for managing and executing tools."""

import json
import logging

from foundry_tui.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry that holds tools and dispatches execution."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Look up a tool by function name."""
        return self._tools.get(name)

    def get_definitions(self) -> list[dict]:
        """Return all tool schemas in OpenAI API format."""
        return [t.get_definition() for t in self._tools.values()]

    def is_empty(self) -> bool:
        """Check whether any tools are registered."""
        return len(self._tools) == 0

    @property
    def tool_names(self) -> list[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools.keys())

    async def execute(self, name: str, arguments: str) -> ToolResult:
        """Parse JSON arguments and execute a tool by name.

        Returns a ToolResult; never raises.
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(content=f"Error: Unknown tool '{name}'", error=True)

        try:
            kwargs = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as e:
            return ToolResult(content=f"Error: Invalid arguments JSON: {e}", error=True)

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(content=f"Error executing {name}: {e}", error=True)
