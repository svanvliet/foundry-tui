"""Azure OpenAI API client with streaming support."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from openai import AsyncAzureOpenAI


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


class AzureOpenAIClient:
    """Client for Azure OpenAI API."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
    ):
        """Initialize the client."""
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=0,  # Disable automatic retries - show errors immediately
        )

    async def stream_chat(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion.

        Yields StreamChunk objects with content as it arrives.
        The final chunk will have finish_reason set.
        When the model invokes tools, chunks carry tool_calls deltas
        and the final chunk has finish_reason="tool_calls".
        """
        api_messages = [m.to_api_dict() for m in messages]

        kwargs = {
            "model": deployment_name,
            "messages": api_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            # Final usage-only chunk (no choices) when stream_options.include_usage is set
            chunk_usage: TokenUsage | None = None
            if hasattr(chunk, "usage") and chunk.usage:
                cached = 0
                if hasattr(chunk.usage, "prompt_tokens_details") and chunk.usage.prompt_tokens_details:
                    cached = getattr(chunk.usage.prompt_tokens_details, "cached_tokens", 0) or 0
                chunk_usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                    cached_tokens=cached,
                )

            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                delta = choice.delta
                finish_reason = choice.finish_reason

                content = delta.content if delta and delta.content else ""

                # Parse tool call deltas
                tc_deltas: list[ToolCallDelta] | None = None
                if delta and delta.tool_calls:
                    tc_deltas = []
                    for tc in delta.tool_calls:
                        tc_deltas.append(
                            ToolCallDelta(
                                index=tc.index,
                                id=tc.id,
                                type=tc.type,
                                function_name=tc.function.name if tc.function else None,
                                function_arguments=tc.function.arguments if tc.function else None,
                            )
                        )

                if content or finish_reason or tc_deltas or chunk_usage:
                    yield StreamChunk(
                        content=content,
                        finish_reason=finish_reason,
                        tool_calls=tc_deltas,
                        usage=chunk_usage,
                    )
            elif chunk_usage:
                # Usage-only chunk (after all content)
                yield StreamChunk(content="", usage=chunk_usage)

    async def chat(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, TokenUsage | None, list[ToolCall] | None]:
        """Get a non-streaming chat completion.

        Returns (content, token_usage, tool_calls).
        """
        api_messages = [m.to_api_dict() for m in messages]

        kwargs = {
            "model": deployment_name,
            "messages": api_messages,
            "stream": False,
        }

        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)

        msg = response.choices[0].message
        content = msg.content or ""

        # Extract tool calls if present
        tool_calls: list[ToolCall] | None = None
        if msg.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function=ToolCallFunction(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    ),
                )
                for tc in msg.tool_calls
            ]

        usage = None
        if response.usage:
            cached = 0
            if hasattr(response.usage, "prompt_tokens_details") and response.usage.prompt_tokens_details:
                cached = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=cached,
            )

        return content, usage, tool_calls
