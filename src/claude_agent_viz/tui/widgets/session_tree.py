"""Session tree widget for Claude Agent Visualizer.

Displays sessions and agents in a hierarchical tree structure.
"""

from pathlib import Path
from typing import Union

from rich.text import Text
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ...state import AppState
from ...store.models import (
    Agent,
    AgentStatus,
    InputRequest,
    InputRequestStatus,
    Session,
    SessionStatus,
    ToolUse,
)


# Type alias for tree node data
TreeData = Union[Session, Agent, ToolUse, InputRequest, None]


class SessionTree(Tree[TreeData]):
    """Hierarchical tree of sessions and agents.

    Shows:
    - Sessions (collapsed/expanded)
    - Agents under each session (with status icons)
    - Tool uses under each agent
    - Input requests under agents waiting for input
    """

    DEFAULT_CSS = """
    SessionTree {
        width: 100%;
        height: 100%;
        border: solid $surface-lighten-2;
        background: $surface;
    }

    SessionTree:focus {
        border: solid $primary;
    }

    SessionTree > .tree--cursor {
        background: $surface-lighten-2;
    }
    """

    class NodeSelected(Message):
        """Message sent when a node is selected."""

        def __init__(self, data: TreeData) -> None:
            self.data = data
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__("Sessions", **kwargs)
        self.guide_depth = 3
        self._state: AppState | None = None

    def update_from_state(self, state: AppState) -> None:
        """Rebuild the tree from application state."""
        self._state = state

        # Remember which nodes were expanded
        expanded_ids = self._get_expanded_ids()

        # Clear and rebuild
        self.clear()

        # Sort sessions: active first, then by start time
        sessions = sorted(
            state.sessions.values(),
            key=lambda s: (s.status != SessionStatus.ACTIVE, s.started_at),
            reverse=True,
        )

        for session in sessions:
            self._add_session(session, expanded_ids)

        # Expand root by default
        self.root.expand()

    def _get_expanded_ids(self) -> set[str]:
        """Get IDs of currently expanded nodes."""
        expanded = set()

        def collect(node: TreeNode[TreeData]) -> None:
            if node.is_expanded and node.data:
                if hasattr(node.data, "id"):
                    expanded.add(node.data.id)
            for child in node.children:
                collect(child)

        collect(self.root)
        return expanded

    def _add_session(self, session: Session, expanded_ids: set[str]) -> None:
        """Add a session node to the tree."""
        label = self._format_session_label(session)
        node = self.root.add(label, data=session)

        # Expand if was expanded, or if active
        if session.id in expanded_ids or session.status == SessionStatus.ACTIVE:
            node.expand()

        # Add root agents (those without parents)
        root_agents = [a for a in session.agents if a.parent_id is None]
        for agent in root_agents:
            self._add_agent(node, agent, expanded_ids)

    def _add_agent(
        self,
        parent: TreeNode[TreeData],
        agent: Agent,
        expanded_ids: set[str],
    ) -> None:
        """Add an agent node to the tree."""
        label = self._format_agent_label(agent)
        node = parent.add(label, data=agent)

        # Expand if running or waiting for input
        should_expand = (
            agent.id in expanded_ids
            or agent.status in (AgentStatus.RUNNING, AgentStatus.WAITING_INPUT)
        )
        if should_expand:
            node.expand()

        # Add recent tool uses (last 3)
        for tool in agent.tool_uses[-3:]:
            tool_label = self._format_tool_label(tool)
            node.add_leaf(tool_label, data=tool)

        # Add pending input requests
        for request in agent.input_requests:
            if request.status == InputRequestStatus.PENDING:
                request_label = self._format_input_label(request)
                node.add_leaf(request_label, data=request)

        # Recursively add child agents
        for child in agent.children:
            self._add_agent(node, child, expanded_ids)

    def _format_session_label(self, session: Session) -> Text:
        """Format a session node label."""
        # Get directory name (last part of path)
        dir_name = Path(session.working_dir).name or session.working_dir
        if len(dir_name) > 25:
            dir_name = dir_name[:22] + "..."

        # Format duration
        duration = self._format_duration(session.duration)

        # Status indicator - show idle if no recent activity
        if session.status == SessionStatus.ACTIVE and session.is_idle:
            status_style = "yellow dim"
            status_suffix = " (idle)"
        elif session.status == SessionStatus.ACTIVE:
            status_style = "green"
            status_suffix = ""
        elif session.status == SessionStatus.COMPLETED:
            status_style = "dim"
            status_suffix = ""
        elif session.status == SessionStatus.FAILED:
            status_style = "red"
            status_suffix = ""
        else:
            status_style = ""
            status_suffix = ""

        return Text.assemble(
            (dir_name, f"bold {status_style}"),
            (status_suffix, "dim"),
            " ",
            (f"[{duration}]", "dim"),
        )

    def _format_agent_label(self, agent: Agent) -> Text:
        """Format an agent node label."""
        # Status icon and color
        icon, color = {
            AgentStatus.RUNNING: ("●", "yellow"),
            AgentStatus.COMPLETED: ("○", "green"),
            AgentStatus.FAILED: ("✗", "red"),
            AgentStatus.WAITING_INPUT: ("◐", "blue bold"),
        }.get(agent.status, ("?", ""))

        # Truncate description
        desc = agent.description
        if len(desc) > 30:
            desc = desc[:27] + "..."

        return Text.assemble(
            (icon, color),
            " ",
            (agent.agent_type, "bold"),
            ": ",
            (desc, ""),
        )

    def _format_tool_label(self, tool: ToolUse) -> Text:
        """Format a tool use node label."""
        # Status icon
        icon, color = {
            "running": ("●", "yellow"),
            "completed": ("○", "green dim"),
            "failed": ("✗", "red"),
        }.get(tool.status.value, ("?", ""))

        # Tool display name
        name = tool.display_name
        if len(name) > 20:
            name = name[:17] + "..."

        # Result preview if completed
        result = ""
        if tool.result_preview:
            result = f" → {tool.result_preview[:20]}"
        elif tool.error_message:
            result = f" → {tool.error_message[:20]}"

        return Text.assemble(
            ("└─", "dim"),
            (icon, color),
            " ",
            (name, "dim"),
            (result, "dim italic"),
        )

    def _format_input_label(self, request: InputRequest) -> Text:
        """Format an input request node label."""
        prompt = request.prompt
        if len(prompt) > 35:
            prompt = prompt[:32] + "..."

        return Text.assemble(
            ("└─ ", "dim"),
            ("? ", "blue bold"),
            (f'"{prompt}"', "blue italic"),
        )

    def _format_duration(self, td) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(td.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def on_tree_node_selected(self, event: Tree.NodeSelected[TreeData]) -> None:
        """Handle node selection."""
        if event.node.data is not None:
            self.post_message(self.NodeSelected(event.node.data))
