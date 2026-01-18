"""Application state management for Claude Agent Visualizer."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .discovery.parser import ParsedSession, ParsedToolUse, parse_session
from .store.models import Session, ToolUse, ToolStatus


def get_active_claude_directories() -> set[str]:
    """Get working directories of all running Claude processes.

    Returns:
        Set of absolute paths where Claude instances are running.
    """
    active_dirs: set[str] = set()

    try:
        # Use ps to find Claude processes - more reliable than pgrep
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return active_dirs

        # Find PIDs of processes with "claude" command (not grep or other matches)
        pids = []
        for line in result.stdout.split('\n'):
            # Match lines where the command is "claude" (not grep, python, etc.)
            if ' claude ' in line or line.endswith(' claude') or 'claude --' in line:
                # Skip grep, python, and other non-claude processes
                if 'grep' in line or 'python' in line or 'claude-viz' in line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    pids.append(parts[1])  # PID is second column

        for pid in pids:
            if not pid:
                continue

            # Get working directory using lsof
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-p", pid],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                for line in lsof_result.stdout.split('\n'):
                    if ' cwd ' in line:
                        # Parse the cwd line to get the directory path
                        # Format: name pid user FD type ... path
                        parts = line.split()
                        if len(parts) >= 9:
                            # Path is the last part
                            cwd_path = parts[-1]
                            active_dirs.add(cwd_path)
                        break
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                continue

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    return active_dirs


@dataclass
class AppState:
    """Global application state."""

    sessions: list[Session] = field(default_factory=list)
    selected_session_id: str | None = None
    selected_tool_id: str | None = None
    spawn_mode: str = "external"  # "external" or "embedded"
    show_active_only: bool = True  # Filter to show only active sessions

    # Callbacks for state changes
    _on_session_update: list[Callable[[], None]] = field(default_factory=list)

    def add_update_listener(self, callback: Callable[[], None]) -> None:
        """Add a callback to be called when state updates."""
        self._on_session_update.append(callback)

    def notify_update(self) -> None:
        """Notify all listeners of a state update."""
        for callback in self._on_session_update:
            callback()

    @property
    def selected_session(self) -> Session | None:
        """Get the currently selected session."""
        if not self.selected_session_id:
            return None
        for session in self.sessions:
            if session.session_id == self.selected_session_id:
                return session
        return None

    @property
    def selected_tool(self) -> ToolUse | None:
        """Get the currently selected tool."""
        session = self.selected_session
        if not session or not self.selected_tool_id:
            return None
        return session.get_tool_by_id(self.selected_tool_id)

    def select_session(self, session_id: str | None) -> None:
        """Select a session by ID."""
        self.selected_session_id = session_id
        self.selected_tool_id = None
        self.notify_update()

    def select_tool(self, tool_id: str | None) -> None:
        """Select a tool by ID."""
        self.selected_tool_id = tool_id
        self.notify_update()

    def toggle_spawn_mode(self) -> str:
        """Toggle between embedded and external spawn modes."""
        self.spawn_mode = "embedded" if self.spawn_mode == "external" else "external"
        self.notify_update()
        return self.spawn_mode

    def toggle_active_filter(self) -> bool:
        """Toggle between showing all sessions and active only."""
        self.show_active_only = not self.show_active_only
        self.notify_update()
        return self.show_active_only

    @property
    def filtered_sessions(self) -> list[Session]:
        """Get sessions filtered by active status if filter is enabled."""
        if not self.show_active_only:
            return self.sessions
        return [s for s in self.sessions if s.is_active]

    def load_session(
        self,
        jsonl_path: Path,
        active_directories: set[str] | None = None,
    ) -> Session:
        """Load a session from a JSONL file.

        Args:
            jsonl_path: Path to the session JSONL file.
            active_directories: Optional set of directories with running Claude processes.
                If None, will be fetched automatically.
        """
        parsed = parse_session(jsonl_path)
        session = convert_parsed_session(parsed, active_directories)

        # Check if session already exists
        for i, existing in enumerate(self.sessions):
            if existing.session_id == session.session_id:
                self.sessions[i] = session
                self.notify_update()
                return session

        self.sessions.insert(0, session)
        self.notify_update()
        return session

    def update_session(self, jsonl_path: Path) -> Session:
        """Update a session from a JSONL file."""
        return self.load_session(jsonl_path)


def convert_parsed_session(
    parsed: ParsedSession,
    active_directories: set[str] | None = None,
) -> Session:
    """Convert a ParsedSession to a Session model.

    Args:
        parsed: The parsed session data.
        active_directories: Set of directories with running Claude processes.
            If None, will be fetched automatically.
    """
    tool_uses = [convert_parsed_tool_use(t) for t in parsed.tool_uses]

    # Detect if session is active based on running Claude process
    # A session is active if there's a Claude instance running in its project directory
    is_active = False
    if parsed.project_path:
        if active_directories is None:
            active_directories = get_active_claude_directories()

        # Check if project path matches any active directory exactly
        project_path = str(Path(parsed.project_path).resolve())
        for active_dir in active_directories:
            try:
                active_resolved = str(Path(active_dir).resolve())
                # Only exact path matches - a session is only active if Claude
                # is running in exactly that directory, not a subdirectory
                if project_path == active_resolved:
                    is_active = True
                    break
            except (OSError, ValueError):
                continue

    return Session(
        session_id=parsed.session_id,
        session_path=parsed.session_path,
        tool_uses=tool_uses,
        message_count=parsed.message_count,
        start_time=parsed.start_time,
        summary=parsed.summary,
        project_path=parsed.project_path,
        is_active=is_active,
    )


def convert_parsed_tool_use(parsed: ParsedToolUse) -> ToolUse:
    """Convert a ParsedToolUse to a ToolUse model."""
    status = ToolStatus.ERROR if parsed.is_error else ToolStatus.COMPLETED

    return ToolUse(
        tool_use_id=parsed.tool_use_id,
        tool_name=parsed.tool_name,
        input_params=parsed.input_params,
        status=status,
        preview=parsed.preview,
        timestamp=parsed.timestamp,
        result_content=parsed.result_content,
        error_message=parsed.error_message,
    )
