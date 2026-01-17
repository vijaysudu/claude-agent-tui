"""Data models for Claude Agent Visualizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class SessionStatus(Enum):
    """Status of a Claude Code session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(Enum):
    """Status of an agent."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_INPUT = "waiting_input"


class ToolCategory(Enum):
    """Category of a tool."""
    BUILTIN = "builtin"
    SKILL = "skill"
    MCP = "mcp"
    COMMAND = "command"


class ToolStatus(Enum):
    """Status of a tool use."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InputRequestType(Enum):
    """Type of input request."""
    QUESTION = "question"
    CONFIRMATION = "confirmation"
    SELECTION = "selection"


class InputRequestStatus(Enum):
    """Status of an input request."""
    PENDING = "pending"
    RESPONDED = "responded"
    EXPIRED = "expired"


@dataclass
class InputOption:
    """An option for selection-type input requests."""
    label: str
    value: str
    description: Optional[str] = None


@dataclass
class InputRequest:
    """A request for user input from an agent."""
    id: str
    agent_id: str
    session_id: str
    request_type: InputRequestType
    prompt: str
    status: InputRequestStatus
    created_at: datetime
    options: list[InputOption] = field(default_factory=list)
    response: Optional[str] = None
    responded_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if the request has expired."""
        if self.timeout_at is None:
            return False
        return datetime.now() > self.timeout_at


@dataclass
class ToolUse:
    """A tool use by an agent."""
    id: str
    agent_id: str
    tool_name: str
    tool_category: ToolCategory
    parameters: dict
    status: ToolStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result_preview: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for the tool."""
        if self.tool_category == ToolCategory.MCP:
            # mcp__github__get_file → GitHub: get_file
            parts = self.tool_name.split("__")
            if len(parts) >= 3:
                return f"{parts[1].title()}: {parts[2]}"
        elif self.tool_category == ToolCategory.SKILL:
            return f"/{self.tool_name}"
        return self.tool_name


@dataclass
class Agent:
    """An agent in a Claude Code session."""
    id: str
    session_id: str
    agent_type: str
    description: str
    status: AgentStatus
    started_at: datetime
    parent_id: Optional[str] = None
    ended_at: Optional[datetime] = None
    tokens_used: int = 0
    messages_count: int = 0
    tool_uses: list[ToolUse] = field(default_factory=list)
    input_requests: list[InputRequest] = field(default_factory=list)
    children: list[Agent] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        """Get the duration of the agent."""
        end = self.ended_at or datetime.now()
        return end - self.started_at

    @property
    def status_icon(self) -> str:
        """Get the status icon for display."""
        return {
            AgentStatus.RUNNING: "●",
            AgentStatus.COMPLETED: "○",
            AgentStatus.FAILED: "✗",
            AgentStatus.WAITING_INPUT: "◐",
        }[self.status]

    @property
    def status_color(self) -> str:
        """Get the status color for display."""
        return {
            AgentStatus.RUNNING: "yellow",
            AgentStatus.COMPLETED: "green",
            AgentStatus.FAILED: "red",
            AgentStatus.WAITING_INPUT: "blue",
        }[self.status]


@dataclass
class Session:
    """A Claude Code session."""
    id: str
    working_dir: str
    started_at: datetime
    status: SessionStatus
    pid: int
    ended_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    agents: list[Agent] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        """Get the duration of the session."""
        end = self.ended_at or datetime.now()
        return end - self.started_at

    @property
    def idle_time(self) -> Optional[timedelta]:
        """Get how long the session has been idle."""
        if self.last_activity and self.status == SessionStatus.ACTIVE:
            return datetime.now() - self.last_activity
        return None

    @property
    def is_idle(self) -> bool:
        """Check if the session is idle (no activity for 30+ seconds)."""
        idle = self.idle_time
        return idle is not None and idle.total_seconds() > 30

    @property
    def root_agent(self) -> Optional[Agent]:
        """Get the root agent (first agent with no parent)."""
        return next((a for a in self.agents if a.parent_id is None), None)

    @property
    def total_tokens(self) -> int:
        """Get total tokens used across all agents."""
        return sum(a.tokens_used for a in self.agents)

    @property
    def pending_inputs(self) -> list[InputRequest]:
        """Get all pending input requests."""
        return [
            req
            for agent in self.agents
            for req in agent.input_requests
            if req.status == InputRequestStatus.PENDING
        ]

    @property
    def active_agents(self) -> list[Agent]:
        """Get all currently running agents."""
        return [a for a in self.agents if a.status == AgentStatus.RUNNING]

    @property
    def waiting_agents(self) -> list[Agent]:
        """Get all agents waiting for input."""
        return [a for a in self.agents if a.status == AgentStatus.WAITING_INPUT]
