"""Configuration loading for Foundry TUI."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from foundry_tui.models import Model, ModelCatalog


class ConfigError(Exception):
    """Configuration error."""

    pass


@dataclass
class AzureConfig:
    """Azure AI Foundry configuration — single endpoint for all models.

    ``endpoint`` is the resource-level URL (no /api/projects/... suffix).
    Clients append /openai/v1 to form the base URL for the standard OpenAI SDK.
    """

    endpoint: str
    api_key: str


@dataclass
class AppSettings:
    """Application settings."""

    log_level: str
    context_ratio: float
    cost_warning_threshold: int


@dataclass
class Config:
    """Full application configuration."""

    azure: AzureConfig
    catalog: ModelCatalog
    settings: AppSettings
    default_model: Model


def find_project_root() -> Path:
    """Find the project root directory."""
    current = Path.cwd()

    # Look for markers of project root
    markers = ["models-catalog.json", "pyproject.toml", ".git"]

    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    # Fall back to current directory
    return Path.cwd()


def load_config() -> Config:
    """Load configuration from environment and files."""
    project_root = find_project_root()

    # Load .env file
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Load model catalog
    catalog_path = project_root / "models-catalog.json"
    if not catalog_path.exists():
        raise ConfigError(f"Model catalog not found: {catalog_path}")

    try:
        with open(catalog_path) as f:
            catalog_data = json.load(f)
        catalog = ModelCatalog.model_validate(catalog_data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in model catalog: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to parse model catalog: {e}")

    # Single Azure AI endpoint for all models
    azure_endpoint = os.getenv("AZURE_AI_ENDPOINT")
    azure_key = os.getenv("AZURE_AI_API_KEY")

    if not azure_endpoint or not azure_key:
        raise ConfigError(
            "Missing Azure AI configuration. "
            "Set AZURE_AI_ENDPOINT and AZURE_AI_API_KEY in .env"
        )

    # Normalize to resource-level URL (strip /api/projects/... if present)
    if "/api/projects/" in azure_endpoint:
        azure_endpoint = azure_endpoint.split("/api/projects/")[0]
    azure_endpoint = azure_endpoint.rstrip("/")

    # App settings with defaults
    settings = AppSettings(
        log_level=os.getenv("FOUNDRY_TUI_LOG_LEVEL", "INFO"),
        context_ratio=float(os.getenv("FOUNDRY_TUI_CONTEXT_RATIO", "0.8")),
        cost_warning_threshold=int(os.getenv("FOUNDRY_TUI_COST_WARNING_THRESHOLD", "10000")),
    )

    # Get default model (first chat model, or first model)
    default_model = catalog.get_model("gpt-4o")
    if not default_model and catalog.models:
        default_model = catalog.models[0]
    if not default_model:
        raise ConfigError("No models defined in catalog")

    return Config(
        azure=AzureConfig(
            endpoint=azure_endpoint,
            api_key=azure_key,
        ),
        catalog=catalog,
        settings=settings,
        default_model=default_model,
    )
