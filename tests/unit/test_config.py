"""Unit tests for config.py — Configuration loading and validation."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry_tui.config import ConfigError, load_config


@pytest.fixture
def mock_catalog(tmp_path: Path) -> Path:
    """Create a minimal valid catalog file."""
    catalog = {
        "models": [
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "openai",
                "category": "chat",
                "deployment": {"deployment_name": "gpt-4o"},
                "capabilities": {"tools": True, "streaming": True},
                "context_window": 128000,
                "max_output_tokens": 16384,
            }
        ]
    }
    catalog_path = tmp_path / "models-catalog.json"
    catalog_path.write_text(json.dumps(catalog))
    return tmp_path


@pytest.fixture
def full_env_vars() -> dict[str, str]:
    """Complete set of required environment variables."""
    return {
        "AZURE_AI_ENDPOINT": "https://test.services.ai.azure.com/",
        "AZURE_AI_API_KEY": "test-key-123",
    }


class TestLoadConfigSuccess:
    """Tests for successful configuration loading."""

    def test_load_config_success(self, mock_catalog: Path, full_env_vars: dict):
        """Config should load successfully with all required env vars."""
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, full_env_vars, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    config = load_config()

        assert config.azure.endpoint == "https://test.services.ai.azure.com"
        assert config.azure.api_key == "test-key-123"

    def test_endpoint_strips_project_path(self, mock_catalog: Path):
        """Endpoint with /api/projects/... suffix should be normalized."""
        env = {
            "AZURE_AI_ENDPOINT": "https://test.services.ai.azure.com/api/projects/my-project",
            "AZURE_AI_API_KEY": "test-key-123",
        }
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, env, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    config = load_config()

        assert config.azure.endpoint == "https://test.services.ai.azure.com"

    def test_default_model_gpt4o(self, mock_catalog: Path, full_env_vars: dict):
        """Default model should be gpt-4o when it exists in catalog."""
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, full_env_vars, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    config = load_config()

        assert config.default_model.id == "gpt-4o"

    def test_default_settings(self, mock_catalog: Path, full_env_vars: dict):
        """App settings should have correct defaults."""
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, full_env_vars, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    config = load_config()

        assert config.settings.log_level == "INFO"
        assert config.settings.context_ratio == 0.8
        assert config.settings.cost_warning_threshold == 10000

    def test_custom_settings_from_env(self, mock_catalog: Path, full_env_vars: dict):
        """App settings should be overridable via env vars."""
        custom_env = {
            **full_env_vars,
            "FOUNDRY_TUI_LOG_LEVEL": "DEBUG",
            "FOUNDRY_TUI_CONTEXT_RATIO": "0.5",
            "FOUNDRY_TUI_COST_WARNING_THRESHOLD": "5000",
        }
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, custom_env, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    config = load_config()

        assert config.settings.log_level == "DEBUG"
        assert config.settings.context_ratio == 0.5
        assert config.settings.cost_warning_threshold == 5000

    def test_endpoint_trailing_slash_stripped(self, mock_catalog: Path, full_env_vars: dict):
        """Trailing slash on endpoint should be stripped."""
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, full_env_vars, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    config = load_config()

        assert not config.azure.endpoint.endswith("/")


class TestLoadConfigErrors:
    """Tests for configuration error handling."""

    def test_missing_azure_ai_endpoint(self, mock_catalog: Path):
        """Missing AZURE_AI_ENDPOINT should raise ConfigError."""
        env = {"AZURE_AI_API_KEY": "key"}
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, env, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    with pytest.raises(ConfigError, match="AZURE_AI"):
                        load_config()

    def test_missing_azure_ai_key(self, mock_catalog: Path):
        """Missing AZURE_AI_API_KEY should raise ConfigError."""
        env = {"AZURE_AI_ENDPOINT": "https://test/"}
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, env, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    with pytest.raises(ConfigError, match="AZURE_AI"):
                        load_config()

    def test_missing_both_credentials(self, mock_catalog: Path):
        """Missing both endpoint and key should raise ConfigError."""
        with patch("foundry_tui.config.find_project_root", return_value=mock_catalog):
            with patch.dict(os.environ, {}, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    with pytest.raises(ConfigError, match="AZURE_AI"):
                        load_config()

    def test_invalid_catalog_json(self, tmp_path: Path, full_env_vars: dict):
        """Malformed catalog JSON should raise ConfigError."""
        (tmp_path / "models-catalog.json").write_text("{not valid json")
        with patch("foundry_tui.config.find_project_root", return_value=tmp_path):
            with patch.dict(os.environ, full_env_vars, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    with pytest.raises(ConfigError):
                        load_config()

    def test_missing_catalog_file(self, tmp_path: Path, full_env_vars: dict):
        """Missing catalog file should raise ConfigError."""
        with patch("foundry_tui.config.find_project_root", return_value=tmp_path):
            with patch.dict(os.environ, full_env_vars, clear=True):
                with patch("foundry_tui.config.load_dotenv"):
                    with pytest.raises(ConfigError, match="not found"):
                        load_config()
