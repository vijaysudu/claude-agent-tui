"""Detail panel widget for displaying tool and session details."""

from __future__ import annotations

import json
from typing import Any

from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Container
from textual.app import ComposeResult
from textual.widgets import Static, RichLog

from ...store.models import ToolUse, ToolStatus, Session


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
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_tool: ToolUse | None = None
        self._current_session: Session | None = None

    def compose(self) -> ComposeResult:
        """Compose the widget with persistent children."""
        yield Static("Select a session or tool", id="detail-header")
        yield RichLog(highlight=True, markup=True, wrap=True, id="detail-content")

    def show_tool(self, tool: ToolUse | None) -> None:
        """Display tool details."""
        self._current_tool = tool

        header = self.query_one("#detail-header", Static)
        content = self.query_one("#detail-content", RichLog)
        content.clear()

        if tool is None:
            if self._current_session:
                self._render_session(self._current_session, header, content)
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
            return

        self._render_session(session, header, content)

    def _render_session(self, session: Session, header: Static, content: RichLog) -> None:
        """Render session content."""
        # Update header
        header_text = f" Session: {session.display_name}"
        if session.is_active:
            header_text += " [green](active)[/green]"
        header.update(header_text)

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
