"""Azure OpenAI API client with streaming support."""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import httpx
from openai import AsyncAzureOpenAI

from foundry_tui.storage.logger import get_logger


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


class AzureOpenAIClient:
    """Client for Azure OpenAI API."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
    ):
        """Initialize the client."""
        # Create httpx client with request/response logging hooks
        http_client = httpx.AsyncClient(
            event_hooks={
                "request": [self._log_http_request],
                "response": [self._log_http_response],
            }
        )
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=0,  # Disable automatic retries - show errors immediately
            http_client=http_client,
        )

    @staticmethod
    async def _log_http_request(request: httpx.Request) -> None:
        """Log outgoing HTTP request details."""
        logger = get_logger()
        body_bytes = len(request.content) if request.content else 0
        logger.info(f"HTTP REQUEST: {request.method} {request.url}")
        logger.info(f"  Content-Length: {body_bytes:,} bytes")

        if request.content and body_bytes > 0:
            try:
                body = json.loads(request.content)
                # Log message count and sizes
                messages = body.get("messages", [])
                logger.info(f"  Messages: {len(messages)}")
                for i, msg in enumerate(messages):
                    role = msg.get("role", "?")
                    content = msg.get("content") or ""
                    content_len = len(content) if isinstance(content, str) else len(json.dumps(content))
                    tc_info = ""
                    if msg.get("tool_calls"):
                        tc_info = f" | tool_calls={len(msg['tool_calls'])}"
                    logger.info(f"    [{i}] role={role} | {content_len} chars{tc_info}")

                # Log tool definitions size
                tools = body.get("tools", [])
                if tools:
                    tools_json = json.dumps(tools)
                    logger.info(f"  Tool definitions: {len(tools)} tools, {len(tools_json):,} chars")

                # Log other params
                params = {k: v for k, v in body.items() if k not in ("messages", "tools")}
                logger.info(f"  Params: {params}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.info(f"  Body: (non-JSON, {body_bytes} bytes)")

    @staticmethod
    async def _log_http_response(response: httpx.Response) -> None:
        """Log HTTP response status and rate limit headers."""
        logger = get_logger()
        # Extract rate-limit headers
        rl_remaining_requests = response.headers.get("x-ratelimit-remaining-requests", "?")
        rl_remaining_tokens = response.headers.get("x-ratelimit-remaining-tokens", "?")
        rl_limit_requests = response.headers.get("x-ratelimit-limit-requests", "?")
        rl_limit_tokens = response.headers.get("x-ratelimit-limit-tokens", "?")
        retry_after = response.headers.get("retry-after-ms") or response.headers.get("retry-after", "")

        logger.info(
            f"HTTP RESPONSE: {response.status_code} | "
            f"RPM: {rl_remaining_requests}/{rl_limit_requests} remaining | "
            f"TPM: {rl_remaining_tokens}/{rl_limit_tokens} remaining"
        )
        if retry_after:
            logger.info(f"  Retry-After: {retry_after}")

        # For error responses, log the body
        if response.status_code >= 400:
            try:
                await response.aread()
                logger.error(f"  Error response body: {response.text[:1000]}")
            except Exception:
                logger.error(f"  Error response: (could not read body)")

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
