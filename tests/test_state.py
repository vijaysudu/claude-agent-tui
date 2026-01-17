"""Tests for the AppState class."""

import pytest
from datetime import datetime

from claude_agent_viz.state import AppState
from claude_agent_viz.store.models import (
    AgentStatus,
    InputRequestStatus,
    SessionStatus,
    ToolStatus,
)


class TestAppState:
    """Tests for AppState class."""

    def test_get_or_create_session(self):
        """Test session creation."""
        state = AppState()
        session = state.get_or_create_session(
            "test-session-1",
            working_dir="/tmp/test",
            pid=12345,
        )

        assert session.id == "test-session-1"
        assert session.working_dir == "/tmp/test"
        assert session.pid == 12345
        assert session.status == SessionStatus.ACTIVE
        assert "test-session-1" in state.sessions

    def test_get_existing_session(self):
        """Test getting an existing session."""
        state = AppState()
        session1 = state.get_or_create_session("test-session-1")
        session2 = state.get_or_create_session("test-session-1")

        assert session1 is session2

    def test_end_session(self):
        """Test ending a session."""
        state = AppState()
        state.get_or_create_session("test-session-1")
        state.end_session("test-session-1", SessionStatus.COMPLETED)

        session = state.sessions["test-session-1"]
        assert session.status == SessionStatus.COMPLETED
        assert session.ended_at is not None

    def test_add_agent(self):
        """Test adding an agent."""
        state = AppState()
        agent = state.add_agent(
            session_id="test-session-1",
            agent_id="agent-1",
            agent_type="Explore",
            description="Find files",
            working_dir="/tmp/test",
        )

        assert agent.id == "agent-1"
        assert agent.agent_type == "Explore"
        assert agent.description == "Find files"
        assert agent.status == AgentStatus.RUNNING
        assert len(state.sessions["test-session-1"].agents) == 1

    def test_add_agent_with_parent(self):
        """Test adding a child agent."""
        state = AppState()
        parent = state.add_agent(
            session_id="test-session-1",
            agent_id="parent-1",
            agent_type="Task",
            description="Main task",
        )
        child = state.add_agent(
            session_id="test-session-1",
            agent_id="child-1",
            agent_type="Explore",
            description="Sub task",
            parent_id="parent-1",
        )

        assert child.parent_id == "parent-1"
        assert child in parent.children

    def test_update_agent_status(self):
        """Test updating agent status."""
        state = AppState()
        state.add_agent(
            session_id="test-session-1",
            agent_id="agent-1",
            agent_type="Task",
            description="Test",
        )
        state.update_agent_status(
            "test-session-1", "agent-1", AgentStatus.COMPLETED
        )

        agent = state.get_agent("test-session-1", "agent-1")
        assert agent.status == AgentStatus.COMPLETED
        assert agent.ended_at is not None

    def test_add_tool_use(self):
        """Test adding a tool use."""
        state = AppState()
        state.add_agent(
            session_id="test-session-1",
            agent_id="agent-1",
            agent_type="Task",
            description="Test",
        )
        tool = state.add_tool_use(
            session_id="test-session-1",
            agent_id="agent-1",
            tool_id="tool-1",
            tool_name="Read",
            parameters={"file_path": "/tmp/test.txt"},
        )

        assert tool.id == "tool-1"
        assert tool.tool_name == "Read"
        assert tool.status == ToolStatus.RUNNING

    def test_complete_tool_use(self):
        """Test completing a tool use."""
        state = AppState()
        state.add_agent(
            session_id="test-session-1",
            agent_id="agent-1",
            agent_type="Task",
            description="Test",
        )
        state.add_tool_use(
            session_id="test-session-1",
            agent_id="agent-1",
            tool_id="tool-1",
            tool_name="Read",
        )
        state.complete_tool_use(
            session_id="test-session-1",
            agent_id="agent-1",
            tool_id="tool-1",
            status=ToolStatus.COMPLETED,
            result_preview="File contents...",
        )

        agent = state.get_agent("test-session-1", "agent-1")
        tool = agent.tool_uses[0]
        assert tool.status == ToolStatus.COMPLETED
        assert tool.result_preview == "File contents..."
        assert tool.duration_ms is not None

    def test_add_input_request(self):
        """Test adding an input request."""
        state = AppState()
        state.add_agent(
            session_id="test-session-1",
            agent_id="agent-1",
            agent_type="Task",
            description="Test",
        )
        request = state.add_input_request(
            session_id="test-session-1",
            agent_id="agent-1",
            request_id="req-1",
            prompt="Choose an option:",
            options=["Option A", "Option B"],
        )

        assert request.id == "req-1"
        assert request.prompt == "Choose an option:"
        assert len(request.options) == 2
        assert request.status == InputRequestStatus.PENDING

        # Agent should be waiting for input
        agent = state.get_agent("test-session-1", "agent-1")
        assert agent.status == AgentStatus.WAITING_INPUT

    def test_respond_to_input(self):
        """Test responding to an input request."""
        state = AppState()
        state.add_agent(
            session_id="test-session-1",
            agent_id="agent-1",
            agent_type="Task",
            description="Test",
        )
        state.add_input_request(
            session_id="test-session-1",
            agent_id="agent-1",
            request_id="req-1",
            prompt="Choose:",
            options=["A", "B"],
        )
        state.respond_to_input(
            session_id="test-session-1",
            agent_id="agent-1",
            request_id="req-1",
            response="A",
        )

        agent = state.get_agent("test-session-1", "agent-1")
        request = agent.input_requests[0]
        assert request.status == InputRequestStatus.RESPONDED
        assert request.response == "A"
        assert agent.status == AgentStatus.RUNNING

    def test_observer_notification(self):
        """Test that observers are notified on state changes."""
        state = AppState()
        notifications = []

        def observer():
            notifications.append(True)

        state.add_observer(observer)
        state.get_or_create_session("test-session-1")

        assert len(notifications) == 1

    def test_active_sessions_property(self):
        """Test active_sessions property."""
        state = AppState()
        state.get_or_create_session("active-1")
        state.get_or_create_session("active-2")
        state.get_or_create_session("completed-1")
        state.end_session("completed-1", SessionStatus.COMPLETED)

        active = state.active_sessions
        assert len(active) == 2
        assert all(s.status == SessionStatus.ACTIVE for s in active)

    def test_pending_inputs_property(self):
        """Test pending_inputs property."""
        state = AppState()
        state.add_agent("s1", "a1", "Task", "Test")
        state.add_agent("s1", "a2", "Task", "Test2")
        state.add_input_request("s1", "a1", "r1", "Q1?")
        state.add_input_request("s1", "a2", "r2", "Q2?")

        assert state.pending_inputs == 2

        state.respond_to_input("s1", "a1", "r1", "Answer")
        assert state.pending_inputs == 1


