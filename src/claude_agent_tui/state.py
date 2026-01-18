"""Application state management for Claude Agent Visualizer."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .discovery.parser import ParsedSession, ParsedToolUse, ParsedMessage, parse_session
from .discovery.config_parser import discover_all_configs, get_claude_dir
from .store.models import Session, ToolUse, ToolStatus, ConversationMessage, MessageRole
from .store.config_models import (
    Skill,
    Hook,
    Command,
    Agent,
    MCPServer,
    ConfigCollection,
)


def get_current_session_ids() -> dict[str, str]:
    """Get the current active session IDs from Claude's history.jsonl.

    Reads the most recent entries from ~/.claude/history.jsonl to determine
    which session is currently active for each project directory.

    Returns:
        Dict mapping project paths to their current session IDs.
    """
    history_path = Path.home() / ".claude" / "history.jsonl"
    project_sessions: dict[str, str] = {}

    if not history_path.exists():
        return project_sessions

    try:
        # Read last 100 lines (should be enough to find recent sessions)
        with open(history_path, "r", encoding="utf-8") as f:
            # Read all lines and get last 100
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines

        # Process in order - later entries override earlier ones
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                project = entry.get("project")
                session_id = entry.get("sessionId")
                if project and session_id:
                    # Normalize project path
                    project = str(Path(project).resolve())
                    project_sessions[project] = session_id
            except json.JSONDecodeError:
                continue

    except (OSError, IOError):
        pass

    return project_sessions


def get_active_claude_processes() -> dict[str, list[int]]:
    """Get working directories and PIDs of all running Claude processes.

    Uses pgrep to find Claude processes and lsof to get their working directories.

    Returns:
        Dict mapping directory paths to list of Claude process PIDs in that directory.
    """
    active_processes: dict[str, list[int]] = {}

    try:
        # Use pgrep to find Claude process PIDs
        result = subprocess.run(
            ["pgrep", "-f", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return active_processes

        pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]

        for pid in pids:
            # Filter out non-claude processes (grep, python, claude-tui, etc.)
            try:
                ps_result = subprocess.run(
                    ["ps", "-p", pid, "-o", "args="],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                cmd = ps_result.stdout.strip()
                # Only match actual claude command, not claude-tui or scripts
                if not cmd or 'claude-tui' in cmd or 'python' in cmd or 'grep' in cmd:
                    continue
                if not (cmd == 'claude' or cmd.startswith('claude ') or '/claude' in cmd):
                    continue
            except subprocess.SubprocessError:
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
                        parts = line.split()
                        if len(parts) >= 9:
                            cwd_path = parts[-1]
                            if cwd_path not in active_processes:
                                active_processes[cwd_path] = []
                            active_processes[cwd_path].append(int(pid))
                        break
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
                continue

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    return active_processes


def get_active_claude_directories() -> set[str]:
    """Get working directories of all running Claude processes.

    Returns:
        Set of absolute paths where Claude instances are running.
    """
    return set(get_active_claude_processes().keys())


@dataclass
class AppState:
    """Global application state."""

    sessions: list[Session] = field(default_factory=list)
    selected_session_id: str | None = None
    selected_tool_id: str | None = None
    spawn_mode: str = "external"  # "external" or "embedded" (embedded requires compatible textual-terminal)
    show_active_only: bool = True  # Filter to show only active sessions

    # Config items
    skills: list[Skill] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    agents: list[Agent] = field(default_factory=list)
    mcp_servers: list[MCPServer] = field(default_factory=list)

    # Config selection state
    selected_config_type: str | None = None
    selected_config_id: str | None = None

    # Track spawned process PIDs for cleanup
    _spawned_pids: list[int] = field(default_factory=list)

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

    def load_configs(self, claude_dir: Path | None = None) -> None:
        """Load all configuration items from Claude's config directory.

        Args:
            claude_dir: Path to Claude config directory (defaults to ~/.claude).
        """
        if claude_dir is None:
            claude_dir = get_claude_dir()

        configs = discover_all_configs(claude_dir)
        self.skills = configs.skills
        self.hooks = configs.hooks
        self.commands = configs.commands
        self.agents = configs.agents
        self.mcp_servers = configs.mcp_servers
        self.notify_update()

    def select_config_item(self, item_type: str, item_id: str) -> None:
        """Select a config item by type and ID.

        Args:
            item_type: The type of config item (skill, hook, command, agent, mcp_server).
            item_id: The unique ID of the item.
        """
        self.selected_config_type = item_type
        self.selected_config_id = item_id
        # Clear session/tool selection when selecting config
        self.selected_session_id = None
        self.selected_tool_id = None
        self.notify_update()

    def clear_config_selection(self) -> None:
        """Clear the current config selection."""
        self.selected_config_type = None
        self.selected_config_id = None
        self.notify_update()

    def get_selected_config(self) -> Skill | Hook | Command | Agent | MCPServer | None:
        """Get the currently selected config item.

        Returns:
            The selected config item or None if nothing is selected.
        """
        if not self.selected_config_type or not self.selected_config_id:
            return None

        items_map = {
            "skill": self.skills,
            "hook": self.hooks,
            "command": self.commands,
            "agent": self.agents,
            "mcp_server": self.mcp_servers,
        }

        items = items_map.get(self.selected_config_type)
        if not items:
            return None

        # Find by ID based on type
        for item in items:
            if self._get_config_item_id(self.selected_config_type, item) == self.selected_config_id:
                return item

        return None

    def _get_config_item_id(
        self, item_type: str, item: Skill | Hook | Command | Agent | MCPServer
    ) -> str:
        """Get the unique ID for a config item.

        Args:
            item_type: The type of config item.
            item: The config item.

        Returns:
            Unique string ID.
        """
        if item_type == "skill" and isinstance(item, Skill):
            if item.is_from_plugin and item.plugin_name:
                return f"{item.plugin_name}:{item.name}"
            return item.name
        elif item_type == "hook" and isinstance(item, Hook):
            if item.matcher:
                return f"{item.hook_type}:{item.matcher}"
            return f"{item.hook_type}:{hash(item.command) % 10000}"
        elif item_type == "command" and isinstance(item, Command):
            return item.name
        elif item_type == "agent" and isinstance(item, Agent):
            if item.is_from_plugin and item.plugin_name:
                return f"{item.plugin_name}:{item.name}"
            return item.name
        elif item_type == "mcp_server" and isinstance(item, MCPServer):
            return item.name
        return str(id(item))

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

    def track_spawned_pid(self, pid: int) -> None:
        """Track a spawned process PID for cleanup.

        Args:
            pid: Process ID to track.
        """
        if pid not in self._spawned_pids:
            self._spawned_pids.append(pid)

    def untrack_spawned_pid(self, pid: int) -> None:
        """Remove a PID from tracking (e.g., when process exits normally).

        Args:
            pid: Process ID to untrack.
        """
        if pid in self._spawned_pids:
            self._spawned_pids.remove(pid)

    def cleanup_spawned_processes(self) -> list[tuple[int, bool]]:
        """Kill all tracked spawned processes.

        Called when the app exits to prevent orphaned processes.

        Returns:
            List of (pid, success) tuples indicating cleanup results.
        """
        import os
        import signal

        results = []
        for pid in self._spawned_pids[:]:  # Copy list to avoid modification during iteration
            try:
                # Check if process is still running
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                # Process exists, send SIGTERM
                os.kill(pid, signal.SIGTERM)
                results.append((pid, True))
            except OSError:
                # Process doesn't exist or we can't signal it
                results.append((pid, False))
            finally:
                self._spawned_pids.remove(pid)

        return results


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
    messages = [convert_parsed_message(m) for m in parsed.messages]

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
        messages=messages,
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


def convert_parsed_message(parsed: ParsedMessage) -> ConversationMessage:
    """Convert a ParsedMessage to a ConversationMessage model."""
    role = MessageRole.USER if parsed.role == "user" else MessageRole.ASSISTANT

    return ConversationMessage(
        uuid=parsed.uuid,
        role=role,
        timestamp=parsed.timestamp,
        text_content=parsed.text_content,
        thinking_content=parsed.thinking_content,
        tool_use_ids=parsed.tool_use_ids,
        is_tool_result=parsed.is_tool_result,
        raw_content=parsed.raw_content,
    )
