"""Full-screen embedded Claude terminal."""

from __future__ import annotations

import os
import time
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Container

from ..widgets.claude_terminal import ClaudeTerminal


class TerminalScreen(Screen):
    """Full-screen modal for embedded Claude session."""

    DEFAULT_CSS = """
    TerminalScreen {
        background: $surface;
    }

    TerminalScreen .screen-container {
        height: 100%;
        width: 100%;
        padding: 0;
    }

    TerminalScreen ClaudeTerminal {
        height: 1fr;
    }

    TerminalScreen .status-bar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close (graceful)", show=True),
        Binding("ctrl+c", "interrupt", "Ctrl+C (x2 to force)", show=True),
        Binding("ctrl+q", "force_close", "Force Quit", show=True),
    ]

    def __init__(
        self,
        cwd: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the terminal screen.

        Args:
            cwd: Working directory for the Claude session.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.cwd = cwd or os.getcwd()
        self._terminal: ClaudeTerminal | None = None
        self._interrupt_count = 0
        self._last_interrupt_time = 0.0

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield ClaudeTerminal(cwd=self.cwd)
        yield Static(
            f"[bold]Claude Session[/bold] | {self.cwd} | ESC=exit | Ctrl+C x2=force",
            classes="status-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount."""
        self._terminal = self.query_one(ClaudeTerminal)
        self.title = "Claude Terminal"
        self.sub_title = self.cwd

    async def action_close(self) -> None:
        """Close the terminal screen with graceful shutdown."""
        if self._terminal and self._terminal.is_running:
            self.notify("Sending /exit to Claude...")
            success = await self._terminal.graceful_shutdown()
            if success:
                self.notify("Session exited gracefully")
            else:
                self.notify("Session didn't exit, force stopping...", severity="warning")
                self._terminal.stop_session()
        self.app.pop_screen()

    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude (double-press to force kill)."""
        current_time = time.time()

        # Reset counter if more than 2 seconds passed
        if current_time - self._last_interrupt_time > 2:
            self._interrupt_count = 0

        self._interrupt_count += 1
        self._last_interrupt_time = current_time

        if self._interrupt_count == 1:
            # First press: normal interrupt
            if self._terminal:
                self._terminal.send_interrupt()
            self.notify("Sent Ctrl+C (press again within 2s to force quit)")

        elif self._interrupt_count >= 2:
            # Second+ press: force kill
            self.notify("Force killing session...", severity="warning")
            self.run_worker(self._force_kill())

    async def _force_kill(self) -> None:
        """Force kill the session."""
        if self._terminal:
            await self._terminal.force_shutdown()
        self.app.pop_screen()

    def action_force_close(self) -> None:
        """Force close immediately with SIGTERM."""
        if self._terminal:
            self._terminal.stop_session()
        self.app.pop_screen()

    def on_claude_terminal_session_ended(
        self, event: ClaudeTerminal.SessionEnded
    ) -> None:
        """Handle session end."""
        self.notify(
            f"Claude session ended with code {event.exit_code}",
            severity="information" if event.exit_code == 0 else "warning",
        )
