"""Embedded terminal screen for Claude sessions using textual-terminal."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Container

try:
    from textual_terminal import Terminal
    TERMINAL_AVAILABLE = True
except ImportError:
    TERMINAL_AVAILABLE = False
    Terminal = None  # type: ignore[misc, assignment]

if TYPE_CHECKING:
    from textual_terminal import Terminal as TerminalType


class EmbeddedTerminalScreen(Screen):
    """Full-screen embedded terminal for Claude sessions."""

    DEFAULT_CSS = """
    EmbeddedTerminalScreen {
        background: $surface;
    }

    EmbeddedTerminalScreen .screen-container {
        height: 100%;
        width: 100%;
        padding: 0;
    }

    EmbeddedTerminalScreen Terminal {
        height: 1fr;
    }

    EmbeddedTerminalScreen .status-bar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }

    EmbeddedTerminalScreen .error-message {
        height: 100%;
        width: 100%;
        content-align: center middle;
        color: $error;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("ctrl+q", "force_close", "Force Quit", show=True),
    ]

    def __init__(
        self,
        session_id: str | None = None,
        cwd: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the embedded terminal screen.

        Args:
            session_id: Optional session ID to resume. If None, starts new session.
            cwd: Working directory for the session.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.session_id = session_id
        self.cwd = cwd or os.getcwd()
        self._terminal: Any = None

    def _get_command(self) -> str | None:
        """Build the command to run in the terminal."""
        claude_path = shutil.which("claude")
        if not claude_path:
            return None

        if self.session_id:
            return f"cd {self.cwd} && claude --resume {self.session_id}"
        else:
            return f"cd {self.cwd} && claude"

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()

        if not TERMINAL_AVAILABLE:
            yield Static(
                "[bold red]Error:[/] textual-terminal not installed.\n\n"
                "Install with: pip install textual-terminal",
                classes="error-message",
            )
        else:
            command = self._get_command()
            if not command:
                yield Static(
                    "[bold red]Error:[/] 'claude' command not found in PATH.",
                    classes="error-message",
                )
            else:
                with Container(classes="screen-container"):
                    # Use bash -c to run the compound command
                    yield Terminal(
                        command=f"bash -c '{command}'",
                        default_colors="textual",
                        id="claude-terminal",
                    )

        status_text = "[bold]Claude Terminal[/bold]"
        if self.session_id:
            status_text += f" | Resuming: {self.session_id[:8]}..."
        else:
            status_text += " | New Session"
        status_text += " | ESC=close | Ctrl+Q=force quit"

        yield Static(status_text, classes="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount."""
        if TERMINAL_AVAILABLE and Terminal is not None:
            try:
                self._terminal = self.query_one("#claude-terminal", Terminal)
                if self._terminal is not None:
                    self._terminal.start()
            except Exception:
                pass

        if self.session_id:
            self.title = "Resume Claude Session"
            self.sub_title = f"{self.session_id[:8]}..."
        else:
            self.title = "New Claude Session"
            self.sub_title = self.cwd

    def action_close(self) -> None:
        """Close the terminal screen."""
        self.app.pop_screen()

    def action_force_close(self) -> None:
        """Force close the terminal screen."""
        self.app.pop_screen()
