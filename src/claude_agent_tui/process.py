"""Process management for Claude sessions."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClaudeProcess:
    """Represents a running Claude process."""

    pid: int
    cwd: str
    command: str
    session_id: str | None = None


def find_claude_processes() -> list[ClaudeProcess]:
    """Find all running Claude processes.

    Returns:
        List of ClaudeProcess objects for running claude commands.
    """
    processes = []

    try:
        # Use ps to find claude processes
        # ps -eo pid,cwd,command gets PID, working directory, and full command
        result = subprocess.run(
            ["ps", "-eo", "pid,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return processes

        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue

            pid_str, command = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue

            # Check if this is a claude process
            if "claude" in command.lower() and "claude-tui" not in command.lower():
                # Try to get the working directory
                cwd = get_process_cwd(pid) or ""

                # Try to extract session ID from environment or cwd
                session_id = extract_session_id(pid, cwd)

                processes.append(ClaudeProcess(
                    pid=pid,
                    cwd=cwd,
                    command=command,
                    session_id=session_id,
                ))

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return processes


def get_process_cwd(pid: int) -> str | None:
    """Get the current working directory of a process.

    Args:
        pid: Process ID.

    Returns:
        Working directory path or None.
    """
    try:
        # On macOS, use lsof
        result = subprocess.run(
            ["lsof", "-p", str(pid), "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        for line in result.stdout.split("\n"):
            if line.startswith("n") and line.endswith("cwd"):
                # Next line should have the path
                continue
            if line.startswith("n/"):
                return line[1:]  # Remove 'n' prefix

        # Alternative: try /proc on Linux
        proc_cwd = Path(f"/proc/{pid}/cwd")
        if proc_cwd.exists():
            return str(proc_cwd.resolve())

    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    return None


def extract_session_id(pid: int, cwd: str) -> str | None:
    """Try to extract session ID for a Claude process.

    Args:
        pid: Process ID.
        cwd: Working directory.

    Returns:
        Session ID if found, None otherwise.
    """
    # Look for JSONL files being written in ~/.claude/projects
    claude_projects = Path.home() / ".claude" / "projects"

    if not claude_projects.exists():
        return None

    try:
        # Find recently modified JSONL files
        jsonl_files = list(claude_projects.glob("*/*.jsonl"))

        # Sort by modification time (most recent first)
        jsonl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Check if any recent file might belong to this process
        # by looking at the project path in the filename
        cwd_path = Path(cwd) if cwd else None

        for jsonl_file in jsonl_files[:10]:  # Check recent files
            # The parent directory name often contains project info
            project_dir = jsonl_file.parent.name

            # Simple heuristic: if cwd matches part of project dir
            if cwd_path and cwd_path.name in project_dir:
                return jsonl_file.stem

        # Return the most recent as fallback
        if jsonl_files:
            return jsonl_files[0].stem

    except (PermissionError, OSError):
        pass

    return None


def kill_process(pid: int, force: bool = False) -> bool:
    """Kill a process by PID.

    Args:
        pid: Process ID to kill.
        force: If True, use SIGKILL instead of SIGTERM.

    Returns:
        True if successful, False otherwise.
    """
    try:
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
        return True
    except (OSError, PermissionError):
        return False


def kill_session(session_id: str) -> tuple[bool, str]:
    """Kill a Claude session by session ID.

    Args:
        session_id: The session ID to kill.

    Returns:
        Tuple of (success, message).
    """
    processes = find_claude_processes()

    # Find matching process
    for proc in processes:
        if proc.session_id == session_id:
            if kill_process(proc.pid):
                return True, f"Killed process {proc.pid}"
            else:
                return False, f"Failed to kill process {proc.pid}"

    return False, f"No running process found for session {session_id}"


def kill_by_pid(pid: int, force: bool = False) -> tuple[bool, str]:
    """Kill a process by PID with confirmation.

    Args:
        pid: Process ID to kill.
        force: If True, use SIGKILL.

    Returns:
        Tuple of (success, message).
    """
    # Verify it's a claude process first
    processes = find_claude_processes()
    is_claude = any(p.pid == pid for p in processes)

    if not is_claude:
        return False, f"PID {pid} is not a Claude process"

    if kill_process(pid, force):
        return True, f"Killed process {pid}"
    else:
        return False, f"Failed to kill process {pid}"


def get_session_pid(session_path: Path) -> int | None:
    """Try to find the PID of a running session.

    Args:
        session_path: Path to the session JSONL file.

    Returns:
        PID if found, None otherwise.
    """
    session_id = session_path.stem
    processes = find_claude_processes()

    for proc in processes:
        if proc.session_id == session_id:
            return proc.pid

    return None


def is_session_running(session_path: Path) -> bool:
    """Check if a session is currently running.

    Args:
        session_path: Path to the session JSONL file.

    Returns:
        True if session appears to be running.
    """
    # Check if file was modified very recently (within last 30 seconds)
    try:
        import time
        mtime = session_path.stat().st_mtime
        age = time.time() - mtime
        if age < 30:
            return True
    except OSError:
        pass

    # Check for a corresponding process
    return get_session_pid(session_path) is not None
