"""Demo data generator for Claude Agent Visualizer.

Provides realistic mock data for testing the TUI without needing actual
Claude Code sessions running.
"""

from datetime import datetime, timedelta

from .state import AppState
from .store.models import (
    Agent,
    AgentStatus,
    InputOption,
    InputRequest,
    InputRequestStatus,
    InputRequestType,
    Session,
    SessionStatus,
    ToolCategory,
    ToolStatus,
    ToolUse,
)


def create_demo_state() -> AppState:
    """Create a demo state with realistic sample data.

    Returns an AppState populated with multiple sessions, agents, and tools
    to showcase all features of the visualizer.
    """
    state = AppState()
    now = datetime.now()

    # --- Session 1: Active development session with multiple agents ---
    session1 = Session(
        id="sess_demo_abc123",
        working_dir="~/projects/myapp",
        started_at=now - timedelta(minutes=5, seconds=32),
        status=SessionStatus.ACTIVE,
        pid=12345,
        last_activity=now - timedelta(seconds=5),
    )

    # Root agent
    root_agent = Agent(
        id="agent_root_001",
        session_id=session1.id,
        agent_type="Root",
        description="Main orchestration",
        status=AgentStatus.RUNNING,
        started_at=session1.started_at,
        tokens_used=15234,
        messages_count=24,
    )

    # Explore agent (child of root)
    explore_agent = Agent(
        id="agent_explore_002",
        session_id=session1.id,
        parent_id=root_agent.id,
        agent_type="Explore",
        description="Find authentication files",
        status=AgentStatus.RUNNING,
        started_at=now - timedelta(minutes=3),
        tokens_used=4521,
        messages_count=8,
        tool_uses=[
            ToolUse(
                id="tool_001",
                agent_id="agent_explore_002",
                tool_name="Glob",
                tool_category=ToolCategory.BUILTIN,
                parameters={"pattern": "**/*.py"},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=2, seconds=45),
                ended_at=now - timedelta(minutes=2, seconds=42),
                duration_ms=3000,
                result_preview="45 files matched",
            ),
            ToolUse(
                id="tool_002",
                agent_id="agent_explore_002",
                tool_name="Grep",
                tool_category=ToolCategory.BUILTIN,
                parameters={"pattern": "authentication", "path": "src/"},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=2, seconds=30),
                ended_at=now - timedelta(minutes=2, seconds=25),
                duration_ms=5000,
                result_preview="12 matches in 5 files",
            ),
            ToolUse(
                id="tool_003",
                agent_id="agent_explore_002",
                tool_name="Read",
                tool_category=ToolCategory.BUILTIN,
                parameters={"file_path": "src/auth/login.py"},
                status=ToolStatus.RUNNING,
                started_at=now - timedelta(seconds=5),
            ),
        ],
    )
    root_agent.children.append(explore_agent)

    # Plan agent (child of root, waiting for input)
    plan_agent = Agent(
        id="agent_plan_003",
        session_id=session1.id,
        parent_id=root_agent.id,
        agent_type="Plan",
        description="Design authentication flow",
        status=AgentStatus.WAITING_INPUT,
        started_at=now - timedelta(minutes=1, seconds=30),
        tokens_used=2100,
        messages_count=5,
        input_requests=[
            InputRequest(
                id="input_001",
                agent_id="agent_plan_003",
                session_id=session1.id,
                request_type=InputRequestType.SELECTION,
                prompt="Which authentication method should we implement?",
                options=[
                    InputOption(
                        label="OAuth 2.0",
                        value="oauth",
                        description="Industry standard for third-party auth",
                    ),
                    InputOption(
                        label="JWT",
                        value="jwt",
                        description="Stateless token-based authentication",
                    ),
                    InputOption(
                        label="Session-based",
                        value="session",
                        description="Traditional server-side sessions",
                    ),
                ],
                status=InputRequestStatus.PENDING,
                created_at=now - timedelta(seconds=45),
            ),
        ],
    )
    root_agent.children.append(plan_agent)

    # Completed bash agent
    bash_agent = Agent(
        id="agent_bash_004",
        session_id=session1.id,
        parent_id=root_agent.id,
        agent_type="Bash",
        description="Run tests",
        status=AgentStatus.COMPLETED,
        started_at=now - timedelta(minutes=4, seconds=15),
        ended_at=now - timedelta(minutes=3, seconds=45),
        tokens_used=890,
        messages_count=3,
        tool_uses=[
            ToolUse(
                id="tool_004",
                agent_id="agent_bash_004",
                tool_name="Bash",
                tool_category=ToolCategory.COMMAND,
                parameters={"command": "npm test"},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=4),
                ended_at=now - timedelta(minutes=3, seconds=50),
                duration_ms=10000,
                result_preview="42 tests passed, 0 failed",
            ),
        ],
    )
    root_agent.children.append(bash_agent)

    session1.agents = [root_agent, explore_agent, plan_agent, bash_agent]
    state.sessions[session1.id] = session1

    # --- Session 2: Simpler session with MCP tools ---
    session2 = Session(
        id="sess_demo_def456",
        working_dir="~/projects/api",
        started_at=now - timedelta(minutes=2, seconds=15),
        status=SessionStatus.ACTIVE,
        pid=12346,
        last_activity=now - timedelta(seconds=10),
    )

    api_agent = Agent(
        id="agent_api_005",
        session_id=session2.id,
        agent_type="general-purpose",
        description="Review PR #123",
        status=AgentStatus.RUNNING,
        started_at=session2.started_at,
        tokens_used=8765,
        messages_count=15,
        tool_uses=[
            ToolUse(
                id="tool_005",
                agent_id="agent_api_005",
                tool_name="mcp__github__pull_request_read",
                tool_category=ToolCategory.MCP,
                parameters={"owner": "myorg", "repo": "api", "pull_number": 123},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=2),
                ended_at=now - timedelta(minutes=1, seconds=55),
                duration_ms=5000,
                result_preview="PR #123: Add user authentication",
            ),
            ToolUse(
                id="tool_006",
                agent_id="agent_api_005",
                tool_name="mcp__github__get_file_contents",
                tool_category=ToolCategory.MCP,
                parameters={"path": "src/auth.py"},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=1, seconds=50),
                ended_at=now - timedelta(minutes=1, seconds=45),
                duration_ms=5000,
                result_preview="File contents retrieved",
            ),
        ],
    )

    session2.agents = [api_agent]
    state.sessions[session2.id] = session2

    # --- Session 3: Recently completed session ---
    session3 = Session(
        id="sess_demo_ghi789",
        working_dir="~/projects/docs",
        started_at=now - timedelta(minutes=10),
        ended_at=now - timedelta(minutes=1),
        status=SessionStatus.COMPLETED,
        pid=12347,
        last_activity=now - timedelta(minutes=1),
    )

    docs_agent = Agent(
        id="agent_docs_006",
        session_id=session3.id,
        agent_type="Explore",
        description="Update README",
        status=AgentStatus.COMPLETED,
        started_at=session3.started_at,
        ended_at=session3.ended_at,
        tokens_used=3200,
        messages_count=7,
        tool_uses=[
            ToolUse(
                id="tool_007",
                agent_id="agent_docs_006",
                tool_name="Read",
                tool_category=ToolCategory.BUILTIN,
                parameters={"file_path": "README.md"},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=9),
                ended_at=now - timedelta(minutes=8, seconds=55),
                duration_ms=5000,
            ),
            ToolUse(
                id="tool_008",
                agent_id="agent_docs_006",
                tool_name="Edit",
                tool_category=ToolCategory.BUILTIN,
                parameters={"file_path": "README.md"},
                status=ToolStatus.COMPLETED,
                started_at=now - timedelta(minutes=5),
                ended_at=now - timedelta(minutes=4, seconds=50),
                duration_ms=10000,
            ),
        ],
    )

    session3.agents = [docs_agent]
    state.sessions[session3.id] = session3

    # --- Session 4: Failed agent ---
    session4 = Session(
        id="sess_demo_jkl012",
        working_dir="~/projects/failing",
        started_at=now - timedelta(minutes=3),
        status=SessionStatus.ACTIVE,
        pid=12348,
        last_activity=now - timedelta(minutes=2),
    )

    failed_agent = Agent(
        id="agent_fail_007",
        session_id=session4.id,
        agent_type="Bash",
        description="Build project",
        status=AgentStatus.FAILED,
        started_at=session4.started_at,
        ended_at=now - timedelta(minutes=2),
        tokens_used=500,
        messages_count=2,
        tool_uses=[
            ToolUse(
                id="tool_009",
                agent_id="agent_fail_007",
                tool_name="Bash",
                tool_category=ToolCategory.COMMAND,
                parameters={"command": "npm run build"},
                status=ToolStatus.FAILED,
                started_at=now - timedelta(minutes=2, seconds=30),
                ended_at=now - timedelta(minutes=2),
                duration_ms=30000,
                error_message="Exit code 1: Module not found: '@types/node'",
            ),
        ],
    )

    session4.agents = [failed_agent]
    state.sessions[session4.id] = session4

    return state


def create_minimal_demo_state() -> AppState:
    """Create a minimal demo state with just one session.

    Useful for testing basic functionality.
    """
    state = AppState()
    now = datetime.now()

    session = Session(
        id="sess_minimal",
        working_dir="~/demo",
        started_at=now - timedelta(minutes=1),
        status=SessionStatus.ACTIVE,
        pid=99999,
        last_activity=now - timedelta(seconds=5),
    )

    agent = Agent(
        id="agent_minimal",
        session_id=session.id,
        agent_type="Explore",
        description="Demo agent",
        status=AgentStatus.RUNNING,
        started_at=session.started_at,
        tokens_used=1000,
        messages_count=5,
    )

    session.agents = [agent]
    state.sessions[session.id] = session

    return state
