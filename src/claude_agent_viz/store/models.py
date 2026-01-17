"""Data models for Claude agent visualization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ToolStatus(Enum):
    """Status of a tool execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ToolUse:
    """Represents a single tool use in a session."""

    tool_use_id: str
    tool_name: str
    input_params: dict[str, Any]
    status: ToolStatus = ToolStatus.COMPLETED
    preview: str = ""
    duration_ms: int | None = None
    timestamp: str | None = None

    # Result content - populated from tool_result
    result_content: str | None = None
    error_message: str | None = None

    def get_file_path(self) -> str | None:
        """Get the file path if this tool operates on a file."""
        if self.tool_name in ("Read", "Edit", "Write"):
            return self.input_params.get("file_path")
        elif self.tool_name == "Grep":
            return self.input_params.get("path")
        elif self.tool_name == "Glob":
            return self.input_params.get("path")
        return None

    def get_display_name(self) -> str:
        """Get a display-friendly name for this tool use."""
        if self.tool_name == "Read":
            path = self.input_params.get("file_path", "")
            return f"Read: {Path(path).name if path else 'file'}"
        elif self.tool_name == "Edit":
            path = self.input_params.get("file_path", "")
            return f"Edit: {Path(path).name if path else 'file'}"
        elif self.tool_name == "Write":
            path = self.input_params.get("file_path", "")
            return f"Write: {Path(path).name if path else 'file'}"
        elif self.tool_name == "Bash":
            cmd = self.input_params.get("command", "")
            parts = cmd.split() if cmd else []
            short_cmd = parts[0] if parts else "command"
            return f"Bash: {short_cmd}"
        elif self.tool_name == "Grep":
            pattern = self.input_params.get("pattern", "")[:20]
            return f"Grep: {pattern}"
        elif self.tool_name == "Glob":
            pattern = self.input_params.get("pattern", "")[:20]
            return f"Glob: {pattern}"
        elif self.tool_name == "Task":
            desc = self.input_params.get("description", "")[:20]
            return f"Task: {desc}"
        return self.tool_name


@dataclass
class Session:
    """Represents a Claude session."""

    session_id: str
    session_path: Path
    tool_uses: list[ToolUse] = field(default_factory=list)
    message_count: int = 0
    start_time: str | None = None
    is_active: bool = False
    pid: int | None = None  # Process ID if session is running
    summary: str | None = None  # First user message or task description
    project_path: str | None = None  # Working directory / project path

    @property
    def tool_count(self) -> int:
        """Return the number of tool uses."""
        return len(self.tool_uses)

    @property
    def display_name(self) -> str:
        """Get a display-friendly name for the session."""
        # Use first part of session ID
        return self.session_id[:8] if len(self.session_id) > 8 else self.session_id

    @property
    def display_summary(self) -> str:
        """Get a display-friendly summary."""
        if self.summary:
            summary = self.summary.strip().replace("\n", " ").replace("\r", "")
            if len(summary) > 60:
                return summary[:57] + "..."
            return summary
        return "No summary available"

    @property
    def project_name(self) -> str:
        """Get the project name from the path."""
        if self.project_path:
            return Path(self.project_path).name
        return "unknown"

    def get_tool_by_id(self, tool_use_id: str) -> ToolUse | None:
        """Get a tool use by its ID."""
        for tool in self.tool_uses:
            if tool.tool_use_id == tool_use_id:
                return tool
        return None
