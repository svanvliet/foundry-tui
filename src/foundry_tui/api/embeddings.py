"""Azure AI embedding client for semantic memory search.

Uses text-embedding-3-small (1536 dims) deployed on the same
Azure AI endpoint as the chat models. No separate credentials needed.
"""

import logging
import math
import os

from openai import AsyncOpenAI

logger = logging.getLogger("foundry_tui")

# Default deployment name — overridable via env var
DEFAULT_DEPLOYMENT = "text-embedding-3-small"


class EmbeddingClient:
    """Client for Azure OpenAI text embeddings."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str | None = None,
    ):
        self._deployment = deployment or os.getenv(
            "AZURE_AI_EMBEDDING_DEPLOYMENT", DEFAULT_DEPLOYMENT
        )
        base_url = f"{endpoint}/openai/v1"
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=0,
        )
        self._available: bool | None = None  # cached availability check

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string. Returns 1536-dim vector."""
        response = await self._client.embeddings.create(
            input=[text],
            model=self._deployment,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call."""
        if not texts:
            return []
        response = await self._client.embeddings.create(
            input=texts,
            model=self._deployment,
        )
        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]

    async def is_available(self) -> bool:
        """Check if the embedding model is deployed and reachable. Result is cached."""
        if self._available is not None:
            return self._available

        try:
            await self.embed("test")
            self._available = True
            logger.info("Embedding model available: %s", self._deployment)
        except Exception as e:
            self._available = False
            logger.info("Embedding model not available (%s): %s", self._deployment, e)

        return self._available

    async def close(self) -> None:
        """Close the client."""
        await self._client.close()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Pure Python, no deps."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def create_embedding_client() -> EmbeddingClient | None:
    """Create an EmbeddingClient if Azure AI credentials are configured."""
    endpoint = os.getenv("AZURE_AI_ENDPOINT")
    api_key = os.getenv("AZURE_AI_API_KEY")
    deployment = os.getenv("AZURE_AI_EMBEDDING_DEPLOYMENT")

    if not endpoint or not api_key or not deployment:
        return None

    # Normalize to resource-level URL
    if "/api/projects/" in endpoint:
        endpoint = endpoint.split("/api/projects/")[0]
    endpoint = endpoint.rstrip("/")

    return EmbeddingClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment=deployment,
    )
