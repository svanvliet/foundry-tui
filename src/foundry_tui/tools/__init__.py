"""Tool definitions for function calling."""

import logging

from foundry_tui.tools.config import load_user_tools
from foundry_tui.tools.registry import ToolRegistry
from foundry_tui.tools.tavily_search import create_tavily_search_tool

logger = logging.getLogger(__name__)


def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry with built-in and user-defined tools.

    Built-in tools are auto-registered when their env vars are configured.
    User-defined tools are loaded from ~/.foundry-tui/tools.json.
    """
    registry = ToolRegistry()

    # Built-in: Tavily Web Search
    tavily = create_tavily_search_tool()
    if tavily:
        registry.register(tavily)

    # User-defined tools from config
    for tool in load_user_tools():
        registry.register(tool)

    if registry.is_empty():
        logger.info("No tools configured")
    else:
        logger.info("Tool registry ready: %s", ", ".join(registry.tool_names))

    return registry
