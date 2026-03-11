"""Unified API client — single OpenAI SDK instance for all models.

Routes by model.capabilities.api:
  - "responses" → client.responses.create()  (RAPI)
  - "completions" → client.chat.completions.create()  (CAPI)

All models go through the same Azure AI endpoint.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from foundry_tui.api.types import (
    Message,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    ToolCallFunction,
)
from foundry_tui.config import Config
from foundry_tui.models import Model
from foundry_tui.storage.logger import get_logger


@dataclass
class ResponseResult:
    """Result from a non-streaming RAPI call."""

    content: str
    usage: TokenUsage | None
    tool_calls: list[ToolCall] | None
    response_id: str | None


class ChatClient:
    """Unified chat client backed by a single OpenAI SDK instance."""

    def __init__(self, config: Config):
        self.config = config
        http_client = httpx.AsyncClient(
            event_hooks={
                "request": [self._log_http_request],
                "response": [self._log_http_response],
            }
        )
        base_url = f"{config.azure.endpoint}/openai/v1"
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=config.azure.api_key,
            max_retries=0,
            http_client=http_client,
        )

    # ── Logging ──────────────────────────────────────────────────────

    @staticmethod
    async def _log_http_request(request: httpx.Request) -> None:
        logger = get_logger()
        body_bytes = len(request.content) if request.content else 0
        logger.info(f"HTTP REQUEST: {request.method} {request.url}")
        logger.info(f"  Content-Length: {body_bytes:,} bytes")

        if request.content and body_bytes > 0:
            try:
                body = json.loads(request.content)
                # CAPI uses "messages", RAPI uses "input"
                messages = body.get("messages", [])
                input_items = body.get("input", [])
                if messages:
                    logger.info(f"  Messages: {len(messages)}")
                    for i, msg in enumerate(messages):
                        role = msg.get("role", "?")
                        content = msg.get("content") or ""
                        content_len = len(content) if isinstance(content, str) else len(json.dumps(content))
                        tc_info = ""
                        if msg.get("tool_calls"):
                            tc_info = f" | tool_calls={len(msg['tool_calls'])}"
                        logger.info(f"    [{i}] role={role} | {content_len} chars{tc_info}")
                elif isinstance(input_items, list):
                    logger.info(f"  Input items: {len(input_items)}")
                elif isinstance(input_items, str):
                    logger.info(f"  Input: string ({len(input_items)} chars)")

                tools = body.get("tools", [])
                if tools:
                    tools_json = json.dumps(tools)
                    logger.info(f"  Tool definitions: {len(tools)} tools, {len(tools_json):,} chars")

                params = {k: v for k, v in body.items() if k not in ("messages", "tools", "input", "instructions")}
                logger.info(f"  Params: {params}")
                if body.get("instructions"):
                    logger.info(f"  Instructions: {len(body['instructions'])} chars")
                if body.get("previous_response_id"):
                    logger.info(f"  previous_response_id: {body['previous_response_id']}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.info(f"  Body: (non-JSON, {body_bytes} bytes)")

    @staticmethod
    async def _log_http_response(response: httpx.Response) -> None:
        logger = get_logger()
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

        if response.status_code >= 400:
            try:
                await response.aread()
                logger.error(f"  Error response body: {response.text[:1000]}")
            except Exception:
                logger.error("  Error response: (could not read body)")

    # ── RAPI input conversion ────────────────────────────────────────

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
                if instructions:
                    instructions += "\n\n" + (msg.content or "")
                else:
                    instructions = msg.content or ""

            elif msg.role == "tool":
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.tool_call_id or "",
                        "output": msg.content or "",
                    }
                )

            elif msg.role == "assistant" and msg.tool_calls:
                if msg.content:
                    input_items.append({"role": "assistant", "content": msg.content})
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
                input_items.append({"role": msg.role, "content": msg.content or ""})

        return input_items, instructions

    @staticmethod
    def _build_rapi_tools(
        function_tools: list[dict] | None,
        web_search: bool = False,
    ) -> list[dict] | None:
        """Build RAPI tools list from function tool defs + built-in tools."""
        tools: list[dict] = []

        if web_search:
            tools.append({"type": "web_search_preview"})

        if function_tools:
            for ft in function_tools:
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

    # ── Public API ───────────────────────────────────────────────────

    async def stream_chat(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        store: bool | None = None,
        previous_response_id: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion, routing by model.capabilities.api."""
        effective_tools = tools if (tools and model.capabilities.tools) else None

        if model.capabilities.api == "responses":
            async for chunk in self._stream_responses(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
                store=store,
                previous_response_id=previous_response_id,
            ):
                yield chunk
        else:
            async for chunk in self._stream_completions(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            ):
                yield chunk

    async def chat(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, TokenUsage | None, list[ToolCall] | None]:
        """Get a non-streaming chat completion."""
        effective_tools = tools if (tools and model.capabilities.tools) else None

        if model.capabilities.api == "responses":
            result = await self._respond(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            )
            return result.content, result.usage, result.tool_calls
        else:
            return await self._chat_completions(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.close()

    # ── Chat Completions API (CAPI) ─────────────────────────────────

    async def _stream_completions(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        api_messages = [m.to_api_dict() for m in messages]

        kwargs: dict = {
            "model": model.deployment_name,
            "messages": api_messages,
            "stream": True,
        }
        # Only OpenAI-native models support stream_options
        if model.provider == "openai":
            kwargs["stream_options"] = {"include_usage": True}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            chunk_usage = self._parse_capi_usage(chunk)

            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                delta = choice.delta
                content = delta.content if delta and delta.content else ""
                finish_reason = choice.finish_reason

                tc_deltas = self._parse_capi_tool_deltas(delta)

                if content or finish_reason or tc_deltas or chunk_usage:
                    yield StreamChunk(
                        content=content,
                        finish_reason=finish_reason,
                        tool_calls=tc_deltas,
                        usage=chunk_usage,
                    )
            elif chunk_usage:
                yield StreamChunk(content="", usage=chunk_usage)

    async def _chat_completions(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, TokenUsage | None, list[ToolCall] | None]:
        api_messages = [m.to_api_dict() for m in messages]

        kwargs: dict = {
            "model": model.deployment_name,
            "messages": api_messages,
            "stream": False,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)

        msg = response.choices[0].message
        content = msg.content or ""

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

    # ── Responses API (RAPI) ─────────────────────────────────────────

    async def _stream_responses(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        store: bool | None = None,
        previous_response_id: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        logger = get_logger()
        web_search = model.capabilities.web_search

        # Build input
        if previous_response_id:
            last_user = None
            for msg in reversed(messages):
                if msg.role == "user":
                    last_user = msg.content or ""
                    break
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
                previous_response_id = None
        else:
            input_items, instructions = self._messages_to_input(messages)

        rapi_tools = self._build_rapi_tools(tools, web_search=web_search)

        kwargs: dict = {
            "model": model.deployment_name,
            "input": input_items,
            "stream": True,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        if rapi_tools:
            kwargs["tools"] = rapi_tools
        if store is not None:
            kwargs["store"] = store
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        stream = await self.client.responses.create(**kwargs)

        func_calls: dict[int, dict] = {}
        response_id: str | None = None

        async for event in stream:
            event_type = event.type

            if event_type == "response.output_text.delta":
                yield StreamChunk(content=event.delta)

            elif event_type == "response.function_call_arguments.delta":
                idx = event.output_index
                if idx not in func_calls:
                    func_calls[idx] = {"id": event.item_id, "name": "", "arguments": ""}
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
                    func_calls[idx] = {"id": event.item_id, "name": event.name, "arguments": event.arguments}

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

            elif event_type in (
                "response.web_search_call.in_progress",
                "response.web_search_call.searching",
            ):
                logger.info(f"RAPI: Web search {event_type.split('.')[-1]}")

            elif event_type == "response.web_search_call.completed":
                logger.info("RAPI: Web search completed")

            elif event_type == "response.completed":
                response_id = event.response.id
                usage = self._parse_rapi_usage(event.response.usage)

                finish_reason = "tool_calls" if func_calls else "stop"
                yield StreamChunk(
                    content="",
                    finish_reason=finish_reason,
                    usage=usage,
                    response_id=response_id,
                )

            elif event_type == "response.failed":
                resp = getattr(event, "response", None)
                error = getattr(event, "error", None) or (getattr(resp, "error", None) if resp else None)
                if error:
                    error_msg = getattr(error, "message", None) or str(error)
                elif resp:
                    error_msg = f"status={getattr(resp, 'status', '?')}, id={getattr(resp, 'id', '?')}"
                else:
                    error_msg = f"Unknown RAPI error (event keys: {dir(event)})"
                logger.error(f"RAPI stream failed: {error_msg}")
                raise RuntimeError(f"Responses API error: {error_msg}")

            elif event_type == "response.reasoning_summary_text.delta":
                yield StreamChunk(content=f"<think>{event.delta}</think>")

    async def _respond(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        store: bool | None = None,
        previous_response_id: str | None = None,
    ) -> ResponseResult:
        """Non-streaming RAPI call."""
        web_search = model.capabilities.web_search
        input_items, instructions = self._messages_to_input(messages)
        rapi_tools = self._build_rapi_tools(tools, web_search=web_search)

        kwargs: dict = {
            "model": model.deployment_name,
            "input": input_items,
            "stream": False,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        if rapi_tools:
            kwargs["tools"] = rapi_tools
        if store is not None:
            kwargs["store"] = store
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        response = await self.client.responses.create(**kwargs)

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

        usage = self._parse_rapi_usage(response.usage)

        return ResponseResult(
            content=content,
            usage=usage,
            tool_calls=tool_calls,
            response_id=response.id,
        )

    # ── Usage parsing helpers ────────────────────────────────────────

    @staticmethod
    def _parse_capi_usage(chunk) -> TokenUsage | None:
        if hasattr(chunk, "usage") and chunk.usage:
            cached = 0
            if hasattr(chunk.usage, "prompt_tokens_details") and chunk.usage.prompt_tokens_details:
                cached = getattr(chunk.usage.prompt_tokens_details, "cached_tokens", 0) or 0
            return TokenUsage(
                prompt_tokens=chunk.usage.prompt_tokens or 0,
                completion_tokens=chunk.usage.completion_tokens or 0,
                total_tokens=chunk.usage.total_tokens or 0,
                cached_tokens=cached,
            )
        return None

    @staticmethod
    def _parse_capi_tool_deltas(delta) -> list[ToolCallDelta] | None:
        if delta and delta.tool_calls:
            return [
                ToolCallDelta(
                    index=tc.index,
                    id=tc.id,
                    type=tc.type,
                    function_name=tc.function.name if tc.function else None,
                    function_arguments=tc.function.arguments if tc.function else None,
                )
                for tc in delta.tool_calls
            ]
        return None

    @staticmethod
    def _parse_rapi_usage(usage_data) -> TokenUsage | None:
        if usage_data:
            cached = 0
            if hasattr(usage_data, "input_tokens_details") and usage_data.input_tokens_details:
                cached = getattr(usage_data.input_tokens_details, "cached_tokens", 0) or 0
            return TokenUsage(
                prompt_tokens=usage_data.input_tokens or 0,
                completion_tokens=usage_data.output_tokens or 0,
                total_tokens=usage_data.total_tokens or 0,
                cached_tokens=cached,
            )
        return None
