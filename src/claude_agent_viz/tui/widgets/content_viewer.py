"""Content viewer widget for displaying tool results with syntax highlighting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import RichLog


def get_language_from_path(file_path: str) -> str:
    """Determine the language/lexer from a file path."""
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
        ".scss": "scss",
        ".sql": "sql",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".toml": "toml",
        ".ini": "ini",
        ".xml": "xml",
        ".dockerfile": "dockerfile",
    }

    path = Path(file_path)

    # Check for Dockerfile without extension
    if path.name.lower() == "dockerfile":
        return "dockerfile"

    return suffix_map.get(path.suffix.lower(), "text")


class ContentViewer(Container):
    """Displays tool content with syntax highlighting."""

    DEFAULT_CSS = """
    ContentViewer {
        height: 100%;
        width: 100%;
    }

    ContentViewer .content-scroll {
        height: 100%;
        width: 100%;
    }

    ContentViewer .file-header {
        background: $surface;
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
    }

    ContentViewer .error-content {
        color: $error;
        padding: 1;
    }

    ContentViewer .command-header {
        background: $surface;
        color: $primary;
        padding: 0 1;
    }

    ContentViewer .diff-add {
        color: $success;
    }

    ContentViewer .diff-remove {
        color: $error;
    }

    ContentViewer RichLog {
        height: auto;
        max-height: 100%;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._content_log: RichLog | None = None

    def compose(self) -> ComposeResult:
        """Compose the widget."""
        with VerticalScroll(classes="content-scroll"):
            yield RichLog(highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        """Handle mount event."""
        self._content_log = self.query_one(RichLog)

    def clear(self) -> None:
        """Clear the content viewer."""
        if self._content_log:
            self._content_log.clear()

    def show_file_content(self, content: str, file_path: str) -> None:
        """Display file contents with syntax highlighting.

        Args:
            content: The file contents to display.
            file_path: Path to the file (used for syntax detection).
        """
        if not self._content_log:
            return

        self._content_log.clear()

        # Add file header
        header = Text(f" {file_path}", style="italic dim")
        self._content_log.write(header)
        self._content_log.write("")

        # Add syntax-highlighted content
        language = get_language_from_path(file_path)
        syntax = Syntax(
            content,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        self._content_log.write(syntax)

    def show_diff(self, old_string: str, new_string: str, file_path: str) -> None:
        """Display a diff between old and new content.

        Args:
            old_string: The original content.
            new_string: The new content.
            file_path: Path to the file being edited.
        """
        if not self._content_log:
            return

        self._content_log.clear()

        # Add file header
        header = Text(f" {file_path}", style="italic dim")
        self._content_log.write(header)
        self._content_log.write("")

        # Create unified diff-style output
        old_lines = old_string.splitlines()
        new_lines = new_string.splitlines()

        # Simple diff visualization
        self._content_log.write(Text("───────────────────────────────────", style="dim"))
        self._content_log.write(Text("Changes:", style="bold"))
        self._content_log.write("")

        # Show removed lines
        for line in old_lines:
            styled_line = Text()
            styled_line.append("- ", style="red bold")
            styled_line.append(line, style="red")
            self._content_log.write(styled_line)

        # Show added lines
        for line in new_lines:
            styled_line = Text()
            styled_line.append("+ ", style="green bold")
            styled_line.append(line, style="green")
            self._content_log.write(styled_line)

        self._content_log.write("")
        self._content_log.write(Text("───────────────────────────────────", style="dim"))

    def show_command_output(self, command: str, output: str, is_error: bool = False) -> None:
        """Display command output.

        Args:
            command: The command that was executed.
            output: The command output.
            is_error: Whether the output is an error.
        """
        if not self._content_log:
            return

        self._content_log.clear()

        # Add command header
        cmd_text = Text()
        cmd_text.append("$ ", style="green bold")
        cmd_text.append(command, style="bold")
        self._content_log.write(cmd_text)
        self._content_log.write("")

        # Add output
        style = "red" if is_error else None
        if output:
            # Try to detect if output looks like code
            syntax = Syntax(
                output,
                "bash",
                theme="monokai",
                word_wrap=True,
            )
            self._content_log.write(syntax)
        else:
            self._content_log.write(Text("(no output)", style="dim italic"))

    def show_search_results(
        self,
        pattern: str,
        results: str,
        search_type: str = "grep",
    ) -> None:
        """Display search results (grep/glob).

        Args:
            pattern: The search pattern.
            results: The search results.
            search_type: Type of search ("grep" or "glob").
        """
        if not self._content_log:
            return

        self._content_log.clear()

        # Add search header
        header = Text()
        header.append(f"{search_type.upper()}: ", style="cyan bold")
        header.append(pattern, style="yellow")
        self._content_log.write(header)
        self._content_log.write("")

        if results:
            # For grep results, highlight matches
            for line in results.splitlines():
                self._content_log.write(Text(line))
        else:
            self._content_log.write(Text("(no matches)", style="dim italic"))

    def show_generic_content(self, title: str, content: str) -> None:
        """Display generic content.

        Args:
            title: Title to display.
            content: Content to display.
        """
        if not self._content_log:
            return

        self._content_log.clear()

        # Add title
        self._content_log.write(Text(title, style="bold"))
        self._content_log.write("")

        # Add content
        self._content_log.write(content)

    def show_error(self, error_message: str) -> None:
        """Display an error message.

        Args:
            error_message: The error message to display.
        """
        if not self._content_log:
            return

        self._content_log.clear()

        # Add error header
        header = Text(" ERROR", style="red bold")
        self._content_log.write(header)
        self._content_log.write("")

        # Add error content
        self._content_log.write(Text(error_message, style="red"))
