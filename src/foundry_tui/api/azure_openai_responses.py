"""Azure OpenAI Responses API client with streaming support.

Uses the newer Responses API (client.responses.create) instead of
Chat Completions (client.chat.completions.create). Provides built-in
web search via web_search_preview, richer streaming events, and
optional server-side conversation state.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx
from openai import AsyncAzureOpenAI

from foundry_tui.api.azure_openai import (
    Message,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    ToolCallFunction,
)
from foundry_tui.storage.logger import get_logger


@dataclass
class ResponseResult:
    """Result from a non-streaming RAPI call."""

    content: str
    usage: TokenUsage | None
    tool_calls: list[ToolCall] | None
    response_id: str | None


class AzureOpenAIResponsesClient:
    """Client for Azure OpenAI Responses API."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
    ):
        # RAPI requires 2025-03-01-preview or later
        rapi_version = "2025-03-01-preview"
        http_client = httpx.AsyncClient(
            event_hooks={
                "request": [self._log_http_request],
                "response": [self._log_http_response],
            }
        )
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=rapi_version,
            max_retries=0,
            http_client=http_client,
        )

    # ── Logging (reuse pattern from CAPI client) ─────────────────────

    @staticmethod
    async def _log_http_request(request: httpx.Request) -> None:
        logger = get_logger()
        body_bytes = len(request.content) if request.content else 0
        logger.info(f"HTTP REQUEST [RAPI]: {request.method} {request.url}")
        logger.info(f"  Content-Length: {body_bytes:,} bytes")

        if request.content and body_bytes > 0:
            try:
                body = json.loads(request.content)
                input_items = body.get("input", [])
                if isinstance(input_items, list):
                    logger.info(f"  Input items: {len(input_items)}")
                elif isinstance(input_items, str):
                    logger.info(f"  Input: string ({len(input_items)} chars)")

                tools = body.get("tools", [])
                if tools:
                    logger.info(f"  Tools: {len(tools)}")

                params = {
                    k: v
                    for k, v in body.items()
                    if k not in ("input", "tools", "instructions")
                }
                logger.info(f"  Params: {params}")
                if body.get("instructions"):
                    logger.info(
                        f"  Instructions: {len(body['instructions'])} chars"
                    )
                if body.get("previous_response_id"):
                    logger.info(
                        f"  previous_response_id: {body['previous_response_id']}"
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.info(f"  Body: (non-JSON, {body_bytes} bytes)")

    @staticmethod
    async def _log_http_response(response: httpx.Response) -> None:
        logger = get_logger()
        rl_remaining_requests = response.headers.get(
            "x-ratelimit-remaining-requests", "?"
        )
        rl_remaining_tokens = response.headers.get(
            "x-ratelimit-remaining-tokens", "?"
        )
        rl_limit_requests = response.headers.get(
            "x-ratelimit-limit-requests", "?"
        )
        rl_limit_tokens = response.headers.get(
            "x-ratelimit-limit-tokens", "?"
        )
        retry_after = response.headers.get("retry-after-ms") or response.headers.get(
            "retry-after", ""
        )

        logger.info(
            f"HTTP RESPONSE [RAPI]: {response.status_code} | "
            f"RPM: {rl_remaining_requests}/{rl_limit_requests} remaining | "
            f"TPM: {rl_remaining_tokens}/{rl_limit_tokens} remaining"
        )
        if retry_after:
            logger.info(f"  Retry-After: {retry_after}")

        if response.status_code >= 400:
            try:
                await response.aread()
                logger.error(f"  Error response body: {response.text[:1000]}")
            except Exception:
                logger.error("  Error response: (could not read body)")

    # ── Input conversion ─────────────────────────────────────────────

    @staticmethod
    def _messages_to_input(
        messages: list[Message],
    ) -> tuple[list[dict], str | None]:
        """Convert Message list to RAPI input format.

        Returns (input_items, instructions).
        System messages become the ``instructions`` parameter.
        Tool-result messages become ``function_call_output`` items.
        Assistant messages with tool_calls become function_call items.
        """
        input_items: list[dict] = []
        instructions: str | None = None

        for msg in messages:
            if msg.role == "system":
                # Merge multiple system messages
                if instructions:
                    instructions += "\n\n" + (msg.content or "")
                else:
                    instructions = msg.content or ""

            elif msg.role == "tool":
                # Tool result → function_call_output
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.tool_call_id or "",
                        "output": msg.content or "",
                    }
                )

            elif msg.role == "assistant" and msg.tool_calls:
                # Assistant with tool calls → emit function_call items
                # Also emit the text content if any
                if msg.content:
                    input_items.append(
                        {"role": "assistant", "content": msg.content}
                    )
                for tc in msg.tool_calls:
                    input_items.append(
                        {
                            "type": "function_call",
                            "id": tc.id,
                            "call_id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )

            else:
                # Regular user/assistant message
                input_items.append(
                    {"role": msg.role, "content": msg.content or ""}
                )

        return input_items, instructions

    @staticmethod
    def _build_tools(
        function_tools: list[dict] | None,
        web_search: bool = False,
    ) -> list[dict] | None:
        """Build RAPI tools list from function tool defs + built-in tools."""
        tools: list[dict] = []

        if web_search:
            tools.append({"type": "web_search"})

        if function_tools:
            for ft in function_tools:
                # CAPI format: {type: "function", function: {name, description, parameters}}
                # RAPI format: {type: "function", name, description, parameters}
                func = ft.get("function", {})
                tools.append(
                    {
                        "type": "function",
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                        "strict": False,
                    }
                )

        return tools if tools else None

    # ── Streaming ────────────────────────────────────────────────────

    async def stream_response(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
        function_tools: list[dict] | None = None,
        web_search: bool = False,
        store: bool | None = None,
        previous_response_id: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a response using the Responses API.

        Yields StreamChunk objects compatible with the CAPI streaming interface.
        The final chunk's ``response_id`` field (on StreamChunk) carries the
        response ID for chaining via ``previous_response_id``.

        When ``previous_response_id`` is set, only the new user message is sent
        (server has the prior context).
        """
        logger = get_logger()

        # Build input
        if previous_response_id:
            # Server has context — send only the latest user message
            last_user = None
            for msg in reversed(messages):
                if msg.role == "user":
                    last_user = msg.content or ""
                    break
            # Also check for pending tool results that need to be sent
            pending_tool_results: list[dict] = []
            for msg in messages:
                if msg.role == "tool":
                    pending_tool_results.append(
                        {
                            "type": "function_call_output",
                            "call_id": msg.tool_call_id or "",
                            "output": msg.content or "",
                        }
                    )

            if pending_tool_results:
                input_items = pending_tool_results
                instructions = None
            elif last_user is not None:
                input_items = [{"role": "user", "content": last_user}]
                instructions = None
            else:
                input_items, instructions = self._messages_to_input(messages)
                previous_response_id = None  # Can't chain without user msg
        else:
            input_items, instructions = self._messages_to_input(messages)

        tools = self._build_tools(function_tools, web_search=web_search)

        kwargs: dict = {
            "model": deployment_name,
            "input": input_items,
            "stream": True,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
        if store is not None:
            kwargs["store"] = store
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        stream = await self.client.responses.create(**kwargs)

        # Track function calls by output_index for assembly
        func_calls: dict[int, dict] = {}
        response_id: str | None = None

        async for event in stream:
            event_type = event.type

            if event_type == "response.output_text.delta":
                yield StreamChunk(content=event.delta)

            elif event_type == "response.function_call_arguments.delta":
                idx = event.output_index
                if idx not in func_calls:
                    func_calls[idx] = {
                        "id": event.item_id,
                        "name": "",
                        "arguments": "",
                    }
                func_calls[idx]["arguments"] += event.delta

                yield StreamChunk(
                    content="",
                    tool_calls=[
                        ToolCallDelta(
                            index=idx,
                            id=event.item_id,
                            type="function",
                            function_arguments=event.delta,
                        )
                    ],
                )

            elif event_type == "response.function_call_arguments.done":
                idx = event.output_index
                if idx in func_calls:
                    func_calls[idx]["name"] = event.name
                    func_calls[idx]["arguments"] = event.arguments
                else:
                    func_calls[idx] = {
                        "id": event.item_id,
                        "name": event.name,
                        "arguments": event.arguments,
                    }

                # Emit a delta with the function name
                yield StreamChunk(
                    content="",
                    tool_calls=[
                        ToolCallDelta(
                            index=idx,
                            id=event.item_id,
                            type="function",
                            function_name=event.name,
                        )
                    ],
                )

            elif event_type == "response.output_item.added":
                item = event.item
                if hasattr(item, "type") and item.type == "function_call":
                    idx = event.output_index
                    func_calls[idx] = {
                        "id": getattr(item, "call_id", "") or getattr(item, "id", ""),
                        "name": getattr(item, "name", ""),
                        "arguments": "",
                    }
                    # Emit name delta so the UI can show which tool is being called
                    name = getattr(item, "name", "")
                    if name:
                        yield StreamChunk(
                            content="",
                            tool_calls=[
                                ToolCallDelta(
                                    index=idx,
                                    id=func_calls[idx]["id"],
                                    type="function",
                                    function_name=name,
                                )
                            ],
                        )

            elif event_type == "response.web_search_call.in_progress":
                logger.info("RAPI: Web search in progress")

            elif event_type == "response.web_search_call.searching":
                logger.info("RAPI: Web search searching")

            elif event_type == "response.web_search_call.completed":
                logger.info("RAPI: Web search completed")

            elif event_type == "response.completed":
                response_id = event.response.id
                # Extract usage
                usage_data = event.response.usage
                if usage_data:
                    cached = 0
                    if hasattr(usage_data, "input_tokens_details") and usage_data.input_tokens_details:
                        cached = getattr(
                            usage_data.input_tokens_details, "cached_tokens", 0
                        ) or 0
                    usage = TokenUsage(
                        prompt_tokens=usage_data.input_tokens or 0,
                        completion_tokens=usage_data.output_tokens or 0,
                        total_tokens=usage_data.total_tokens or 0,
                        cached_tokens=cached,
                    )
                else:
                    usage = None

                # Determine finish reason
                if func_calls:
                    finish_reason = "tool_calls"
                else:
                    finish_reason = "stop"

                yield StreamChunk(
                    content="",
                    finish_reason=finish_reason,
                    usage=usage,
                    response_id=response_id,
                )

            elif event_type == "response.failed":
                error = getattr(event, "error", None) or getattr(
                    event.response, "error", None
                )
                error_msg = str(error) if error else "Unknown RAPI error"
                logger.error(f"RAPI stream failed: {error_msg}")
                raise RuntimeError(f"Responses API error: {error_msg}")

            elif event_type == "response.reasoning_summary_text.delta":
                # Reasoning models emit thinking via this event
                # Wrap in <think> tags so existing thinking parser handles it
                yield StreamChunk(content=f"<think>{event.delta}</think>")

    # ── Non-streaming ────────────────────────────────────────────────

    async def respond(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
        function_tools: list[dict] | None = None,
        web_search: bool = False,
        store: bool | None = None,
        previous_response_id: str | None = None,
    ) -> ResponseResult:
        """Get a non-streaming response."""
        input_items, instructions = self._messages_to_input(messages)
        tools = self._build_tools(function_tools, web_search=web_search)

        kwargs: dict = {
            "model": deployment_name,
            "input": input_items,
            "stream": False,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
        if store is not None:
            kwargs["store"] = store
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        response = await self.client.responses.create(**kwargs)

        # Extract text content
        content = ""
        tool_calls: list[ToolCall] | None = None

        for item in response.output:
            if hasattr(item, "type"):
                if item.type == "message":
                    for part in getattr(item, "content", []):
                        if hasattr(part, "text"):
                            content += part.text
                elif item.type == "function_call":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append(
                        ToolCall(
                            id=getattr(item, "call_id", "") or getattr(item, "id", ""),
                            type="function",
                            function=ToolCallFunction(
                                name=getattr(item, "name", ""),
                                arguments=getattr(item, "arguments", ""),
                            ),
                        )
                    )

        # Usage
        usage = None
        if response.usage:
            cached = 0
            if hasattr(response.usage, "input_tokens_details") and response.usage.input_tokens_details:
                cached = getattr(
                    response.usage.input_tokens_details, "cached_tokens", 0
                ) or 0
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens or 0,
                completion_tokens=response.usage.output_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
                cached_tokens=cached,
            )

        return ResponseResult(
            content=content,
            usage=usage,
            tool_calls=tool_calls,
            response_id=response.id,
        )