class TestApplyEvent:
    """Tests for apply_event method."""

    def test_apply_tool_start_event(self):
        """Test applying a tool_start event."""
        state = AppState()
        state.add_agent("session-1", "agent-1", "Task", "Test")

        state.apply_event({
            "type": "tool_start",
            "session_id": "session-1",
            "agent_id": "agent-1",
            "tool_id": "tool-1",
            "tool_name": "Read",
            "parameters": {"file_path": "/tmp/test.txt"},
        })

        agent = state.get_agent("session-1", "agent-1")
        assert len(agent.tool_uses) == 1
        assert agent.tool_uses[0].tool_name == "Read"

    def test_apply_tool_end_event(self):
        """Test applying a tool_end event."""
        state = AppState()
        state.add_agent("session-1", "agent-1", "Task", "Test")
        state.add_tool_use("session-1", "agent-1", "tool-1", "Read")

        state.apply_event({
            "type": "tool_end",
            "session_id": "session-1",
            "agent_id": "agent-1",
            "tool_id": "tool-1",
            "status": "completed",
            "result_preview": "File read successfully",
        })

        agent = state.get_agent("session-1", "agent-1")
        assert agent.tool_uses[0].status == ToolStatus.COMPLETED
        assert agent.tool_uses[0].result_preview == "File read successfully"

    def test_apply_session_end_event(self):
        """Test applying a session_end event."""
        state = AppState()
        state.get_or_create_session("session-1")

        state.apply_event({
            "type": "session_end",
            "session_id": "session-1",
        })

        assert state.sessions["session-1"].status == SessionStatus.COMPLETED

    def test_apply_session_idle_event(self):
        """Test applying a session_idle event keeps session ACTIVE."""
        state = AppState()
        session = state.get_or_create_session("session-1")
        original_activity = session.last_activity

        # Simulate some time passing
        import time
        time.sleep(0.01)

        state.apply_event({
            "event_type": "session_idle",
            "session_id": "session-1",
        })

        # Session should still be active, but last_activity updated
        assert state.sessions["session-1"].status == SessionStatus.ACTIVE
        assert state.sessions["session-1"].last_activity > original_activity
