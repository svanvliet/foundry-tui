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


def get_model_rate_limits(model_id: str) -> dict | None:
    """Get rate limits for a model (rpm, tpm, capacity)."""
    config = load_user_config()
    return config.get("rate_limits", {}).get(model_id)


def set_model_rate_limits(model_id: str, rpm: int, tpm: int, capacity: int) -> None:
    """Save rate limits for a model."""
    config = load_user_config()
    if "rate_limits" not in config:
        config["rate_limits"] = {}
    config["rate_limits"][model_id] = {"rpm": rpm, "tpm": tpm, "capacity": capacity}
    save_user_config(config)


def set_all_rate_limits(limits: dict[str, dict]) -> None:
    """Save rate limits for all models at once."""
    config = load_user_config()
    config["rate_limits"] = limits
    save_user_config(config)


def get_system_prompt() -> str | None:
    """Get the current system prompt."""
    config = load_user_config()
    return config.get("system_prompt")


def set_system_prompt(prompt: str | None) -> None:
    """Save the system prompt (None to clear)."""
    config = load_user_config()
    if prompt:
        config["system_prompt"] = prompt
    elif "system_prompt" in config:
        del config["system_prompt"]
    save_user_config(config)


def get_theme() -> str | None:
    """Get the saved theme name."""
    config = load_user_config()
    return config.get("theme")


def set_theme(theme: str | None) -> None:
    """Save the theme name (None to clear)."""
    config = load_user_config()
    if theme:
        config["theme"] = theme
    elif "theme" in config:
        del config["theme"]
    save_user_config(config)


def get_server_state() -> bool:
    """Get the server-side state preference (RAPI store=true)."""
    config = load_user_config()
    return config.get("server_state", False)


def set_server_state(enabled: bool) -> None:
    """Save the server-side state preference."""
    config = load_user_config()
    config["server_state"] = enabled
    save_user_config(config)
