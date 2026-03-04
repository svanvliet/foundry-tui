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


def log_api_error(model: str, error: Exception) -> None:
    """Log an API error."""
    logger = get_logger()
    logger.error(f"API Error from {model}: {error}")


def log_event(event: str, **details) -> None:
    """Log a general event."""
    logger = get_logger()
    detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
    logger.info(f"{event}: {detail_str}" if detail_str else event)
