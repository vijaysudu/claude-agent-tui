"""Embedded Claude terminal widget using PTY."""

from __future__ import annotations

import fcntl
import os
import pty
import shutil
import signal
import struct
import termios
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import RichLog, Input
from textual import work


class ClaudeTerminal(Container):
    """Embedded Claude terminal using PTY for full terminal emulation."""

    DEFAULT_CSS = """
    ClaudeTerminal {
        height: 100%;
        width: 100%;
        layout: vertical;
    }

    ClaudeTerminal RichLog {
        height: 1fr;
        border: solid $primary;
        scrollbar-gutter: stable;
    }

    ClaudeTerminal Input {
        dock: bottom;
        height: 3;
        border: solid $accent;
    }

    ClaudeTerminal .terminal-output {
        height: 1fr;
        background: $surface;
        color: $text;
    }
    """

    class SessionStarted(Message):
        """Message sent when the Claude session starts."""

        def __init__(self, pid: int) -> None:
            super().__init__()
            self.pid = pid

    class SessionEnded(Message):
        """Message sent when the Claude session ends."""

        def __init__(self, exit_code: int) -> None:
            super().__init__()
            self.exit_code = exit_code

    class OutputReceived(Message):
        """Message sent when output is received from Claude."""

        def __init__(self, output: str) -> None:
            super().__init__()
            self.output = output

    def __init__(self, cwd: str | None = None, **kwargs: Any) -> None:
        """Initialize the Claude terminal.

        Args:
            cwd: Working directory for the Claude session.
        """
        super().__init__(**kwargs)
        self.cwd = cwd or os.getcwd()
        self._master_fd: int | None = None
        self._slave_fd: int | None = None
        self._pid: int | None = None
        self._running = False
        self._output_log: RichLog | None = None
        self._input: Input | None = None

    def compose(self) -> ComposeResult:
        """Compose the terminal widget."""
        yield RichLog(highlight=True, markup=True, wrap=True, classes="terminal-output")
        yield Input(placeholder="Type your message to Claude...", id="terminal-input")

    def on_mount(self) -> None:
        """Handle widget mount."""
        self._output_log = self.query_one(RichLog)
        self._input = self.query_one("#terminal-input", Input)

        # Show startup message
        self._output_log.write("[bold cyan]Claude Terminal[/bold cyan]")
        self._output_log.write(f"Working directory: {self.cwd}")
        self._output_log.write("")

        # Start Claude session
        self.spawn_claude()

    def on_unmount(self) -> None:
        """Handle widget unmount."""
        self.stop_session()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "terminal-input":
            text = event.value
            event.input.value = ""

            if text:
                await self.send_input(text + "\n")
                # Echo the input
                if self._output_log:
                    self._output_log.write(f"[green]> {text}[/green]")

    @work(thread=True)
    def spawn_claude(self) -> None:
        """Spawn a Claude session in a PTY."""
        # Find the claude executable
        claude_path = shutil.which("claude")
        if not claude_path:
            if self._output_log:
                self.app.call_from_thread(
                    self._output_log.write,
                    "[red]Error: 'claude' command not found in PATH[/red]",
                )
            return

        # Create pseudo-terminal
        self._master_fd, self._slave_fd = pty.openpty()

        # Fork the process
        pid = os.fork()

        if pid == 0:
            # Child process
            os.close(self._master_fd)
            os.setsid()

            # Set up slave as controlling terminal
            os.dup2(self._slave_fd, 0)  # stdin
            os.dup2(self._slave_fd, 1)  # stdout
            os.dup2(self._slave_fd, 2)  # stderr

            if self._slave_fd > 2:
                os.close(self._slave_fd)

            # Change to working directory
            os.chdir(self.cwd)

            # Set environment
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            # Execute claude
            os.execvpe(claude_path, [claude_path], env)
        else:
            # Parent process
            os.close(self._slave_fd)
            self._slave_fd = None
            self._pid = pid
            self._running = True

            # Post message about session start
            self.app.call_from_thread(self.post_message, self.SessionStarted(pid))

            # Start reading output
            self._read_output_sync()

    def _read_output_sync(self) -> None:
        """Synchronously read output from PTY (runs in thread)."""
        if self._master_fd is None:
            return

        try:
            while self._running and self._master_fd is not None:
                try:
                    data = os.read(self._master_fd, 4096)
                    if not data:
                        break

                    # Decode and process output
                    text = data.decode("utf-8", errors="replace")
                    # Strip ANSI escape sequences for cleaner display
                    # (or keep them for color support)
                    self._write_output(text)

                except OSError:
                    break
        finally:
            self._running = False
            if self._pid:
                try:
                    _, status = os.waitpid(self._pid, os.WNOHANG)
                    exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
                except OSError:
                    exit_code = -1
                self.app.call_from_thread(self.post_message, self.SessionEnded(exit_code))

    def _write_output(self, text: str) -> None:
        """Write output to the log widget (thread-safe)."""
        if self._output_log:
            # Split by lines and write each
            for line in text.splitlines():
                if line.strip():
                    self.app.call_from_thread(self._output_log.write, line)

    async def send_input(self, text: str) -> None:
        """Send input to the Claude session.

        Args:
            text: Text to send to Claude.
        """
        if self._master_fd is not None and self._running:
            try:
                os.write(self._master_fd, text.encode("utf-8"))
            except OSError:
                pass

    def stop_session(self) -> None:
        """Stop the Claude session."""
        self._running = False

        if self._pid:
            try:
                os.kill(self._pid, signal.SIGTERM)
                os.waitpid(self._pid, 0)
            except OSError:
                pass
            self._pid = None

        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

    def set_terminal_size(self, rows: int, cols: int) -> None:
        """Set the terminal size.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        if self._master_fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def send_interrupt(self) -> None:
        """Send Ctrl+C interrupt to the Claude session."""
        if self._master_fd is not None and self._running:
            try:
                os.write(self._master_fd, b"\x03")
            except OSError:
                pass

    async def graceful_shutdown(self) -> bool:
        """Attempt graceful shutdown by sending /exit command.

        Returns:
            True if session exited gracefully, False if timed out.
        """
        import asyncio

        if not self._running:
            return True

        # Send /exit command
        await self.send_input("/exit\n")
        if self._output_log:
            self._output_log.write("[yellow]Sending /exit command...[/yellow]")

        # Wait up to 5 seconds for process to exit
        for _ in range(50):
            if not self._running:
                return True
            await asyncio.sleep(0.1)

        return False

    async def force_shutdown(self) -> None:
        """Force shutdown with double Ctrl+C then SIGTERM."""
        import asyncio

        if not self._running:
            return

        # Send first Ctrl+C
        self.send_interrupt()
        if self._output_log:
            self._output_log.write("[yellow]Sending Ctrl+C...[/yellow]")
        await asyncio.sleep(0.5)

        if not self._running:
            return

        # Send second Ctrl+C
        self.send_interrupt()
        if self._output_log:
            self._output_log.write("[yellow]Sending second Ctrl+C...[/yellow]")
        await asyncio.sleep(0.5)

        # If still running, use SIGTERM
        if self._running:
            if self._output_log:
                self._output_log.write("[red]Force stopping session...[/red]")
            self.stop_session()

    @property
    def is_running(self) -> bool:
        """Check if the session is running."""
        return self._running

    @property
    def pid(self) -> int | None:
        """Get the process ID of the session."""
        return self._pid
