"""Shared fixtures for integration tests.

All integration tests load real credentials from .env and hit the live
Azure AI endpoint. Mark all tests with @pytest.mark.integration so they
can be skipped with: pytest -m "not integration"
"""

import pytest

from foundry_tui.api.client import ChatClient
from foundry_tui.api.types import Message
from foundry_tui.config import load_config
from foundry_tui.models import ModelCatalog


def _has_credentials() -> bool:
    """Check if required Azure credentials are available."""
    try:
        load_config()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.integration

SKIP_REASON = "Azure credentials not available (check .env)"

# Cache config at module level (it's just data, no event loop)
_config = None


def _get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config


@pytest.fixture(scope="session")
def config():
    """Load real config from .env — session-scoped to avoid repeated IO."""
    if not _has_credentials():
        pytest.skip(SKIP_REASON)
    return _get_config()


@pytest.fixture(scope="session")
def catalog(config) -> ModelCatalog:
    """Get the model catalog."""
    return config.catalog


@pytest.fixture
def chat_client(config) -> ChatClient:
    """Create a fresh ChatClient per test to avoid shared-connection issues."""
    return ChatClient(config)


# Shared test prompt — deterministic and fast
SIMPLE_PROMPT = [Message(role="user", content="Say hello in exactly 3 words.")]

# Tool definition for tool-calling tests
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
            },
            "required": ["location"],
        },
    },
}

TOOL_PROMPT = [
    Message(role="user", content="What's the weather like in Seattle right now?")
]
