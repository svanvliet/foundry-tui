"""Tavily web search tool for function calling."""

import logging
import os

import httpx

from foundry_tui.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class TavilySearchTool(Tool):
    """Search the web using the Tavily Search API."""

    name = "web_search"
    description = (
        "Search the web for current information. "
        "Use for questions about recent events, facts, or anything requiring up-to-date data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results (1-10)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def execute(self, *, query: str, max_results: int = 5) -> ToolResult:
        """Execute a Tavily web search."""
        max_results = max(1, min(max_results, 10))

        payload = {
            "query": query,
            "max_results": max_results,
            "include_answer": True,
            "search_depth": "basic",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            resp = await self._client.post(TAVILY_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return ToolResult(content="Error: Invalid Tavily API key", error=True)
            if e.response.status_code == 429:
                return ToolResult(content="Error: Tavily rate limit exceeded", error=True)
            return ToolResult(content=f"Error: Tavily HTTP {e.response.status_code}", error=True)
        except httpx.RequestError as e:
            return ToolResult(content=f"Error: Search request failed: {e}", error=True)

        data = resp.json()

        # Build formatted results
        lines: list[str] = []

        # Include Tavily's direct answer if available
        answer = data.get("answer")
        if answer:
            lines.append(f"Summary: {answer}")
            lines.append("")

        results = data.get("results", [])
        if not results and not answer:
            return ToolResult(content=f"No results found for: {query}")

        for i, result in enumerate(results, 1):
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            snippet = result.get("content", "")
            lines.append(f"[{i}] {title} — {url}")
            if snippet:
                lines.append(f"    {snippet[:200]}")
            lines.append("")

        return ToolResult(content="\n".join(lines).strip())

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


def create_tavily_search_tool() -> TavilySearchTool | None:
    """Create a Tavily Search tool if the API key env var is set."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None

    logger.info("Tavily Search tool configured")
    return TavilySearchTool(api_key=api_key)
