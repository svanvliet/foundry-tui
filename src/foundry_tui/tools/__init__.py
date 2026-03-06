"""Tool definitions for function calling."""

import logging

from foundry_tui.api.embeddings import EmbeddingClient, create_embedding_client
from foundry_tui.tools.config import load_user_tools
from foundry_tui.tools.file_create import CreateFileTool
from foundry_tui.tools.image_generate import GenerateImageTool, create_image_tool
from foundry_tui.tools.memory import create_memory_tools
from foundry_tui.tools.registry import ToolRegistry
from foundry_tui.tools.tavily_search import create_tavily_search_tool

logger = logging.getLogger(__name__)


def create_default_registry(
    source_model: str = "unknown",
    image_quality: str = "high",
) -> tuple[ToolRegistry, EmbeddingClient | None]:
    """Create a ToolRegistry with built-in and user-defined tools.

    Built-in tools are auto-registered when their env vars are configured.
    Memory tools are always registered (file-based, no config needed).
    User-defined tools are loaded from ~/.foundry-tui/tools.json.

    Returns (registry, embedding_client) — client may be None if not configured.
    """
    registry = ToolRegistry()

    # Create embedding client (optional, for semantic memory search)
    embedding_client = create_embedding_client()
    if embedding_client:
        logger.info("Embedding client configured for semantic memory search")

    # Built-in: Memory tools (always available)
    for tool in create_memory_tools(source_model=source_model, embedding_client=embedding_client):
        registry.register(tool)

    # Built-in: Tavily Web Search
    tavily = create_tavily_search_tool()
    if tavily:
        registry.register(tavily)

    # Built-in: File creation (always available, no config needed)
    registry.register(CreateFileTool())

    # Built-in: Image generation (requires AZURE_OPENAI_IMAGE_DEPLOYMENT)
    image_tool = create_image_tool(default_quality=image_quality)
    if image_tool:
        registry.register(image_tool)

    # User-defined tools from config
    for tool in load_user_tools():
        registry.register(tool)

    if registry.is_empty():
        logger.info("No tools configured")
    else:
        logger.info("Tool registry ready: %s", ", ".join(registry.tool_names))

    return registry, embedding_client
