"""Terminal detection and launching for spawning Claude Code sessions.

Supports macOS Terminal.app, iTerm2, and tmux.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from enum import Enum
from pathlib import Path

from ..logging import get_logger

log = get_logger("spawner")


class TerminalType(Enum):
    """Supported terminal types."""

    ITERM2 = "iterm2"
    TERMINAL_APP = "terminal"
    TMUX = "tmux"
    UNKNOWN = "unknown"


def detect_terminal() -> TerminalType:
    """Detect the best available terminal to use.

    Prefers iTerm2 > tmux > Terminal.app on macOS.

    Returns:
        The detected terminal type
    """
    # Check if running inside tmux
    if os.environ.get("TMUX"):
        return TerminalType.TMUX

    # Check for iTerm2 (macOS)
    if _is_iterm2_available():
        return TerminalType.ITERM2

    # Check for Terminal.app (macOS)
    if _is_terminal_app_available():
        return TerminalType.TERMINAL_APP

    return TerminalType.UNKNOWN


def get_available_terminals() -> list[TerminalType]:
    """Get list of available terminal types.

    Returns:
        List of available terminal types
    """
    available = []

    if os.environ.get("TMUX"):
        available.append(TerminalType.TMUX)

    if _is_iterm2_available():
        available.append(TerminalType.ITERM2)

    if _is_terminal_app_available():
        available.append(TerminalType.TERMINAL_APP)

    return available


def _is_iterm2_available() -> bool:
    """Check if iTerm2 is available."""
    return Path("/Applications/iTerm.app").exists()


def _is_terminal_app_available() -> bool:
    """Check if Terminal.app is available."""
    # Terminal.app can be in different locations depending on macOS version
    paths = [
        "/System/Applications/Utilities/Terminal.app",
        "/Applications/Utilities/Terminal.app",
    ]
    return any(Path(p).exists() for p in paths)


def spawn_session(
    cwd: str,
    terminal: TerminalType | None = None,
) -> bool:
    """Spawn a new Claude Code session in a terminal window.

    Args:
        cwd: Working directory for the new session
        terminal: Terminal type to use. If None, auto-detect.

    Returns:
        True if successfully spawned, False otherwise
    """
    if terminal is None:
        terminal = detect_terminal()

    # Validate cwd
    if not Path(cwd).is_dir():
        log.error(f"Invalid working directory: {cwd}")
        return False

    # Check that claude command is available
    if not shutil.which("claude"):
        log.error("Claude command not found in PATH")
        return False

    log.info(f"Spawning session in {cwd} using {terminal.value}")

    try:
        if terminal == TerminalType.ITERM2:
            return _spawn_iterm2(cwd)
        elif terminal == TerminalType.TERMINAL_APP:
            return _spawn_terminal_app(cwd)
        elif terminal == TerminalType.TMUX:
            return _spawn_tmux(cwd)
        else:
            log.error(f"Unsupported terminal type: {terminal}")
            return False
    except Exception as e:
        log.error(f"Failed to spawn session: {e}")
        return False


def _spawn_iterm2(cwd: str) -> bool:
    """Spawn a new session in iTerm2."""
    # AppleScript to open new tab in iTerm2
    script = f'''
    tell application "iTerm2"
        activate
        tell current window
            create tab with default profile
            tell current session
                write text "cd {_escape_applescript(cwd)} && claude"
            end tell
        end tell
    end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        log.error(f"iTerm2 AppleScript failed: {result.stderr}")
        return False

    return True


def _spawn_terminal_app(cwd: str) -> bool:
    """Spawn a new session in Terminal.app."""
    # AppleScript to open new window in Terminal.app
    script = f'''
    tell application "Terminal"
        activate
        do script "cd {_escape_applescript(cwd)} && claude"
    end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        log.error(f"Terminal.app AppleScript failed: {result.stderr}")
        return False

    return True


def _spawn_tmux(cwd: str) -> bool:
    """Spawn a new session in tmux.

    Creates a new window in the current tmux session.
    """
    # Create new tmux window
    result = subprocess.run(
        [
            "tmux",
            "new-window",
            "-c",
            cwd,
            "-n",
            f"claude-{Path(cwd).name[:10]}",
            "claude",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        log.error(f"tmux new-window failed: {result.stderr}")
        return False

    return True


def _escape_applescript(s: str) -> str:
    """Escape a string for use in AppleScript."""
    # Escape backslashes and double quotes
    return s.replace("\\", "\\\\").replace('"', '\\"')
