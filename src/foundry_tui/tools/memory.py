"""Memory tools for persistent user context via function calling.

Three tools allow models to save, recall, and forget memories about the user.
Memories are stored in ~/.foundry-tui/memories.md with optional embedding
sidecar for semantic search.
"""

import logging

from foundry_tui.api.embeddings import EmbeddingClient
from foundry_tui.storage.memory import (
    delete_embedding,
    delete_memory,
    load_memories,
    save_embedding,
    save_memory,
    search_memories,
    semantic_search,
)
from foundry_tui.tools.base import Tool, ToolResult

logger = logging.getLogger("foundry_tui")


class SaveMemoryTool(Tool):
    """Save a fact or preference about the user for future conversations."""

    name = "save_memory"
    description = (
        "Save a single fact or preference about the user for future conversations. "
        "Store ONE fact per call — if you learn multiple things, call this tool "
        "separately for each fact. This allows the user to manage individual memories. "
        "Use this when you learn something useful (name, preferences, role, projects, etc.)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The fact or preference to remember about the user",
            },
        },
        "required": ["content"],
    }

    def __init__(self, source_model: str = "unknown", embedding_client: EmbeddingClient | None = None) -> None:
        self._source_model = source_model
        self._embedding_client = embedding_client

    def set_source_model(self, model: str) -> None:
        """Update the source model (called on model switch)."""
        self._source_model = model

    async def execute(self, *, content: str) -> ToolResult:
        """Save a memory and optionally embed it."""
        try:
            mem = save_memory(content, self._source_model)

            # Embed if client is available
            if self._embedding_client:
                try:
                    vec = await self._embedding_client.embed(content)
                    save_embedding(mem.id, vec)
                    logger.info("Embedded memory %s (%d dims)", mem.id, len(vec))
                except Exception as e:
                    logger.warning("Failed to embed memory %s: %s", mem.id, e)

            return ToolResult(
                content=f"Memory saved (ID: {mem.id}): {content}"
            )
        except Exception as e:
            return ToolResult(content=f"Error saving memory: {e}", error=True)


class RecallMemoriesTool(Tool):
    """Search stored memories about the user."""

    name = "recall_memories"
    description = (
        "Search your saved memories about the user. Returns matching memories. "
        "Use this to recall facts, preferences, or context from past conversations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword or phrase to find in memories",
            },
        },
        "required": ["query"],
    }

    def __init__(self, embedding_client: EmbeddingClient | None = None) -> None:
        self._embedding_client = embedding_client

    async def execute(self, *, query: str) -> ToolResult:
        """Search memories using embeddings (if available) or keyword fallback."""
        results = []

        # Try semantic search first
        if self._embedding_client:
            try:
                results = await semantic_search(query, self._embedding_client, top_k=5)
                if results:
                    logger.info("Semantic recall for '%s': %d results", query, len(results))
            except Exception as e:
                logger.warning("Semantic search failed, falling back to keyword: %s", e)
                results = []

        # Fall back to keyword search
        if not results:
            results = search_memories(query)

        if not results:
            return ToolResult(content=f"No memories found matching: {query}")

        lines = [f"Found {len(results)} memory(ies):"]
        for i, m in enumerate(results, 1):
            lines.append(f"  [{i}] ({m.id}) {m.content}")
        return ToolResult(content="\n".join(lines))


class ForgetMemoryTool(Tool):
    """Delete a specific memory by its ID."""

    name = "forget_memory"
    description = (
        "Delete a stored memory by its ID. Use recall_memories first to find "
        "the ID of the memory you want to remove."
    )
    parameters = {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "The memory ID to delete (e.g., mem_1709654321)",
            },
        },
        "required": ["memory_id"],
    }

    async def execute(self, *, memory_id: str) -> ToolResult:
        """Delete a memory and its embedding."""
        if delete_memory(memory_id):
            delete_embedding(memory_id)
            return ToolResult(content=f"Memory {memory_id} deleted.")
        return ToolResult(
            content=f"Memory {memory_id} not found.", error=True
        )


def create_memory_tools(
    source_model: str = "unknown",
    embedding_client: EmbeddingClient | None = None,
) -> list[Tool]:
    """Create all 3 memory tools. Always available (no env var needed)."""
    save_tool = SaveMemoryTool(source_model=source_model, embedding_client=embedding_client)
    recall_tool = RecallMemoriesTool(embedding_client=embedding_client)
    return [save_tool, recall_tool, ForgetMemoryTool()]
