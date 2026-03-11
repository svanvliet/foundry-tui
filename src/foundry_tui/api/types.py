"""Shared types for API clients."""

from dataclasses import dataclass, field


@dataclass
class ToolCallFunction:
    """Function details within a tool call."""

    name: str
    arguments: str  # JSON string


@dataclass
class ToolCall:
    """A tool call from the model."""

    id: str
    type: str  # "function"
    function: ToolCallFunction


@dataclass
class ToolCallDelta:
    """A partial tool call from a streaming chunk."""

    index: int
    id: str | None = None
    type: str | None = None
    function_name: str | None = None
    function_arguments: str | None = None


@dataclass
class StreamChunk:
    """A chunk of streamed response."""

    content: str
    finish_reason: str | None = None
    tool_calls: list[ToolCallDelta] | None = None
    usage: "TokenUsage | None" = None
    response_id: str | None = None  # RAPI response ID for state chaining


@dataclass
class TokenUsage:
    """Token usage from API response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int = 0


@dataclass
class Message:
    """A chat message."""

    role: str
    content: str | None = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_api_dict(self) -> dict:
        """Convert to dict for API calls, including tool fields when present."""
        d: dict = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d
