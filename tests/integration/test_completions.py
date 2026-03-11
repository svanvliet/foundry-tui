"""Integration tests for models using the Chat Completions API (CAPI).

Tests all models with capabilities.api == "completions" through the unified ChatClient.
"""

import pytest

from foundry_tui.api.client import ChatClient
from foundry_tui.api.types import Message

from .conftest import SIMPLE_PROMPT, TOOL_PROMPT, WEATHER_TOOL

pytestmark = pytest.mark.integration

# All CAPI models from the catalog
CAPI_MODELS = [
    "mistral-small-2503",
    "deepseek-r1",
    "deepseek-v3.2",
    "grok-3",
    "grok-4.1-fast-reasoning",
    "kimi-k2.5",
]


@pytest.fixture(params=CAPI_MODELS)
def model(request, catalog):
    """Get a CAPI model from the catalog."""
    m = catalog.get_model(request.param)
    if m is None:
        pytest.skip(f"Model {request.param} not in catalog")
    if m.capabilities.api != "completions":
        pytest.skip(f"Model {request.param} is not a CAPI model")
    return m


class TestCAPIStreaming:
    """Tests for streaming via Chat Completions API."""

    async def test_streaming_basic(self, chat_client: ChatClient, model):
        """Streaming should produce content chunks with usage."""
        chunks = []
        async for chunk in chat_client.stream_chat(
            model=model,
            messages=SIMPLE_PROMPT,
            max_tokens=100,
        ):
            chunks.append(chunk)

        assert len(chunks) > 0, f"{model.id}: Should produce at least one chunk"

        content = "".join(c.content for c in chunks)
        assert len(content) > 0, f"{model.id}: Should produce non-empty content"

        final_with_usage = [c for c in chunks if c.usage is not None]
        assert len(final_with_usage) > 0, f"{model.id}: Should have usage info"


class TestCAPINonStreaming:
    """Tests for non-streaming Chat Completions API."""

    async def test_non_streaming_basic(self, chat_client: ChatClient, model):
        """Non-streaming should return content and usage."""
        content, usage, tool_calls = await chat_client.chat(
            model=model,
            messages=SIMPLE_PROMPT,
            max_tokens=100,
        )

        assert len(content) > 0, f"{model.id}: Should return non-empty content"


class TestCAPIToolCalling:
    """Tests for tool calling via CAPI."""

    @pytest.fixture(params=["deepseek-v3.2", "grok-3", "grok-4.1-fast-reasoning", "kimi-k2.5", "mistral-small-2503"])
    def tool_model(self, request, catalog):
        m = catalog.get_model(request.param)
        if m is None or not m.capabilities.tools:
            pytest.skip(f"Model {request.param} doesn't support tools")
        return m

    async def test_tool_calling(self, chat_client: ChatClient, tool_model):
        """Tool-capable CAPI models should return tool calls."""
        content, usage, tool_calls = await chat_client.chat(
            model=tool_model,
            messages=TOOL_PROMPT,
            max_tokens=200,
            tools=[WEATHER_TOOL],
        )

        assert tool_calls is not None, f"{tool_model.id}: Should return tool calls"
        assert len(tool_calls) > 0
        assert tool_calls[0].function.name == "get_weather"


class TestCAPIReasoning:
    """Tests specific to reasoning models on CAPI."""

    async def test_reasoning_model_response(self, chat_client: ChatClient, catalog):
        """DeepSeek R1 should produce a correct arithmetic response."""
        model = catalog.get_model("deepseek-r1")
        if model is None:
            pytest.skip("deepseek-r1 not in catalog")

        reasoning_prompt = [
            Message(role="user", content="What is 15 * 23? Think step by step.")
        ]

        chunks = []
        async for chunk in chat_client.stream_chat(
            model=model,
            messages=reasoning_prompt,
            max_tokens=500,
        ):
            chunks.append(chunk)

        content = "".join(c.content for c in chunks)
        assert "345" in content, f"DeepSeek R1 should compute 15*23=345, got: {content[:200]}"
