"""Scanner for discovering Claude Code sessions.

Scans ~/.claude/projects/ for session JSONL files and detects active processes.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..logging import get_logger

log = get_logger("scanner")

# Claude projects directory
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def get_claude_projects_dir() -> Path:
    """Get the Claude projects directory path."""
    return CLAUDE_PROJECTS_DIR


@dataclass
class SessionInfo:
    """Basic session info from file scan."""

    session_id: str
    cwd: str
    file_path: Path
    last_modified: datetime
    file_size: int
    encoded_cwd: str  # The encoded directory name like -Users-vijay-git


def decode_cwd(encoded: str) -> str:
    """Decode a Claude-encoded working directory path.

    Claude encodes paths with this pattern:
    - '/' is encoded as '-'
    - '.' is encoded as '--'
    - Path is prefixed with '-'

    Note: This is a best-effort decode. For accurate cwd, parse the JSONL file.

    Example: -Users-vijay--sudharshan-git -> /Users/vijay.sudharshan/git
    Example: -Users-vijay--sudharshan--claude -> /Users/vijay.sudharshan/.claude
    """
    if not encoded.startswith("-"):
        return encoded

    # First, replace '--' with a placeholder (for dots)
    # Then replace '-' with '/' (for path separators)
    # Then replace placeholder back with '.'
    placeholder = "\x00"  # Null byte as placeholder
    result = encoded[1:]  # Remove leading '-'
    result = result.replace("--", placeholder)
    result = result.replace("-", "/")
    result = result.replace(placeholder, ".")

    return "/" + result


def _extract_cwd_from_file(file_path: Path) -> str | None:
    """Extract the cwd from a session JSONL file.

    Reads the first few lines to find the cwd field, which is more accurate
    than trying to decode the directory name.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 20:  # Only check first 20 lines
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if "cwd" in entry:
                        return entry["cwd"]
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return None


def scan_sessions(projects_dir: Path | None = None) -> list[SessionInfo]:
    """Scan for all session files in the Claude projects directory.

    Args:
        projects_dir: Optional custom projects directory. Defaults to ~/.claude/projects/

    Returns:
        List of SessionInfo objects sorted by last_modified (newest first)
    """
    if projects_dir is None:
        projects_dir = CLAUDE_PROJECTS_DIR

    if not projects_dir.exists():
        log.warning(f"Claude projects directory not found: {projects_dir}")
        return []

    sessions = []

    # Iterate through project directories
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        encoded_cwd = project_dir.name

        # Find all JSONL session files in this project
        for session_file in project_dir.glob("*.jsonl"):
            try:
                stat = session_file.stat()
                session_id = session_file.stem  # UUID without .jsonl

                # Extract actual cwd from file (more accurate than decoding dir name)
                cwd = _extract_cwd_from_file(session_file) or decode_cwd(encoded_cwd)

                sessions.append(
                    SessionInfo(
                        session_id=session_id,
                        cwd=cwd,
                        file_path=session_file,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        file_size=stat.st_size,
                        encoded_cwd=encoded_cwd,
                    )
                )
            except OSError as e:
                log.debug(f"Failed to stat session file {session_file}: {e}")

    # Sort by last_modified (newest first)
    sessions.sort(key=lambda s: s.last_modified, reverse=True)

    log.info(f"Found {len(sessions)} session files")
    return sessions


def get_active_processes() -> dict[str, list[int]]:
    """Get running Claude Code processes and their working directories.

    Uses `ps` to find processes with exact command name 'claude',
    then `lsof` to determine each process's working directory.

    Returns:
        Dict mapping working directory to list of process IDs.
        Multiple Claude instances in the same directory will all be tracked.
    """
    active: dict[str, list[int]] = {}

    try:
        # Find claude processes using ps (more reliable than pgrep)
        # ps -eo pid,comm outputs: "  PID COMM"
        result = subprocess.run(
            ["ps", "-eo", "pid,comm"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return active

        # Parse ps output to find Claude processes
        pids = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "claude":
                try:
                    pids.append(int(parts[0]))
                except ValueError:
                    continue

        log.debug(f"Found {len(pids)} claude processes: {pids}")

        for pid in pids:
            try:
                # Get working directory using lsof -a -d cwd
                # -a means AND conditions, -d cwd filters to just cwd entries
                lsof_result = subprocess.run(
                    ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if lsof_result.returncode == 0:
                    # Parse lsof output for cwd path
                    # Output format: "p<pid>\nn<path>"
                    for line in lsof_result.stdout.split("\n"):
                        if line.startswith("n/"):
                            cwd = line[1:]  # Remove 'n' prefix
                            if os.path.isdir(cwd):
                                if cwd not in active:
                                    active[cwd] = []
                                active[cwd].append(pid)
                                log.debug(f"Claude process {pid} in cwd: {cwd}")
                                break
            except (subprocess.TimeoutExpired, ValueError) as e:
                log.debug(f"Failed to get cwd for pid {pid}: {e}")
                continue

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.debug(f"Failed to get active processes: {e}")

    return active


def is_session_active(
    session_info: SessionInfo,
    active_processes: dict[str, int] | None = None,
    activity_timeout_seconds: int = 60,
) -> bool:
    """Determine if a session is active.

    A session is considered active if:
    1. Its JSONL file was modified within the timeout period, OR
    2. A claude process is running with that working directory

    Args:
        session_info: Session to check
        active_processes: Dict of cwd -> pid. If None, will be fetched.
        activity_timeout_seconds: Seconds of inactivity before session is considered inactive

    Returns:
        True if session is active
    """
    # Check recent file modification
    age = datetime.now() - session_info.last_modified
    if age.total_seconds() < activity_timeout_seconds:
        return True

    # Check for running process
    if active_processes is None:
        active_processes = get_active_processes()

    return session_info.cwd in active_processes


def scan_recent_sessions(
    max_age_hours: int = 24,
    projects_dir: Path | None = None,
) -> list[SessionInfo]:
    """Scan for recent session files only.

    Args:
        max_age_hours: Only include sessions modified within this many hours
        projects_dir: Optional custom projects directory

    Returns:
        List of recent SessionInfo objects
    """
    all_sessions = scan_sessions(projects_dir)
    cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

    return [s for s in all_sessions if s.last_modified.timestamp() > cutoff]
