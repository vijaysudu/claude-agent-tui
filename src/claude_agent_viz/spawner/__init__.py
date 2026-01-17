"""Spawner module for launching new Claude Code sessions.

Provides functionality to spawn new Claude Code sessions in terminal windows.
"""

from .terminal import (
    TerminalType,
    detect_terminal,
    get_available_terminals,
    spawn_session,
)

__all__ = [
    "TerminalType",
    "detect_terminal",
    "get_available_terminals",
    "spawn_session",
]
