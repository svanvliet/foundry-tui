"""Integration tests for models using the Responses API (RAPI).

Tests all models with capabilities.api == "responses" through the unified ChatClient.
"""

import pytest

from foundry_tui.api.client import ChatClient
from foundry_tui.api.types import Message

from .conftest import SIMPLE_PROMPT, TOOL_PROMPT, WEATHER_TOOL

pytestmark = pytest.mark.integration

# Representative RAPI models
RAPI_MODELS = ["gpt-4o", "gpt-4.1", "o4-mini"]


@pytest.fixture(params=RAPI_MODELS)
def model(request, catalog):
    """Get a RAPI model from the catalog."""
    m = catalog.get_model(request.param)
    if m is None:
        pytest.skip(f"Model {request.param} not in catalog")
    if m.capabilities.api != "responses":
        pytest.skip(f"Model {request.param} is not a RAPI model")
    return m


class TestRAPIStreaming:
    """Tests for streaming via Responses API."""

    async def test_streaming_basic(self, chat_client: ChatClient, model):
        """Streaming should produce content chunks and a final chunk with usage."""
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

        usage = final_with_usage[-1].usage
        assert usage.prompt_tokens > 0
        assert usage.completion_tokens > 0
        assert usage.total_tokens > 0


class TestRAPINonStreaming:
    """Tests for non-streaming Responses API."""

    async def test_non_streaming_basic(self, chat_client: ChatClient, model):
        """Non-streaming should return content and usage."""
        content, usage, tool_calls = await chat_client.chat(
            model=model,
            messages=SIMPLE_PROMPT,
            max_tokens=100,
        )

        assert len(content) > 0, f"{model.id}: Should return non-empty content"
        assert usage is not None
        assert usage.total_tokens > 0


class TestRAPIToolCalling:
    """Tests for tool calling via Responses API."""

    @pytest.fixture(params=["gpt-4o", "gpt-4.1", "o4-mini"])
    def tool_model(self, request, catalog):
        m = catalog.get_model(request.param)
        if m is None or not m.capabilities.tools:
            pytest.skip(f"Model {request.param} doesn't support tools")
        return m

    async def test_tool_calling(self, chat_client: ChatClient, tool_model):
        """RAPI models should return tool calls when given function definitions."""
        chunks = []
        async for chunk in chat_client.stream_chat(
            model=tool_model,
            messages=TOOL_PROMPT,
            max_tokens=200,
            tools=[WEATHER_TOOL],
        ):
            chunks.append(chunk)

        has_tool_calls = any(c.tool_calls for c in chunks)
        has_tool_finish = any(c.finish_reason == "tool_calls" for c in chunks)
        assert has_tool_calls or has_tool_finish, (
            f"{tool_model.id}: Model should invoke the weather tool"
        )


class TestRAPIWebSearch:
    """Tests for built-in web search via Responses API."""

    @pytest.fixture(params=["gpt-4o"])
    def web_model(self, request, catalog):
        m = catalog.get_model(request.param)
        if m is None or not m.capabilities.web_search:
            pytest.skip(f"Model {request.param} doesn't support web search")
        return m

    async def test_web_search(self, chat_client: ChatClient, web_model):
        """Web search should return content with search results."""
        search_prompt = [
            Message(role="user", content="What is the current population of Tokyo?")
        ]
        content = ""
        async for chunk in chat_client.stream_chat(
            model=web_model,
            messages=search_prompt,
            max_tokens=300,
        ):
            content += chunk.content

        assert len(content) > 0, "Web search should produce content"


class TestRAPIResponseChaining:
    """Tests for response ID chaining (server-side state)."""

    async def test_response_id_chaining(self, chat_client: ChatClient, catalog):
        """Should be able to chain responses using previous_response_id."""
        model = catalog.get_model("gpt-4o")
        if model is None:
            pytest.skip("gpt-4o not in catalog")

        # First request
        response_id = None
        async for chunk in chat_client.stream_chat(
            model=model,
            messages=[Message(role="user", content="My name is Alice.")],
            max_tokens=50,
            store=True,
        ):
            if chunk.response_id:
                response_id = chunk.response_id

        assert response_id is not None, "Should receive a response_id"

        # Second request using previous_response_id
        content = ""
        async for chunk in chat_client.stream_chat(
            model=model,
            messages=[Message(role="user", content="What is my name?")],
            max_tokens=50,
            previous_response_id=response_id,
        ):
            content += chunk.content

        assert "alice" in content.lower(), (
            f"Model should remember 'Alice' from chained context, got: {content}"
        )
