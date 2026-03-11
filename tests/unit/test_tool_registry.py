"""Unit tests for tools/registry.py — Tool registration and execution."""

import pytest

from foundry_tui.tools.base import Tool, ToolResult
from foundry_tui.tools.registry import ToolRegistry


class DummyTool(Tool):
    """A simple test tool."""

    name = "dummy"
    description = "A dummy tool for testing"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "A message"},
        },
        "required": ["message"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(content=f"echo: {kwargs.get('message', '')}")


class FailingTool(Tool):
    """A tool that always raises."""

    name = "failing"
    description = "Always fails"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("Tool exploded")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self):
        """Registered tool should be retrievable by name."""
        registry = ToolRegistry()
        tool = DummyTool()
        registry.register(tool)
        assert registry.get("dummy") is tool

    def test_get_unknown_tool(self):
        """Unknown tool name should return None."""
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Tool should execute and return result."""
        registry = ToolRegistry()
        registry.register(DummyTool())
        result = await registry.execute("dummy", '{"message": "hello"}')
        assert result.content == "echo: hello"
        assert result.error is False

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Executing unknown tool should return error result."""
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", "{}")
        assert result.error is True
        assert "Unknown tool" in result.content

    @pytest.mark.asyncio
    async def test_execute_invalid_json(self):
        """Malformed JSON arguments should return error result."""
        registry = ToolRegistry()
        registry.register(DummyTool())
        result = await registry.execute("dummy", "not json{{{")
        assert result.error is True
        assert "Invalid arguments JSON" in result.content

    @pytest.mark.asyncio
    async def test_execute_tool_exception(self):
        """Tool that raises should be caught and return error result."""
        registry = ToolRegistry()
        registry.register(FailingTool())
        result = await registry.execute("failing", "{}")
        assert result.error is True
        assert "Tool exploded" in result.content

    def test_get_definitions(self):
        """Should return OpenAI-format tool schemas."""
        registry = ToolRegistry()
        registry.register(DummyTool())
        defs = registry.get_definitions()
        assert len(defs) == 1
        assert defs[0]["type"] == "function"
        assert defs[0]["function"]["name"] == "dummy"
        assert "parameters" in defs[0]["function"]

    def test_is_empty(self):
        """Empty registry should report True, non-empty False."""
        registry = ToolRegistry()
        assert registry.is_empty() is True
        registry.register(DummyTool())
        assert registry.is_empty() is False

    def test_unregister(self):
        """Unregistered tool should no longer be accessible."""
        registry = ToolRegistry()
        registry.register(DummyTool())
        assert registry.get("dummy") is not None
        registry.unregister("dummy")
        assert registry.get("dummy") is None

    def test_tool_names(self):
        """tool_names should return sorted list of registered names."""
        registry = ToolRegistry()
        registry.register(DummyTool())
        registry.register(FailingTool())
        assert registry.tool_names == ["dummy", "failing"]

    @pytest.mark.asyncio
    async def test_execute_empty_arguments(self):
        """Empty argument string should parse as empty dict."""
        registry = ToolRegistry()
        registry.register(DummyTool())
        result = await registry.execute("dummy", "")
        assert result.error is False
        assert result.content == "echo: "
