"""Serverless endpoint API client with streaming support.

This handles models deployed as serverless endpoints (Mistral, etc.).
Each model has its own endpoint and API key.
"""

from collections.abc import AsyncGenerator

import httpx

from foundry_tui.api.azure_openai import Message, StreamChunk, TokenUsage


class ServerlessClient:
    """Client for serverless model endpoints."""

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
        messages: list[Message],
        max_tokens: int | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion."""
        url = f"{self.endpoint}/v1/chat/completions"

        payload = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

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

                    import json

                    try:
                        chunk = json.loads(data)
                        if chunk.get("choices"):
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            finish_reason = choice.get("finish_reason")

                            if content or finish_reason:
                                yield StreamChunk(content=content, finish_reason=finish_reason)
                    except json.JSONDecodeError:
                        continue

    async def chat(
        self,
        messages: list[Message],
        max_tokens: int | None = None,
    ) -> tuple[str, TokenUsage | None]:
        """Get a non-streaming chat completion."""
        url = f"{self.endpoint}/v1/chat/completions"

        payload = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        usage = None
        if "usage" in data:
            usage = TokenUsage(
                prompt_tokens=data["usage"]["prompt_tokens"],
                completion_tokens=data["usage"]["completion_tokens"],
                total_tokens=data["usage"]["total_tokens"],
            )

        return content, usage

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()
