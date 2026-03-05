"""Session logging for Foundry TUI."""

import logging
import os
from datetime import datetime
from pathlib import Path


def get_logs_dir() -> Path:
    """Get the logs directory."""
    # Try project directory first, fall back to home
    project_logs = Path.cwd() / "logs"
    if project_logs.parent.exists():
        project_logs.mkdir(exist_ok=True)
        return project_logs

    home_logs = Path.home() / ".foundry-tui" / "logs"
    home_logs.mkdir(parents=True, exist_ok=True)
    return home_logs


def setup_logger(name: str = "foundry_tui") -> logging.Logger:
    """Set up the session logger.

    Creates a new log file for each session with timestamp.
    """
    logger = logging.getLogger(name)

    # Don't add handlers if already configured
    if logger.handlers:
        return logger

    # Get log level from environment
    log_level = os.getenv("FOUNDRY_TUI_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Create logs directory
    logs_dir = get_logs_dir()

    # Create session log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"session_{timestamp}.log"

    # File handler with detailed format
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Log session start
    logger.info("=" * 60)
    logger.info("Foundry TUI session started")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)

    return logger


# Global logger instance
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def log_api_request(model: str, messages: list, **kwargs) -> None:
    """Log an API request."""
    logger = get_logger()
    logger.debug(f"API Request to {model}")
    logger.debug(f"  Messages: {len(messages)} messages")
    for key, value in kwargs.items():
        logger.debug(f"  {key}: {value}")


def log_api_response(model: str, content: str, usage: dict | None = None) -> None:
    """Log an API response."""
    logger = get_logger()
    logger.debug(f"API Response from {model}")
    logger.debug(f"  Content length: {len(content)} chars")
    if usage:
        logger.debug(f"  Usage: {usage}")


def log_token_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    message_breakdown: dict | None = None,
) -> None:
    """Log detailed token usage for an API call.

    Args:
        model: Model ID
        prompt_tokens: Tokens sent (input)
        completion_tokens: Tokens received (output)
        total_tokens: Total tokens
        message_breakdown: Optional dict with role-based token estimates
            e.g. {"system": 150, "history": 2400, "tools": 300, "user": 45}
    """
    logger = get_logger()
    logger.info(f"TOKEN USAGE | model={model}")
    logger.info(f"  Tokens IN  (prompt):     {prompt_tokens:,}")
    logger.info(f"  Tokens OUT (completion): {completion_tokens:,}")
    logger.info(f"  Tokens TOTAL:            {total_tokens:,}")
    if message_breakdown:
        parts = ", ".join(f"{k}={v:,}" for k, v in message_breakdown.items())
        logger.info(f"  Input breakdown: {parts}")


def log_request_detail(
    model: str,
    messages: list,
    tool_defs: list | None = None,
) -> None:
    """Log detailed request content for debugging token usage.

    Args:
        model: Model ID
        messages: List of message dicts sent to the API
        tool_defs: Tool definitions if any
    """
    logger = get_logger()
    logger.info(f"API CALL DETAIL | model={model} | messages={len(messages)}")
    total_chars = 0
    for i, msg in enumerate(messages):
        role = msg.get("role", "?")
        content = msg.get("content") or ""
        content_len = len(content)
        tool_calls = msg.get("tool_calls")
        tool_call_id = msg.get("tool_call_id")

        extra = ""
        if tool_calls:
            extra = f" | tool_calls={len(tool_calls)}"
        if tool_call_id:
            extra = f" | tool_call_id={tool_call_id}"

        logger.info(f"  [{i}] role={role} | {content_len} chars{extra}")
        total_chars += content_len

    est_tokens = total_chars // 4
    logger.info(f"  Total input chars: {total_chars:,} (~{est_tokens:,} tokens est.)")

    if tool_defs:
        tool_json = str(tool_defs)
        logger.info(f"  Tool definitions: {len(tool_defs)} tools, {len(tool_json)} chars")


def log_api_error(model: str, error: Exception) -> None:
    """Log an API error."""
    logger = get_logger()
    logger.error(f"API Error from {model}: {error}")


def log_event(event: str, **details) -> None:
    """Log a general event."""
    logger = get_logger()
    detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
    logger.info(f"{event}: {detail_str}" if detail_str else event)
