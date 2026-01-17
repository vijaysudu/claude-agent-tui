"""Logging configuration for Claude Agent Visualizer."""

import logging
import sys
from pathlib import Path

# Log file location
LOG_DIR = Path.home() / ".cache" / "claude-agent-viz"
LOG_FILE = LOG_DIR / "viz.log"

# Create logger
logger = logging.getLogger("claude-agent-viz")


def setup_logging(verbose: bool = False, log_to_file: bool = True) -> None:
    """Configure logging for the application.

    Args:
        verbose: If True, log DEBUG level to console
        log_to_file: If True, also log to file
    """
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler - only warnings and errors (to not interfere with TUI)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING if not verbose else logging.DEBUG)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler - all logs
    if log_to_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    logger.debug("Logging initialized")


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Optional name for the logger (will be prefixed with app name)

    Returns:
        A logger instance
    """
    if name:
        return logging.getLogger(f"claude-agent-viz.{name}")
    return logger
