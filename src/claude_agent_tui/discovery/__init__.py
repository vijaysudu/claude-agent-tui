"""Session discovery and parsing utilities."""

from .parser import parse_session, ParsedToolUse, ParsedSession

__all__ = ["parse_session", "ParsedToolUse", "ParsedSession"]

# Optional import for watcher (requires watchdog)
try:
    from .watcher import SessionWatcher
    __all__.append("SessionWatcher")
except ImportError:
    SessionWatcher = None  # type: ignore
