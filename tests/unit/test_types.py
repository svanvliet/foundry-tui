"""Unit tests for api/types.py — Message, StreamChunk, TokenUsage."""

from foundry_tui.api.types import (
    Message,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    ToolCallFunction,
)


class TestMessageToApiDict:
    """Tests for Message.to_api_dict() serialization."""

    def test_basic_user_message(self):
        """Basic user message should produce minimal dict."""
        msg = Message(role="user", content="hello")
        d = msg.to_api_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_assistant_message(self):
        """Assistant message with content."""
        msg = Message(role="assistant", content="Hi there!")
        d = msg.to_api_dict()
        assert d == {"role": "assistant", "content": "Hi there!"}

    def test_with_tool_calls(self):
        """Message with tool_calls should include them in the dict."""
        tc = ToolCall(
            id="call_123",
            type="function",
            function=ToolCallFunction(name="search", arguments='{"q": "hello"}'),
        )
        msg = Message(role="assistant", content="", tool_calls=[tc])
        d = msg.to_api_dict()
        assert d["role"] == "assistant"
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["id"] == "call_123"
        assert d["tool_calls"][0]["function"]["name"] == "search"

    def test_tool_result_message(self):
        """Tool result message should include tool_call_id."""
        msg = Message(role="tool", content="search result", tool_call_id="call_123", name="search")
        d = msg.to_api_dict()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "call_123"
        assert d["name"] == "search"
        assert d["content"] == "search result"

    def test_none_content_omitted(self):
        """Message with content=None should omit content key."""
        msg = Message(role="assistant", content=None)
        d = msg.to_api_dict()
        assert "content" not in d

    def test_empty_content_included(self):
        """Message with empty string content should include it."""
        msg = Message(role="assistant", content="")
        d = msg.to_api_dict()
        assert d["content"] == ""

    def test_no_tool_calls_not_in_dict(self):
        """Message without tool_calls should not have that key."""
        msg = Message(role="user", content="hi")
        d = msg.to_api_dict()
        assert "tool_calls" not in d
        assert "tool_call_id" not in d
        assert "name" not in d


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_creation(self):
        """All fields should be populated correctly."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cached_tokens=20,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cached_tokens == 20

    def test_cached_tokens_default(self):
        """cached_tokens should default to 0."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert usage.cached_tokens == 0


class TestStreamChunk:
    """Tests for StreamChunk dataclass."""

    def test_defaults(self):
        """Optional fields should default to None."""
        chunk = StreamChunk(content="hello")
        assert chunk.content == "hello"
        assert chunk.finish_reason is None
        assert chunk.tool_calls is None
        assert chunk.usage is None
        assert chunk.response_id is None

    def test_with_all_fields(self):
        """StreamChunk with all fields populated."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        delta = ToolCallDelta(index=0, function_name="test")
        chunk = StreamChunk(
            content="",
            finish_reason="tool_calls",
            tool_calls=[delta],
            usage=usage,
            response_id="resp_abc",
        )
        assert chunk.finish_reason == "tool_calls"
        assert len(chunk.tool_calls) == 1
        assert chunk.usage.total_tokens == 15
        assert chunk.response_id == "resp_abc"


class TestToolCallDelta:
    """Tests for ToolCallDelta dataclass."""

    def test_minimal(self):
        """ToolCallDelta with only index."""
        delta = ToolCallDelta(index=0)
        assert delta.index == 0
        assert delta.id is None
        assert delta.function_name is None
        assert delta.function_arguments is None

    def test_full(self):
        """ToolCallDelta with all fields."""
        delta = ToolCallDelta(
            index=0,
            id="call_1",
            type="function",
            function_name="search",
            function_arguments='{"q": "test"}',
        )
        assert delta.id == "call_1"
        assert delta.function_name == "search"
