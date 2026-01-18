"""Detail panel widget for displaying tool and session details."""

from __future__ import annotations

import json
from typing import Any

from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Container
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static, RichLog, Input

from ...store.models import ToolUse, ToolStatus, Session, ConversationMessage, MessageRole
from ...store.config_models import Skill, Hook, Command, Agent, MCPServer


# Status display
STATUS_DISPLAY = {
    ToolStatus.PENDING: (" Pending", "yellow"),
    ToolStatus.RUNNING: (" Running", "blue"),
    ToolStatus.COMPLETED: (" Completed", "green"),
    ToolStatus.ERROR: (" Error", "red"),
}


def get_language_from_path(file_path: str) -> str:
    """Determine the language/lexer from a file path."""
    from pathlib import Path
    suffix_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".sh": "bash",
        ".rs": "rust",
        ".go": "go",
    }
    path = Path(file_path)
    return suffix_map.get(path.suffix.lower(), "text")


class DetailPanel(Container):
    """Panel for displaying detailed tool or session information."""

    DEFAULT_CSS = """
    DetailPanel {
        height: 100%;
        width: 100%;
        border: solid $primary;
        padding: 0;
        layout: vertical;
    }

    DetailPanel #detail-header {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $primary;
    }

    DetailPanel #detail-content {
        height: 1fr;
        scrollbar-gutter: stable;
        border: none;
    }

    DetailPanel #reply-input {
        dock: bottom;
        height: 3;
        border-top: solid $primary;
        display: none;
    }

    DetailPanel.session-view #reply-input {
        display: block;
    }
    """

    class ReplySubmitted(Message):
        """Message sent when user submits a reply."""

        def __init__(self, session_id: str, message: str) -> None:
            super().__init__()
            self.session_id = session_id
            self.message = message

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_tool: ToolUse | None = None
        self._current_session: Session | None = None

    def compose(self) -> ComposeResult:
        """Compose the widget with persistent children."""
        yield Static("Select a session or tool", id="detail-header")
        yield RichLog(highlight=True, markup=True, wrap=True, id="detail-content")
        yield Input(placeholder="Press Enter to resume this session in a new terminal", id="reply-input")

    def show_welcome(self) -> None:
        """Display welcome/base state."""
        self._current_tool = None
        self._current_session = None

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        self.remove_class("session-view")

        header.update(" Claude Agent Visualizer")

        content.write(Text("Welcome", style="bold cyan"))
        content.write("")
        content.write("Select a session from the list to view details.")
        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")
        content.write(Text("Keyboard Shortcuts", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("n", "bold cyan"), (" - New session", "")))
        content.write(Text.assemble(("c", "bold cyan"), (" - Resume selected session", "")))
        content.write(Text.assemble(("k", "bold cyan"), (" - Kill selected session", "")))
        content.write(Text.assemble(("r", "bold cyan"), (" - Refresh sessions", "")))
        content.write(Text.assemble(("ESC", "bold cyan"), (" - Go back / Deselect", "")))
        content.write(Text.assemble(("q", "bold cyan"), (" - Quit", "")))

    def show_tool(self, tool: ToolUse | None) -> None:
        """Display tool details."""
        self._current_tool = tool

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        # Hide reply input when viewing tools
        self.remove_class("session-view")

        if tool is None:
            if self._current_session:
                self._render_session(self._current_session, header, content)
                self.add_class("session-view")
            else:
                header.update("Select a tool to view details")
            return

        self._render_tool(tool, header, content)

    def show_session(self, session: Session | None) -> None:
        """Display session details."""
        self._current_session = session
        self._current_tool = None

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        if session is None:
            header.update("Select a session to view details")
            self.remove_class("session-view")
            return

        self._render_session(session, header, content)
        # Show reply input for session view
        self.add_class("session-view")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle reply input submission."""
        if event.input.id == "reply-input" and self._current_session:
            message = event.value.strip()
            if message:
                event.input.value = ""
                self.post_message(
                    self.ReplySubmitted(
                        session_id=self._current_session.session_id,
                        message=message,
                    )
                )

    def _render_session(self, session: Session, header: Static, content: RichLog) -> None:
        """Render session content with full conversation view."""
        # Update header
        header_text = f" Session: {session.display_name}"
        if session.is_active:
            header_text += " [green](active)[/green]"
        header.update(header_text)

        # Build a tool map for quick lookup
        tool_map: dict[str, ToolUse] = {}
        for tool in session.tool_uses:
            tool_map[tool.tool_use_id] = tool

        # Render the full conversation
        if session.messages:
            for msg in session.messages:
                self._render_message(msg, content, tool_map)
        else:
            # Fallback to old view if no messages parsed
            self._render_session_summary(session, content)

    def _render_session_summary(self, session: Session, content: RichLog) -> None:
        """Render session summary (fallback when no messages available)."""
        # Session info
        content.write(Text("Session Information", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("ID: ", "bold"), (session.session_id, "")))
        content.write(Text.assemble(("Project: ", "bold"), (session.project_name, "cyan")))

        if session.project_path:
            content.write(Text.assemble(("Path: ", "bold"), (session.project_path, "dim")))

        status = "[green]Active[/green]" if session.is_active else "[dim]Inactive[/dim]"
        content.write(f"[bold]Status:[/bold] {status}")

        if session.start_time:
            content.write(Text.assemble(("Started: ", "bold"), (session.start_time, "")))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")

        # Summary
        if session.summary:
            content.write(Text("Summary", style="bold cyan"))
            content.write("")
            content.write(session.summary)
            content.write("")
            content.write(Text("─" * 40, style="dim"))
            content.write("")

        # Tool stats
        content.write(Text("Tool Usage", style="bold cyan"))
        content.write("")
        content.write(f"Total tool calls: {session.tool_count}")

        # Count by tool type
        tool_counts: dict[str, int] = {}
        error_count = 0
        for tool in session.tool_uses:
            tool_counts[tool.tool_name] = tool_counts.get(tool.tool_name, 0) + 1
            if tool.status == ToolStatus.ERROR:
                error_count += 1

        content.write("")
        for name, count in sorted(tool_counts.items()):
            content.write(f"  {name}: {count}")

        if error_count > 0:
            content.write("")
            content.write(Text(f"Errors: {error_count}", style="red"))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")
        content.write(Text("Select a tool from the list to view details", style="dim italic"))

    def _render_message(
        self,
        msg: ConversationMessage,
        content: RichLog,
        tool_map: dict[str, ToolUse],
    ) -> None:
        """Render a single conversation message."""
        if msg.role == MessageRole.USER:
            self._render_user_message(msg, content)
        else:
            self._render_assistant_message(msg, content, tool_map)

    def _render_user_message(self, msg: ConversationMessage, content: RichLog) -> None:
        """Render a user message."""
        if not msg.text_content:
            return

        # User message header
        content.write(Text("╭─ User ", style="bold blue") + Text("─" * 32, style="blue"))

        # Message content
        for line in msg.text_content.split("\n"):
            content.write(Text("│ ", style="blue") + Text(line))

        content.write(Text("╰" + "─" * 40, style="blue"))
        content.write("")

    def _render_assistant_message(
        self,
        msg: ConversationMessage,
        content: RichLog,
        tool_map: dict[str, ToolUse],
    ) -> None:
        """Render an assistant message."""
        # Skip if no content at all
        if not msg.text_content and not msg.thinking_content and not msg.tool_use_ids:
            return

        # Assistant message header
        content.write(Text("╭─ Claude ", style="bold green") + Text("─" * 30, style="green"))

        # Thinking content (collapsible)
        if msg.thinking_content:
            thinking_preview = msg.thinking_content[:100]
            if len(msg.thinking_content) > 100:
                thinking_preview += "..."
            content.write(Text("│ ", style="green") + Text("💭 ", style="dim") + Text(thinking_preview, style="dim italic"))

        # Text content
        if msg.text_content:
            for line in msg.text_content.split("\n"):
                content.write(Text("│ ", style="green") + Text(line))

        # Tool uses in this message
        if msg.tool_use_ids:
            content.write(Text("│", style="green"))
            for tool_id in msg.tool_use_ids:
                tool = tool_map.get(tool_id)
                if tool:
                    self._render_tool_compact(tool, content)

        content.write(Text("╰" + "─" * 40, style="green"))
        content.write("")

    def _render_tool_compact(self, tool: ToolUse, content: RichLog) -> None:
        """Render a compact tool use view."""
        # Tool icon and name
        status_icon = "✓" if tool.status == ToolStatus.COMPLETED else "✗"
        status_color = "green" if tool.status == ToolStatus.COMPLETED else "red"

        tool_header = Text("│  ", style="green")
        tool_header.append(f"[{status_color}]{status_icon}[/] ", style=status_color)
        tool_header.append(f"{tool.tool_name}", style="bold yellow")

        # Add preview info
        if tool.tool_name == "Read":
            path = tool.input_params.get("file_path", "")
            tool_header.append(f" {path}", style="dim")
        elif tool.tool_name == "Edit":
            path = tool.input_params.get("file_path", "")
            tool_header.append(f" {path}", style="dim")
        elif tool.tool_name == "Write":
            path = tool.input_params.get("file_path", "")
            tool_header.append(f" {path}", style="dim")
        elif tool.tool_name == "Bash":
            cmd = tool.input_params.get("command", "")[:50]
            tool_header.append(f" $ {cmd}", style="dim")
        elif tool.tool_name == "Grep":
            pattern = tool.input_params.get("pattern", "")[:30]
            tool_header.append(f" /{pattern}/", style="dim")
        elif tool.tool_name == "Glob":
            pattern = tool.input_params.get("pattern", "")[:30]
            tool_header.append(f" {pattern}", style="dim")
        elif tool.tool_name == "Task":
            desc = tool.input_params.get("description", "")[:30]
            tool_header.append(f" {desc}", style="dim")

        content.write(tool_header)

        # Show error if any
        if tool.error_message:
            error_preview = tool.error_message[:100].replace("\n", " ")
            content.write(Text("│    ", style="green") + Text(f"Error: {error_preview}", style="red dim"))

    def _render_tool(self, tool: ToolUse, header: Static, content: RichLog) -> None:
        """Render tool content."""
        # Update header
        status_text, status_color = STATUS_DISPLAY.get(
            tool.status, ("Unknown", "white")
        )
        header_text = f" {tool.tool_name}  [{status_color}]{status_text}[/]"
        header.update(header_text)

        # Overview section
        content.write(Text("Overview", style="bold cyan"))
        content.write("")

        # File path if applicable
        file_path = tool.get_file_path()
        if file_path:
            content.write(Text.assemble(("File: ", "bold"), (file_path, "")))

        # Command for Bash
        if tool.tool_name == "Bash":
            cmd = tool.input_params.get("command", "")
            content.write(Text.assemble(("Command: ", "bold"), ("", "")))
            content.write(Text(f"  $ {cmd}", style="green"))

        # Pattern for Grep/Glob
        if tool.tool_name in ("Grep", "Glob"):
            pattern = tool.input_params.get("pattern", "")
            content.write(Text.assemble(("Pattern: ", "bold"), (pattern, "yellow")))

        # Duration if available
        if tool.duration_ms is not None:
            content.write(f"Duration: {tool.duration_ms}ms")

        # Preview
        if tool.preview:
            content.write("")
            content.write(Text("Preview:", style="bold"))
            content.write(Text(tool.preview, style="dim"))

        content.write("")
        content.write(Text("─" * 40, style="dim"))

        # Content/Result section
        if tool.result_content or tool.error_message:
            content.write("")
            content.write(Text("Result", style="bold cyan"))
            content.write("")

            if tool.error_message:
                content.write(Text(" ERROR", style="red bold"))
                content.write(Text(tool.error_message, style="red"))
            elif tool.result_content:
                self._write_tool_result(tool, content)

            content.write("")
            content.write(Text("─" * 40, style="dim"))

        # Parameters section
        if tool.input_params:
            content.write("")
            content.write(Text("Parameters", style="bold cyan"))
            content.write("")

            for name, value in tool.input_params.items():
                content.write(Text(f"{name}:", style="bold cyan"))
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, indent=2)
                else:
                    value_str = str(value)
                content.write(Text(value_str, style="dim"))
                content.write("")

    def _write_tool_result(self, tool: ToolUse, content: RichLog) -> None:
        """Write tool result with appropriate formatting."""
        result = tool.result_content or ""

        if tool.tool_name == "Read":
            file_path = tool.input_params.get("file_path", "unknown")
            language = get_language_from_path(file_path)
            try:
                syntax = Syntax(
                    result,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                content.write(syntax)
            except Exception:
                content.write(result)

        elif tool.tool_name == "Edit":
            old_string = tool.input_params.get("old_string", "")
            new_string = tool.input_params.get("new_string", "")

            content.write(Text("Changes:", style="bold"))
            content.write("")

            for line in old_string.splitlines():
                styled = Text()
                styled.append("- ", style="red bold")
                styled.append(line, style="red")
                content.write(styled)

            for line in new_string.splitlines():
                styled = Text()
                styled.append("+ ", style="green bold")
                styled.append(line, style="green")
                content.write(styled)

            if result and result != "OK":
                content.write("")
                content.write(Text("Output:", style="bold"))
                content.write(result)

        elif tool.tool_name == "Write":
            file_path = tool.input_params.get("file_path", "unknown")
            written_content = tool.input_params.get("content", "")
            language = get_language_from_path(file_path)
            try:
                syntax = Syntax(
                    written_content,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                content.write(syntax)
            except Exception:
                content.write(written_content)

        elif tool.tool_name == "Bash":
            try:
                syntax = Syntax(
                    result,
                    "bash",
                    theme="monokai",
                    word_wrap=True,
                )
                content.write(syntax)
            except Exception:
                content.write(result)

        elif tool.tool_name in ("Grep", "Glob"):
            for line in result.splitlines():
                content.write(line)

        else:
            content.write(result)

    def show_skill(self, skill: Skill) -> None:
        """Display skill details."""
        self._current_tool = None
        self._current_session = None
        self.remove_class("session-view")

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        # Header
        icon = "" if skill.is_from_plugin else ""
        header.update(f"{icon} Skill: {skill.display_name}")

        # Skill info
        content.write(Text("Skill Information", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("Name: ", "bold"), (skill.name, "cyan")))

        if skill.is_from_plugin and skill.plugin_name:
            content.write(Text.assemble(("Plugin: ", "bold"), (skill.plugin_name, "magenta")))

        if skill.description:
            content.write(Text.assemble(("Description: ", "bold"), (skill.description, "")))

        content.write(Text.assemble(("File: ", "bold"), (str(skill.file_path), "dim")))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")

        # Skill content (markdown)
        content.write(Text("Content", style="bold cyan"))
        content.write("")

        try:
            syntax = Syntax(
                skill.content,
                "markdown",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            content.write(syntax)
        except Exception:
            content.write(skill.content)

    def show_hook(self, hook: Hook) -> None:
        """Display hook details."""
        self._current_tool = None
        self._current_session = None
        self.remove_class("session-view")

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        # Header
        header.update(f" Hook: {hook.display_name}")

        # Hook info
        content.write(Text("Hook Information", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("Type: ", "bold"), (hook.hook_type, "yellow")))

        if hook.matcher:
            content.write(Text.assemble(("Matcher: ", "bold"), (hook.matcher, "magenta")))

        if hook.timeout:
            content.write(Text.assemble(("Timeout: ", "bold"), (f"{hook.timeout}ms", "")))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")

        # Command
        content.write(Text("Command", style="bold cyan"))
        content.write("")

        try:
            syntax = Syntax(
                hook.command,
                "bash",
                theme="monokai",
                word_wrap=True,
            )
            content.write(syntax)
        except Exception:
            content.write(Text(f"$ {hook.command}", style="green"))

    def show_command(self, command: Command) -> None:
        """Display command details."""
        self._current_tool = None
        self._current_session = None
        self.remove_class("session-view")

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        # Header
        header.update(f" Command: /{command.name}")

        # Command info
        content.write(Text("Command Information", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("Name: ", "bold"), (f"/{command.name}", "cyan")))

        if command.description:
            content.write(Text.assemble(("Description: ", "bold"), (command.description, "")))

        content.write(Text.assemble(("File: ", "bold"), (str(command.file_path), "dim")))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")

        # Command content (markdown)
        content.write(Text("Content", style="bold cyan"))
        content.write("")

        try:
            syntax = Syntax(
                command.content,
                "markdown",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            content.write(syntax)
        except Exception:
            content.write(command.content)

    def show_agent(self, agent: Agent) -> None:
        """Display agent details."""
        self._current_tool = None
        self._current_session = None
        self.remove_class("session-view")

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        # Header
        icon = "" if agent.is_from_plugin else ""
        header.update(f"{icon} Agent: {agent.display_name}")

        # Agent info
        content.write(Text("Agent Information", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("Name: ", "bold"), (agent.name, "cyan")))

        if agent.is_from_plugin and agent.plugin_name:
            content.write(Text.assemble(("Plugin: ", "bold"), (agent.plugin_name, "magenta")))

        if agent.description:
            content.write(Text.assemble(("Description: ", "bold"), (agent.description, "")))

        content.write(Text.assemble(("Model: ", "bold"), (agent.model, "yellow")))

        if agent.color:
            # Show the color name, but use a safe style (don't style with the color itself
            # since it might not be a valid Rich color name like 'orange')
            content.write(Text.assemble(("Color: ", "bold"), (agent.color, "")))

        content.write(Text.assemble(("File: ", "bold"), (str(agent.file_path), "dim")))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")

        # Tools
        if agent.tools:
            content.write(Text("Available Tools", style="bold cyan"))
            content.write("")
            for tool in agent.tools:
                content.write(Text.assemble(("  • ", "dim"), (tool, "green")))
            content.write("")
            content.write(Text("─" * 40, style="dim"))
            content.write("")

        # Agent content (markdown)
        content.write(Text("Content", style="bold cyan"))
        content.write("")

        try:
            syntax = Syntax(
                agent.content,
                "markdown",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            content.write(syntax)
        except Exception:
            content.write(agent.content)

    def show_mcp_server(self, server: MCPServer) -> None:
        """Display MCP server details."""
        self._current_tool = None
        self._current_session = None
        self.remove_class("session-view")

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        # Header
        header.update(f" MCP Server: {server.name}")

        # Server info
        content.write(Text("MCP Server Information", style="bold cyan"))
        content.write("")
        content.write(Text.assemble(("Name: ", "bold"), (server.name, "green")))
        content.write(Text.assemble(("Command: ", "bold"), (server.command, "cyan")))

        content.write("")
        content.write(Text("─" * 40, style="dim"))
        content.write("")

        # Full command
        content.write(Text("Full Command", style="bold cyan"))
        content.write("")
        content.write(Text(f"$ {server.full_command}", style="green"))

        # Args
        if server.args:
            content.write("")
            content.write(Text("─" * 40, style="dim"))
            content.write("")
            content.write(Text("Arguments", style="bold cyan"))
            content.write("")
            for i, arg in enumerate(server.args):
                content.write(Text.assemble((f"  [{i}] ", "dim"), (arg, "")))

        # Environment variables
        if server.env:
            content.write("")
            content.write(Text("─" * 40, style="dim"))
            content.write("")
            content.write(Text("Environment Variables", style="bold cyan"))
            content.write("")
            for key, value in server.env.items():
                # Mask sensitive values
                if any(s in key.lower() for s in ["key", "token", "secret", "password"]):
                    display_value = "***" + value[-4:] if len(value) > 4 else "****"
                else:
                    display_value = value
                content.write(Text.assemble(
                    ("  ", ""),
                    (key, "yellow"),
                    ("=", "dim"),
                    (display_value, ""),
                ))

        # Working directory
        if server.cwd:
            content.write("")
            content.write(Text("─" * 40, style="dim"))
            content.write("")
            content.write(Text.assemble(("Working Directory: ", "bold"), (server.cwd, "dim")))
