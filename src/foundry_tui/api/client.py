"""Unified API client that routes to the correct backend."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from foundry_tui.api.azure_ai import AzureAIClient
from foundry_tui.api.azure_openai import AzureOpenAIClient, Message, StreamChunk, TokenUsage, ToolCall
from foundry_tui.api.serverless import ServerlessClient
from foundry_tui.config import Config
from foundry_tui.models import DeploymentType, Model, ServerlessDeployment


@dataclass
class ChatClient:
    """Unified chat client that handles all deployment types."""

    config: Config
    _azure_openai: AzureOpenAIClient | None = None
    _azure_ai: AzureAIClient | None = None
    _serverless_clients: dict[str, ServerlessClient] | None = None

    def __post_init__(self):
        """Initialize clients lazily."""
        self._serverless_clients = {}

    @property
    def azure_openai(self) -> AzureOpenAIClient:
        """Get or create Azure OpenAI client."""
        if self._azure_openai is None:
            self._azure_openai = AzureOpenAIClient(
                endpoint=self.config.azure_openai.endpoint,
                api_key=self.config.azure_openai.api_key,
                api_version=self.config.azure_openai.api_version,
            )
        return self._azure_openai

    @property
    def azure_ai(self) -> AzureAIClient:
        """Get or create Azure AI client."""
        if self._azure_ai is None:
            self._azure_ai = AzureAIClient(
                endpoint=self.config.azure_ai.endpoint,
                api_key=self.config.azure_ai.api_key,
            )
        return self._azure_ai

    def get_serverless_client(self, model: Model) -> ServerlessClient:
        """Get or create a serverless client for a model."""
        if not isinstance(model.deployment, ServerlessDeployment):
            raise ValueError(f"Model {model.id} is not a serverless deployment")

        if model.id not in self._serverless_clients:
            endpoint = self.config.get_serverless_endpoint(model.deployment.endpoint_env)
            api_key = self.config.get_serverless_key(model.deployment.key_env)
            self._serverless_clients[model.id] = ServerlessClient(
                endpoint=endpoint,
                api_key=api_key,
            )
        return self._serverless_clients[model.id]

    async def stream_chat(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion using the appropriate backend.

        Tools are only passed if the model supports them.
        """
        deployment_type = model.deployment_type
        effective_tools = tools if (tools and model.capabilities.tools) else None

        if deployment_type == DeploymentType.AZURE_OPENAI:
            async for chunk in self.azure_openai.stream_chat(
                deployment_name=model.deployment.deployment_name,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            ):
                yield chunk

        elif deployment_type == DeploymentType.AZURE_AI:
            async for chunk in self.azure_ai.stream_chat(
                deployment_name=model.deployment.deployment_name,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            ):
                yield chunk

        elif deployment_type == DeploymentType.SERVERLESS:
            client = self.get_serverless_client(model)
            async for chunk in client.stream_chat(
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            ):
                yield chunk

        else:
            raise ValueError(f"Unknown deployment type: {deployment_type}")

    async def chat(
        self,
        model: Model,
        messages: list[Message],
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, TokenUsage | None, list[ToolCall] | None]:
        """Get a non-streaming chat completion."""
        deployment_type = model.deployment_type
        effective_tools = tools if (tools and model.capabilities.tools) else None

        if deployment_type == DeploymentType.AZURE_OPENAI:
            return await self.azure_openai.chat(
                deployment_name=model.deployment.deployment_name,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            )

        elif deployment_type == DeploymentType.AZURE_AI:
            return await self.azure_ai.chat(
                deployment_name=model.deployment.deployment_name,
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            )

        elif deployment_type == DeploymentType.SERVERLESS:
            client = self.get_serverless_client(model)
            return await client.chat(
                messages=messages,
                max_tokens=max_tokens,
                tools=effective_tools,
            )

        else:
            raise ValueError(f"Unknown deployment type: {deployment_type}")

    async def close(self) -> None:
        """Close all clients."""
        if self._azure_ai:
            await self._azure_ai.close()
        for client in self._serverless_clients.values():
            await client.close()
