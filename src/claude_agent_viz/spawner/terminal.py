"""Terminal spawner for Claude sessions."""

from __future__ import annotations

import os
import pty
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Tuple


@dataclass
class SpawnResult:
    """Result of spawning a Claude session."""

    success: bool
    pid: int | None = None
    error: str | None = None
    master_fd: int | None = None
    slave_fd: int | None = None


def get_available_terminals() -> list[str]:
    """Get list of available terminal emulators.

    Returns:
        List of available terminal command names.
    """
    terminals = [
        "wezterm",
        "kitty",
        "alacritty",
        "iterm2",
        "gnome-terminal",
        "konsole",
        "xterm",
        "Terminal.app",
    ]

    available = []
    for term in terminals:
        if shutil.which(term):
            available.append(term)

    # Check for macOS Terminal.app
    if sys.platform == "darwin" and os.path.exists("/System/Applications/Utilities/Terminal.app"):
        available.append("Terminal.app")

    return available


def spawn_session(cwd: str, terminal: str | None = None) -> SpawnResult:
    """Spawn a new Claude session in an external terminal.

    Args:
        cwd: Working directory for the session.
        terminal: Terminal emulator to use (auto-detect if None).

    Returns:
        SpawnResult indicating success or failure.
    """
    # Find claude executable
    claude_path = shutil.which("claude")
    if not claude_path:
        return SpawnResult(
            success=False,
            error="'claude' command not found in PATH",
        )

    # Auto-detect terminal if not specified
    if terminal is None:
        available = get_available_terminals()
        if not available:
            return SpawnResult(
                success=False,
                error="No supported terminal emulator found",
            )
        terminal = available[0]

    try:
        if terminal == "Terminal.app" or (sys.platform == "darwin" and terminal is None):
            # macOS Terminal.app
            script = f'tell application "Terminal" to do script "cd {cwd} && claude"'
            subprocess.Popen(["osascript", "-e", script])

        elif terminal == "iterm2":
            # iTerm2
            script = f'''
            tell application "iTerm"
                create window with default profile
                tell current session of current window
                    write text "cd {cwd} && claude"
                end tell
            end tell
            '''
            subprocess.Popen(["osascript", "-e", script])

        elif terminal == "wezterm":
            subprocess.Popen(
                ["wezterm", "start", "--cwd", cwd, "--", "claude"],
                start_new_session=True,
            )

        elif terminal == "kitty":
            subprocess.Popen(
                ["kitty", "--directory", cwd, "claude"],
                start_new_session=True,
            )

        elif terminal == "alacritty":
            subprocess.Popen(
                ["alacritty", "--working-directory", cwd, "-e", "claude"],
                start_new_session=True,
            )

        elif terminal == "gnome-terminal":
            subprocess.Popen(
                ["gnome-terminal", f"--working-directory={cwd}", "--", "claude"],
                start_new_session=True,
            )

        elif terminal == "konsole":
            subprocess.Popen(
                ["konsole", "--workdir", cwd, "-e", "claude"],
                start_new_session=True,
            )

        elif terminal == "xterm":
            subprocess.Popen(
                ["xterm", "-e", f"cd {cwd} && claude"],
                start_new_session=True,
            )

        else:
            return SpawnResult(
                success=False,
                error=f"Unsupported terminal: {terminal}",
            )

        return SpawnResult(success=True)

    except Exception as e:
        return SpawnResult(
            success=False,
            error=str(e),
        )


def spawn_embedded(cwd: str) -> SpawnResult:
    """Spawn a Claude session for embedded terminal use.

    This creates a PTY pair that can be used for an embedded terminal.

    Args:
        cwd: Working directory for the session.

    Returns:
        SpawnResult with PTY file descriptors.
    """
    # Find claude executable
    claude_path = shutil.which("claude")
    if not claude_path:
        return SpawnResult(
            success=False,
            error="'claude' command not found in PATH",
        )

    try:
        # Create pseudo-terminal
        master_fd, slave_fd = pty.openpty()

        # Fork the process
        pid = os.fork()

        if pid == 0:
            # Child process
            os.close(master_fd)
            os.setsid()

            # Set up slave as controlling terminal
            os.dup2(slave_fd, 0)  # stdin
            os.dup2(slave_fd, 1)  # stdout
            os.dup2(slave_fd, 2)  # stderr

            if slave_fd > 2:
                os.close(slave_fd)

            # Change to working directory
            os.chdir(cwd)

            # Set environment
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            # Execute claude
            os.execvpe(claude_path, [claude_path], env)

        else:
            # Parent process
            os.close(slave_fd)

            return SpawnResult(
                success=True,
                pid=pid,
                master_fd=master_fd,
            )

    except Exception as e:
        return SpawnResult(
            success=False,
            error=str(e),
        )
