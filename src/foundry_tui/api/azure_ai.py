"""Azure AI Services API client with streaming support.

This handles models deployed via Azure AI Services (DeepSeek, Grok, Kimi).
Uses the Azure AI Model Inference API.
"""

import json
from collections.abc import AsyncGenerator

import httpx

from foundry_tui.api.azure_openai import (
    Message,
    StreamChunk,
    ToolCall,
    ToolCallDelta,
    ToolCallFunction,
    TokenUsage,
)


class AzureAIClient:
    """Client for Azure AI Services API."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
    ):
        """Initialize the client."""
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=120.0)

    async def stream_chat(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion."""
        url = f"{self.endpoint}/models/chat/completions?api-version=2024-05-01-preview"

        payload: dict = {
            "messages": [m.to_api_dict() for m in messages],
            "model": deployment_name,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with self.client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)

                        # Parse usage if present (final chunk with stream_options)
                        chunk_usage: TokenUsage | None = None
                        if chunk.get("usage"):
                            u = chunk["usage"]
                            chunk_usage = TokenUsage(
                                prompt_tokens=u.get("prompt_tokens", 0),
                                completion_tokens=u.get("completion_tokens", 0),
                                total_tokens=u.get("total_tokens", 0),
                            )

                        if chunk.get("choices"):
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            finish_reason = choice.get("finish_reason")

                            # Parse tool call deltas
                            tc_deltas: list[ToolCallDelta] | None = None
                            if delta.get("tool_calls"):
                                tc_deltas = []
                                for tc in delta["tool_calls"]:
                                    fn = tc.get("function", {})
                                    tc_deltas.append(
                                        ToolCallDelta(
                                            index=tc.get("index", 0),
                                            id=tc.get("id"),
                                            type=tc.get("type"),
                                            function_name=fn.get("name"),
                                            function_arguments=fn.get("arguments"),
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
                            yield StreamChunk(content="", usage=chunk_usage)
                    except json.JSONDecodeError:
                        continue

    async def chat(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, TokenUsage | None, list[ToolCall] | None]:
        """Get a non-streaming chat completion."""
        url = f"{self.endpoint}/models/chat/completions?api-version=2024-05-01-preview"

        payload: dict = {
            "messages": [m.to_api_dict() for m in messages],
            "model": deployment_name,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""

        # Extract tool calls
        tool_calls: list[ToolCall] | None = None
        if msg.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=ToolCallFunction(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in msg["tool_calls"]
            ]

        usage = None
        if "usage" in data:
            usage = TokenUsage(
                prompt_tokens=data["usage"]["prompt_tokens"],
                completion_tokens=data["usage"]["completion_tokens"],
                total_tokens=data["usage"]["total_tokens"],
            )

        return content, usage, tool_calls

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()
