"""Persistence utilities for user preferences."""

import json
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Get the configuration directory."""
    config_dir = Path.home() / ".foundry-tui"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_user_config_path() -> Path:
    """Get the user configuration file path."""
    return get_config_dir() / "config.json"


def load_user_config() -> dict[str, Any]:
    """Load user configuration."""
    config_path = get_user_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_user_config(config: dict[str, Any]) -> None:
    """Save user configuration."""
    config_path = get_user_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def get_last_model_id() -> str | None:
    """Get the last used model ID."""
    config = load_user_config()
    return config.get("last_model_id")


def set_last_model_id(model_id: str) -> None:
    """Save the last used model ID."""
    config = load_user_config()
    config["last_model_id"] = model_id
    save_user_config(config)
