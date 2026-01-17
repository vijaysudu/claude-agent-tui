"""Detail panel widget for Claude Agent Visualizer.

Shows detailed information about the selected session, agent, or tool.
"""

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, ProgressBar, DataTable

from ...store.models import (
    Agent,
    AgentStatus,
    InputRequest,
    InputRequestStatus,
    Session,
    ToolUse,
    ToolStatus,
)


class DetailPanel(Container):
    """Panel showing details of selected item.

    Adapts its content based on what type of item is selected:
    - Session: Overview with agent summary
    - Agent: Status, tokens, tools used
    - Tool: Parameters and result
    - Input Request: Question and options
    """

    DEFAULT_CSS = """
    DetailPanel {
        width: 100%;
        height: 100%;
        border: solid $surface-lighten-2;
        background: $surface;
        padding: 1 2;
    }

    DetailPanel .title {
        text-style: bold;
        margin-bottom: 1;
    }

    DetailPanel .section {
        margin-bottom: 1;
    }

    DetailPanel .section-header {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    DetailPanel .value {
        color: $text;
    }

    DetailPanel .dim {
        color: $text-muted;
    }

    DetailPanel .status-active {
        color: $success;
    }

    DetailPanel .status-running {
        color: $warning;
    }

    DetailPanel .status-completed {
        color: $text-muted;
    }

    DetailPanel .status-failed {
        color: $error;
    }

    DetailPanel .status-waiting {
        color: $primary;
    }

    DetailPanel .prompt {
        background: $surface-lighten-1;
        padding: 1;
        margin: 1 0;
    }

    DetailPanel DataTable {
        height: auto;
        max-height: 10;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_data = None

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-content"):
            yield Static("Select an item to view details", classes="dim")

    def show(self, data) -> None:
        """Show details for the given data item."""
        self._current_data = data

        # Clear existing content
        content = self.query_one("#detail-content", Vertical)
        content.remove_children()

        if isinstance(data, Session):
            self._show_session(content, data)
        elif isinstance(data, Agent):
            self._show_agent(content, data)
        elif isinstance(data, ToolUse):
            self._show_tool(content, data)
        elif isinstance(data, InputRequest):
            self._show_input_request(content, data)
        else:
            content.mount(Static("Select an item to view details", classes="dim"))

    def _show_session(self, container: Vertical, session: Session) -> None:
        """Show session details."""
        # Title
        dir_name = Path(session.working_dir).name or session.working_dir
        container.mount(Static(f"Session: {dir_name}", classes="title"))

        # Status and info - use Rich colors directly
        status_color = {
            "active": "green",
            "completed": "dim",
            "failed": "red",
        }.get(session.status.value, "")
        container.mount(
            Static(
                Text.assemble(
                    ("Status: ", ""),
                    (session.status.value.upper(), status_color),
                    ("  |  ", "dim"),
                    ("PID: ", ""),
                    (str(session.pid), ""),
                ),
                classes="section",
            )
        )

        # Working directory
        container.mount(Static(f"Directory: {session.working_dir}", classes="dim section"))

        # Duration
        duration = self._format_duration(session.duration)
        container.mount(Static(f"Duration: {duration}", classes="section"))

        # Statistics
        container.mount(Static("Statistics", classes="section-header"))
        total_agents = len(session.agents)
        active = len([a for a in session.agents if a.status == AgentStatus.RUNNING])
        completed = len([a for a in session.agents if a.status == AgentStatus.COMPLETED])
        waiting = len([a for a in session.agents if a.status == AgentStatus.WAITING_INPUT])
        failed = len([a for a in session.agents if a.status == AgentStatus.FAILED])

        stats_text = Text.assemble(
            (f"Total: {total_agents}", ""),
            ("  |  ", "dim"),
            (f"Active: {active}", "yellow"),
            ("  |  ", "dim"),
            (f"Completed: {completed}", "dim"),
        )
        if waiting > 0:
            stats_text.append("  |  ", "dim")
            stats_text.append(f"Waiting: {waiting}", "cyan")
        if failed > 0:
            stats_text.append("  |  ", "dim")
            stats_text.append(f"Failed: {failed}", "red")

        container.mount(Static(stats_text, classes="section"))

        # Total tokens
        total_tokens = sum(a.tokens_used for a in session.agents)
        container.mount(Static(f"Total tokens: {total_tokens:,}", classes="section"))

    def _show_agent(self, container: Vertical, agent: Agent) -> None:
        """Show agent details."""
        # Title
        container.mount(Static(f"Agent: {agent.agent_type}", classes="title"))

        # Status - use Rich colors directly
        status_color = {
            AgentStatus.RUNNING: "yellow",
            AgentStatus.COMPLETED: "dim",
            AgentStatus.FAILED: "red",
            AgentStatus.WAITING_INPUT: "cyan",
        }.get(agent.status, "")
        status_icon = {
            AgentStatus.RUNNING: "●",
            AgentStatus.COMPLETED: "○",
            AgentStatus.FAILED: "✗",
            AgentStatus.WAITING_INPUT: "◐",
        }.get(agent.status, "?")

        container.mount(
            Static(
                Text.assemble(
                    ("Status: ", ""),
                    (f"{status_icon} {agent.status.value.replace('_', ' ').title()}", status_color),
                ),
                classes="section",
            )
        )

        # Description
        container.mount(Static(f"Task: {agent.description}", classes="section"))

        # Duration
        duration = self._format_duration(agent.duration)
        container.mount(Static(f"Duration: {duration}", classes="section"))

        # Context metrics
        container.mount(Static("Context", classes="section-header"))
        container.mount(
            Static(
                f"Tokens: {agent.tokens_used:,}  |  Messages: {agent.messages_count}",
                classes="section",
            )
        )

        # Token progress bar (assume 100k context for visualization)
        if agent.tokens_used > 0:
            progress = min(agent.tokens_used / 100000, 1.0)
            bar = ProgressBar(total=100, show_eta=False)
            bar.progress = int(progress * 100)
            container.mount(bar)

        # Recent tools
        if agent.tool_uses:
            container.mount(Static("Recent Tools", classes="section-header"))
            table = DataTable(show_header=False)
            table.add_columns("status", "tool", "result")

            for tool in agent.tool_uses[-5:]:
                icon = {
                    ToolStatus.RUNNING: ("●", "yellow"),
                    ToolStatus.COMPLETED: ("○", "green"),
                    ToolStatus.FAILED: ("✗", "red"),
                }.get(tool.status, ("?", ""))

                result = tool.result_preview or tool.error_message or ""
                if len(result) > 30:
                    result = result[:27] + "..."

                table.add_row(
                    Text(icon[0], style=icon[1]),
                    tool.display_name,
                    Text(result, style="dim"),
                )

            container.mount(table)

    def _show_tool(self, container: Vertical, tool: ToolUse) -> None:
        """Show tool use details."""
        container.mount(Static(f"Tool: {tool.display_name}", classes="title"))

        # Status - use Rich colors directly
        status_color = {
            ToolStatus.RUNNING: "yellow",
            ToolStatus.COMPLETED: "green",
            ToolStatus.FAILED: "red",
        }.get(tool.status, "")
        container.mount(
            Static(
                Text.assemble(
                    ("Status: ", ""),
                    (tool.status.value.upper(), status_color),
                ),
                classes="section",
            )
        )

        # Duration
        if tool.duration_ms:
            container.mount(Static(f"Duration: {tool.duration_ms}ms", classes="section"))

        # Category
        container.mount(Static(f"Category: {tool.tool_category.value}", classes="dim section"))

        # Parameters
        if tool.parameters:
            container.mount(Static("Parameters", classes="section-header"))
            for key, value in list(tool.parameters.items())[:5]:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                container.mount(Static(f"  {key}: {value_str}", classes="dim"))

        # Result
        if tool.result_preview:
            container.mount(Static("Result", classes="section-header"))
            container.mount(Static(tool.result_preview, classes="section"))

        # Error
        if tool.error_message:
            container.mount(Static("Error", classes="section-header"))
            container.mount(
                Static(
                    Text(tool.error_message, style="red"),
                    classes="section",
                )
            )

    def _show_input_request(self, container: Vertical, request: InputRequest) -> None:
        """Show input request details."""
        container.mount(Static("Input Request", classes="title"))

        # Status - use Rich colors directly
        status_color = {
            InputRequestStatus.PENDING: "cyan",
            InputRequestStatus.RESPONDED: "dim",
            InputRequestStatus.EXPIRED: "red",
        }.get(request.status, "")
        container.mount(
            Static(
                Text.assemble(
                    ("Status: ", ""),
                    (request.status.value.upper(), status_color),
                ),
                classes="section",
            )
        )

        # Time waiting
        if request.status == InputRequestStatus.PENDING:
            wait_time = datetime.now() - request.created_at
            wait_str = self._format_duration(wait_time)
            container.mount(Static(f"Waiting: {wait_str}", classes="section"))

        # Prompt
        container.mount(Static("Question", classes="section-header"))
        container.mount(Static(request.prompt, classes="prompt"))

        # Options
        if request.options:
            container.mount(Static("Options", classes="section-header"))
            for i, opt in enumerate(request.options, 1):
                opt_text = Text.assemble(
                    (f"[{i}] ", "bold"),
                    (opt.label, ""),
                )
                if opt.description:
                    opt_text.append(f" - {opt.description}", "dim")
                container.mount(Static(opt_text))

        # Instructions
        if request.status == InputRequestStatus.PENDING:
            container.mount(
                Static(
                    "\nRespond in the terminal where Claude is running.",
                    classes="dim section",
                )
            )

        # Response (if responded)
        if request.response:
            container.mount(Static("Response", classes="section-header"))
            container.mount(Static(request.response, classes="section"))

    def _format_duration(self, td) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(td.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
