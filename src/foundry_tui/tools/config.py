"""Load user-defined tools from JSON configuration."""

import json
import logging
import os
import re
from pathlib import Path

import httpx

from foundry_tui.storage.persistence import get_config_dir
from foundry_tui.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


def _interpolate_env(value: str) -> str:
    """Replace ${ENV_VAR} placeholders with environment variable values."""
    def replacer(match: re.Match) -> str:
        var = match.group(1)
        return os.environ.get(var, match.group(0))
    return re.sub(r"\$\{(\w+)\}", replacer, value)


class HttpTool(Tool):
    """A user-defined tool that makes HTTP requests."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        endpoint: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body_template: dict | None = None,
        result_path: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self._endpoint = endpoint
        self._method = method.upper()
        self._headers = headers or {}
        self._body_template = body_template
        self._result_path = result_path
        self._client = httpx.AsyncClient(timeout=30.0)

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the HTTP tool with given arguments."""
        url = _interpolate_env(self._endpoint)
        headers = {k: _interpolate_env(v) for k, v in self._headers.items()}

        # Substitute arguments into URL query params for GET, body for POST
        try:
            if self._method == "GET":
                resp = await self._client.get(url, headers=headers, params=kwargs)
            else:
                body = dict(self._body_template) if self._body_template else kwargs
                resp = await self._client.request(self._method, url, headers=headers, json=body)

            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return ToolResult(content=f"HTTP Error {e.response.status_code}: {e.response.text[:200]}", error=True)
        except httpx.RequestError as e:
            return ToolResult(content=f"Request Error: {e}", error=True)

        # Try to extract a specific path from JSON response
        try:
            data = resp.json()
            if self._result_path:
                for key in self._result_path.lstrip("$.").split("."):
                    data = data[key]
            return ToolResult(content=json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data))
        except (json.JSONDecodeError, KeyError, TypeError):
            return ToolResult(content=resp.text[:2000])


def load_user_tools() -> list[Tool]:
    """Load user-defined tools from ~/.foundry-tui/tools.json."""
    config_path = get_config_dir() / "tools.json"
    if not config_path.exists():
        return []

    try:
        with open(config_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load tools config %s: %s", config_path, e)
        return []

    tools: list[Tool] = []
    for tool_def in config.get("tools", []):
        try:
            name = tool_def["name"]
            description = tool_def["description"]
            parameters = tool_def["parameters"]
            endpoint = tool_def["endpoint"]

            tool = HttpTool(
                name=name,
                description=description,
                parameters=parameters,
                endpoint=endpoint,
                method=tool_def.get("method", "GET"),
                headers=tool_def.get("headers"),
                body_template=tool_def.get("body_template"),
                result_path=tool_def.get("result_path"),
            )
            tools.append(tool)
            logger.info("Loaded user tool: %s", name)
        except KeyError as e:
            logger.warning("Skipping invalid tool definition (missing %s): %s", e, tool_def.get("name", "unknown"))

    return tools
