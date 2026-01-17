"""In-memory state store for Claude Agent Visualizer.

This module provides a reactive state store that holds all session and agent
data in memory. The state is populated by scanning and parsing Claude Code's
session JSONL files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from .discovery import (
    ParsedSession,
    SessionInfo,
    get_active_processes,
    parse_session,
    scan_sessions,
)
from .store.models import (
    Agent,
    AgentStatus,
    InputRequest,
    InputRequestStatus,
    Session,
    SessionStatus,
    ToolCategory,
    ToolStatus,
    ToolUse,
)


@dataclass
class AppState:
    """Application state container.

    Holds all sessions and provides methods to update state from file scans.
    Observers are notified when state changes.
    """

    sessions: dict[str, Session] = field(default_factory=dict)
    _observers: list[Callable[[], None]] = field(default_factory=list, repr=False)
    _file_offsets: dict[str, int] = field(default_factory=dict, repr=False)
    _active_processes: dict[str, int] = field(default_factory=dict, repr=False)

    def add_observer(self, callback: Callable[[], None]) -> None:
        """Add an observer that will be called when state changes."""
        self._observers.append(callback)

    def remove_observer(self, callback: Callable[[], None]) -> None:
        """Remove an observer."""
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self) -> None:
        """Notify all observers of a state change."""
        for callback in self._observers:
            try:
                callback()
            except Exception:
                pass

    # --- File-based Session Discovery ---

    def refresh_from_files(
        self,
        max_sessions: int = 50,
        max_age_hours: int = 24,
    ) -> int:
        """Refresh state by scanning and parsing session files.

        Args:
            max_sessions: Maximum number of sessions to load
            max_age_hours: Only load sessions modified within this many hours

        Returns:
            Number of sessions loaded/updated
        """
        # Get active claude processes for activity detection
        self._active_processes = get_active_processes()

        # Scan for session files
        all_sessions = scan_sessions()

        # Filter by age
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        recent_sessions = [s for s in all_sessions if s.last_modified > cutoff]

        # Limit number of sessions
        sessions_to_load = recent_sessions[:max_sessions]

        updated_count = 0
        for session_info in sessions_to_load:
            if self._load_session(session_info):
                updated_count += 1

        self._notify_observers()
        return updated_count

    def _load_session(self, session_info: SessionInfo) -> bool:
        """Load or update a single session from its file.

        Returns True if the session was updated.
        """
        parsed = parse_session(session_info.file_path)
        if not parsed:
            return False

        # Determine if session is active
        is_active = self._is_session_active(session_info)

        # Check if we already have this session
        if session_info.session_id in self.sessions:
            existing = self.sessions[session_info.session_id]
            # Update existing session
            existing.last_activity = parsed.last_activity
            if is_active:
                existing.status = SessionStatus.ACTIVE
            elif existing.status == SessionStatus.ACTIVE:
                # Mark as completed if no longer active
                existing.status = SessionStatus.COMPLETED
            self._update_session_tools(existing, parsed)
            return True

        # Create new session
        session = Session(
            id=parsed.session_id,
            working_dir=parsed.cwd,
            started_at=parsed.started_at,
            status=SessionStatus.ACTIVE if is_active else SessionStatus.COMPLETED,
            pid=0,
            last_activity=parsed.last_activity,
        )

        # Create default agent for the session
        agent = Agent(
            id=f"{parsed.session_id}-main",
            session_id=parsed.session_id,
            agent_type="Claude",
            description=parsed.summary or parsed.slug,
            status=AgentStatus.RUNNING if is_active else AgentStatus.COMPLETED,
            started_at=parsed.started_at,
            messages_count=parsed.message_count,
        )

        # Add tool uses from parsed session
        for tool in parsed.tool_uses[-20:]:  # Keep last 20 tools
            agent.tool_uses.append(
                ToolUse(
                    id=tool.tool_id,
                    agent_id=agent.id,
                    tool_name=tool.tool_name,
                    tool_category=tool.tool_category,
                    parameters=tool.parameters,
                    status=tool.status,
                    started_at=tool.started_at,
                )
            )

        session.agents.append(agent)
        self.sessions[parsed.session_id] = session
        return True

    def _update_session_tools(self, session: Session, parsed: ParsedSession) -> None:
        """Update session's agent tools from parsed data."""
        if not session.agents:
            return

        agent = session.agents[0]  # Main agent
        agent.messages_count = parsed.message_count

        # Get existing tool IDs
        existing_tool_ids = {t.id for t in agent.tool_uses}

        # Add new tools
        for tool in parsed.tool_uses[-20:]:
            if tool.tool_id not in existing_tool_ids:
                agent.tool_uses.append(
                    ToolUse(
                        id=tool.tool_id,
                        agent_id=agent.id,
                        tool_name=tool.tool_name,
                        tool_category=tool.tool_category,
                        parameters=tool.parameters,
                        status=tool.status,
                        started_at=tool.started_at,
                    )
                )

        # Trim to last 20 tools
        if len(agent.tool_uses) > 20:
            agent.tool_uses = agent.tool_uses[-20:]

    def _is_session_active(self, session_info: SessionInfo) -> bool:
        """Determine if a session is active based on file modification and processes."""
        # Check recent file modification
        age = datetime.now() - session_info.last_modified
        if age.total_seconds() < ACTIVITY_TIMEOUT_SECONDS:
            return True

        # Check for running process in that directory
        return session_info.cwd in self._active_processes

    def update_session(self, session_info: SessionInfo) -> None:
        """Update a single session from file change notification.

        Called by the watcher when a session file changes.
        """
        if self._load_session(session_info):
            self._notify_observers()

    # --- Session Operations ---

    def get_or_create_session(
        self,
        session_id: str,
        working_dir: str = "",
        pid: int = 0,
    ) -> Session:
        """Get existing session or create a new one."""
        if session_id not in self.sessions:
            now = datetime.now()
            self.sessions[session_id] = Session(
                id=session_id,
                working_dir=working_dir,
                started_at=now,
                status=SessionStatus.ACTIVE,
                pid=pid,
                last_activity=now,
            )
            self._notify_observers()
        else:
            self.sessions[session_id].last_activity = datetime.now()
        return self.sessions[session_id]

    def end_session(self, session_id: str, status: SessionStatus = SessionStatus.COMPLETED) -> None:
        """Mark a session as ended."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.status = status
            session.ended_at = datetime.now()
            self._notify_observers()

    def remove_session(self, session_id: str) -> None:
        """Remove a session from state."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._notify_observers()

    # --- Agent Operations ---

    def add_agent(
        self,
        session_id: str,
        agent_id: str,
        agent_type: str,
        description: str,
        parent_id: str | None = None,
        working_dir: str = "",
    ) -> Agent:
        """Add a new agent to a session."""
        session = self.get_or_create_session(session_id, working_dir)

        if not session.working_dir and working_dir:
            session.working_dir = working_dir

        agent = Agent(
            id=agent_id,
            session_id=session_id,
            agent_type=agent_type,
            description=description,
            status=AgentStatus.RUNNING,
            started_at=datetime.now(),
            parent_id=parent_id,
        )

        session.agents.append(agent)

        if parent_id:
            parent = self.get_agent(session_id, parent_id)
            if parent:
                parent.children.append(agent)

        self._notify_observers()
        return agent

    def get_agent(self, session_id: str, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        return next((a for a in session.agents if a.id == agent_id), None)

    def update_agent_status(
        self,
        session_id: str,
        agent_id: str,
        status: AgentStatus,
    ) -> None:
        """Update an agent's status."""
        agent = self.get_agent(session_id, agent_id)
        if agent:
            agent.status = status
            if status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                agent.ended_at = datetime.now()
            self._notify_observers()

    # --- Tool Operations ---

    def add_tool_use(
        self,
        session_id: str,
        agent_id: str,
        tool_id: str,
        tool_name: str,
        tool_category: ToolCategory = ToolCategory.BUILTIN,
        parameters: dict | None = None,
    ) -> ToolUse | None:
        """Add a tool use to an agent."""
        agent = self.get_agent(session_id, agent_id)
        if not agent:
            return None

        tool = ToolUse(
            id=tool_id,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_category=tool_category,
            parameters=parameters or {},
            status=ToolStatus.RUNNING,
            started_at=datetime.now(),
        )

        agent.tool_uses.append(tool)
        self._notify_observers()
        return tool

    # --- Query Methods ---

    @property
    def active_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return [s for s in self.sessions.values() if s.status == SessionStatus.ACTIVE]

    @property
    def total_agents(self) -> int:
        """Get total number of agents across all sessions."""
        return sum(len(s.agents) for s in self.sessions.values())

    @property
    def running_agents(self) -> int:
        """Get number of currently running agents."""
        return sum(
            1
            for s in self.sessions.values()
            for a in s.agents
            if a.status == AgentStatus.RUNNING
        )

    @property
    def pending_inputs(self) -> int:
        """Get number of pending input requests."""
        return sum(
            1
            for s in self.sessions.values()
            for a in s.agents
            for r in a.input_requests
            if r.status == InputRequestStatus.PENDING
        )

    def get_all_pending_input_requests(self) -> list[tuple[Session, Agent, InputRequest]]:
        """Get all pending input requests with their session and agent context."""
        results = []
        for session in self.sessions.values():
            for agent in session.agents:
                for request in agent.input_requests:
                    if request.status == InputRequestStatus.PENDING:
                        results.append((session, agent, request))
        return results
