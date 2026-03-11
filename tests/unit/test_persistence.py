"""Unit tests for storage/persistence.py — User config CRUD."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _patch_config_dir(tmp_path: Path):
    """Patch get_config_dir to use a temp directory."""
    return patch("foundry_tui.storage.persistence.get_config_dir", return_value=tmp_path)


class TestModelIdPersistence:
    """Tests for last model ID get/set."""

    def test_model_id_roundtrip(self, tmp_path: Path):
        """set/get last model ID should round-trip."""
        from foundry_tui.storage.persistence import get_last_model_id, set_last_model_id

        with _patch_config_dir(tmp_path):
            set_last_model_id("gpt-4o")
            assert get_last_model_id() == "gpt-4o"

    def test_model_id_not_set(self, tmp_path: Path):
        """get_last_model_id should return None when not set."""
        from foundry_tui.storage.persistence import get_last_model_id

        with _patch_config_dir(tmp_path):
            assert get_last_model_id() is None


class TestSystemPromptPersistence:
    """Tests for system prompt get/set/clear."""

    def test_system_prompt_roundtrip(self, tmp_path: Path):
        """set/get system prompt should round-trip."""
        from foundry_tui.storage.persistence import get_system_prompt, set_system_prompt

        with _patch_config_dir(tmp_path):
            set_system_prompt("You are a pirate.")
            assert get_system_prompt() == "You are a pirate."

    def test_clear_system_prompt(self, tmp_path: Path):
        """Setting prompt to None should clear it."""
        from foundry_tui.storage.persistence import get_system_prompt, set_system_prompt

        with _patch_config_dir(tmp_path):
            set_system_prompt("You are a pirate.")
            set_system_prompt(None)
            assert get_system_prompt() is None


class TestThemePersistence:
    """Tests for theme get/set."""

    def test_theme_roundtrip(self, tmp_path: Path):
        """set/get theme should round-trip."""
        from foundry_tui.storage.persistence import get_theme, set_theme

        with _patch_config_dir(tmp_path):
            set_theme("nord")
            assert get_theme() == "nord"

    def test_clear_theme(self, tmp_path: Path):
        """Setting theme to None should clear it."""
        from foundry_tui.storage.persistence import get_theme, set_theme

        with _patch_config_dir(tmp_path):
            set_theme("nord")
            set_theme(None)
            assert get_theme() is None


class TestRateLimitsPersistence:
    """Tests for rate limits get/set."""

    def test_rate_limits_roundtrip(self, tmp_path: Path):
        """set/get rate limits should round-trip."""
        from foundry_tui.storage.persistence import get_model_rate_limits, set_model_rate_limits

        with _patch_config_dir(tmp_path):
            set_model_rate_limits("gpt-4o", rpm=60, tpm=80000, capacity=10)
            limits = get_model_rate_limits("gpt-4o")
            assert limits == {"rpm": 60, "tpm": 80000, "capacity": 10}

    def test_rate_limits_not_set(self, tmp_path: Path):
        """Rate limits for unknown model should return None."""
        from foundry_tui.storage.persistence import get_model_rate_limits

        with _patch_config_dir(tmp_path):
            assert get_model_rate_limits("nonexistent") is None

    def test_set_all_rate_limits(self, tmp_path: Path):
        """set_all_rate_limits should replace all rate limits at once."""
        from foundry_tui.storage.persistence import (
            get_model_rate_limits,
            set_all_rate_limits,
        )

        with _patch_config_dir(tmp_path):
            limits = {
                "gpt-4o": {"rpm": 60, "tpm": 80000, "capacity": 10},
                "o4-mini": {"rpm": 10, "tpm": 10000, "capacity": 1},
            }
            set_all_rate_limits(limits)
            assert get_model_rate_limits("gpt-4o") == limits["gpt-4o"]
            assert get_model_rate_limits("o4-mini") == limits["o4-mini"]


class TestMissingConfigFile:
    """Tests for graceful handling of missing config."""

    def test_missing_config_file(self, tmp_path: Path):
        """All getters should return defaults when config file doesn't exist."""
        from foundry_tui.storage.persistence import (
            get_last_model_id,
            get_system_prompt,
            get_theme,
        )

        with _patch_config_dir(tmp_path):
            assert get_last_model_id() is None
            assert get_system_prompt() is None
            assert get_theme() is None

    def test_corrupted_config_file(self, tmp_path: Path):
        """Corrupted config file should return defaults."""
        from foundry_tui.storage.persistence import get_last_model_id

        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json{{{")

        with _patch_config_dir(tmp_path):
            assert get_last_model_id() is None


class TestServerStatePersistence:
    """Tests for server-side state preference."""

    def test_server_state_roundtrip(self, tmp_path: Path):
        """set/get server state should round-trip."""
        from foundry_tui.storage.persistence import get_server_state, set_server_state

        with _patch_config_dir(tmp_path):
            assert get_server_state() is False  # Default
            set_server_state(True)
            assert get_server_state() is True
            set_server_state(False)
            assert get_server_state() is False
