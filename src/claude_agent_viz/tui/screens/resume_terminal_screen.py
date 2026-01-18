"""Terminal screen for resuming existing Claude sessions."""

from __future__ import annotations

import os
import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Container

from ..widgets.resume_terminal import ResumeTerminal


class ResumeTerminalScreen(Screen):
    """Full-screen modal for resuming a Claude session."""

    DEFAULT_CSS = """
    ResumeTerminalScreen {
        background: $surface;
    }

    ResumeTerminalScreen .screen-container {
        height: 100%;
        width: 100%;
        padding: 0;
    }

    ResumeTerminalScreen ResumeTerminal {
        height: 1fr;
    }

    ResumeTerminalScreen .status-bar {
        dock: bottom;
        height: 1;
        background: $accent;
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
        session_id: str,
        cwd: str | None = None,
        initial_message: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the resume terminal screen.

        Args:
            session_id: The session ID to resume.
            cwd: Working directory for the session.
            initial_message: Optional message to send after session starts.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.session_id = session_id
        self.cwd = cwd or os.getcwd()
        self.initial_message = initial_message
        self._terminal: ResumeTerminal | None = None
        self._interrupt_count = 0
        self._last_interrupt_time = 0.0

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield ResumeTerminal(
                session_id=self.session_id,
                cwd=self.cwd,
                initial_message=self.initial_message,
            )
        yield Static(
            f"[bold]Resuming Session[/bold] | {self.session_id[:8]}... | ESC=exit | Ctrl+C x2=force",
            classes="status-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount."""
        self._terminal = self.query_one(ResumeTerminal)
        self.title = "Resume Claude Session"
        self.sub_title = f"{self.session_id[:8]}..."

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

    def on_resume_terminal_session_started(
        self, event: ResumeTerminal.SessionStarted
    ) -> None:
        """Handle session start - track PID for cleanup."""
        # Track the PID so it can be cleaned up if app exits
        if hasattr(self.app, 'state'):
            self.app.state.track_spawned_pid(event.pid)

    def on_resume_terminal_session_ended(
        self, event: ResumeTerminal.SessionEnded
    ) -> None:
        """Handle session end."""
        # Untrack the PID since process exited normally
        if self._terminal and self._terminal._pid and hasattr(self.app, 'state'):
            self.app.state.untrack_spawned_pid(self._terminal._pid)

        self.notify(
            f"Claude session ended with code {event.exit_code}",
            severity="information" if event.exit_code == 0 else "warning",
        )
