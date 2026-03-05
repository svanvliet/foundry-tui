"""Memory tools for persistent user context via function calling.

Three tools allow models to save, recall, and forget memories about the user.
Memories are stored in ~/.foundry-tui/memories.md.
"""

import logging

from foundry_tui.storage.memory import (
    delete_memory,
    load_memories,
    save_memory,
    search_memories,
)
from foundry_tui.tools.base import Tool, ToolResult

logger = logging.getLogger("foundry_tui")


class SaveMemoryTool(Tool):
    """Save a fact or preference about the user for future conversations."""

    name = "save_memory"
    description = (
        "Save a fact, preference, or important detail about the user so you can "
        "remember it in future conversations. Use this when you learn something "
        "useful about the user (name, preferences, role, projects, etc.)."
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

    def __init__(self, source_model: str = "unknown") -> None:
        self._source_model = source_model

    def set_source_model(self, model: str) -> None:
        """Update the source model (called on model switch)."""
        self._source_model = model

    async def execute(self, *, content: str) -> ToolResult:
        """Save a memory."""
        try:
            mem = save_memory(content, self._source_model)
            return ToolResult(
                content=f"Memory saved (ID: {mem.id}): {content}"
            )
        except Exception as e:
            return ToolResult(content=f"Error saving memory: {e}", error=True)


class RecallMemoriesTool(Tool):
    """Search stored memories about the user by keyword."""

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

    async def execute(self, *, query: str) -> ToolResult:
        """Search memories."""
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
        """Delete a memory."""
        if delete_memory(memory_id):
            return ToolResult(content=f"Memory {memory_id} deleted.")
        return ToolResult(
            content=f"Memory {memory_id} not found.", error=True
        )


def create_memory_tools(source_model: str = "unknown") -> list[Tool]:
    """Create all 3 memory tools. Always available (no env var needed)."""
    save_tool = SaveMemoryTool(source_model=source_model)
    return [save_tool, RecallMemoriesTool(), ForgetMemoryTool()]
