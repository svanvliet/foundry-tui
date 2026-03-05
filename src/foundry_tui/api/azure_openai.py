"""Azure OpenAI API client with streaming support."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncAzureOpenAI


@dataclass
class StreamChunk:
    """A chunk of streamed response."""

    content: str
    finish_reason: str | None = None


@dataclass
class TokenUsage:
    """Token usage from API response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class Message:
    """A chat message."""

    role: str
    content: str


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
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion.

        Yields StreamChunk objects with content as it arrives.
        The final chunk will have finish_reason set.
        """
        # Convert messages to API format
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Build kwargs - use max_completion_tokens for newer models
        kwargs = {
            "model": deployment_name,
            "messages": api_messages,
            "stream": True,
        }

        # Use max_completion_tokens (newer API) instead of max_tokens
        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                delta = choice.delta

                content = delta.content if delta and delta.content else ""
                finish_reason = choice.finish_reason

                if content or finish_reason:
                    yield StreamChunk(content=content, finish_reason=finish_reason)

    async def chat(
        self,
        deployment_name: str,
        messages: list[Message],
        max_tokens: int | None = None,
    ) -> tuple[str, TokenUsage | None]:
        """Get a non-streaming chat completion.

        Returns the full response content and token usage.
        """
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Build kwargs - use max_completion_tokens for newer models
        kwargs = {
            "model": deployment_name,
            "messages": api_messages,
            "stream": False,
        }

        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return content, usage
