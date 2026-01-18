"""Data models for Claude configuration items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    """Represents a Claude skill configuration."""

    name: str
    description: str
    file_path: Path
    content: str
    is_from_plugin: bool = False
    plugin_name: str | None = None

    @property
    def display_name(self) -> str:
        """Get display-friendly name."""
        if self.is_from_plugin and self.plugin_name:
            return f"{self.plugin_name}:{self.name}"
        return self.name


@dataclass
class Hook:
    """Represents a Claude hook configuration."""

    hook_type: str  # UserPromptSubmit, PostToolUse, PreToolUse, Notification, Stop
    command: str
    matcher: str | None = None
    timeout: int | None = None

    @property
    def display_name(self) -> str:
        """Get display-friendly name."""
        if self.matcher:
            return f"{self.hook_type}: {self.matcher}"
        return self.hook_type


@dataclass
class Command:
    """Represents a Claude custom command."""

    name: str
    description: str
    file_path: Path
    content: str

    @property
    def display_name(self) -> str:
        """Get display-friendly name."""
        return f"/{self.name}"


@dataclass
class Agent:
    """Represents a Claude agent configuration."""

    name: str
    description: str
    tools: list[str]
    model: str
    file_path: Path
    content: str
    is_from_plugin: bool = False
    plugin_name: str | None = None
    color: str | None = None

    @property
    def display_name(self) -> str:
        """Get display-friendly name."""
        if self.is_from_plugin and self.plugin_name:
            return f"{self.plugin_name}:{self.name}"
        return self.name


@dataclass
class MCPServer:
    """Represents an MCP server configuration."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None

    @property
    def display_name(self) -> str:
        """Get display-friendly name."""
        return self.name

    @property
    def full_command(self) -> str:
        """Get the full command with args."""
        parts = [self.command] + self.args
        return " ".join(parts)


@dataclass
class ConfigCollection:
    """Collection of all configuration items."""

    skills: list[Skill] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    agents: list[Agent] = field(default_factory=list)
    mcp_servers: list[MCPServer] = field(default_factory=list)
