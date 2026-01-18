"""Screen for starting a new Claude session."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button


class NewSessionScreen(ModalScreen[str | None]):
    """Modal screen for entering project directory for new session."""

    DEFAULT_CSS = """
    NewSessionScreen {
        align: center middle;
    }

    NewSessionScreen > Container {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    NewSessionScreen #title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        color: $text;
    }

    NewSessionScreen #subtitle {
        text-align: center;
        color: $text-muted;
        padding-bottom: 1;
    }

    NewSessionScreen #path-input {
        margin: 1 0;
    }

    NewSessionScreen #buttons {
        height: auto;
        align: center middle;
        padding-top: 1;
    }

    NewSessionScreen Button {
        margin: 0 1;
    }

    NewSessionScreen #error-message {
        color: $error;
        text-align: center;
        height: 1;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, default_path: str | None = None, **kwargs) -> None:
        """Initialize the screen.

        Args:
            default_path: Default path to show in the input.
        """
        super().__init__(**kwargs)
        self._default_path = default_path or os.getcwd()

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        with Container():
            yield Static(" New Claude Session", id="title")
            yield Static("Enter the project directory:", id="subtitle")
            yield Input(
                value=self._default_path,
                placeholder="Enter project path...",
                id="path-input",
            )
            yield Static("", id="error-message")
            with Container(id="buttons"):
                yield Button("Start", variant="primary", id="start-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#path-input", Input).focus()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        self._validate_and_start()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "start-btn":
            self._validate_and_start()
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)

    def _validate_and_start(self) -> None:
        """Validate the path and start the session."""
        path_input = self.query_one("#path-input", Input)
        error_label = self.query_one("#error-message", Static)

        path_str = path_input.value.strip()

        # Expand ~ and environment variables
        path_str = os.path.expanduser(path_str)
        path_str = os.path.expandvars(path_str)

        # Validate path
        path = Path(path_str)

        if not path_str:
            error_label.update("Please enter a directory path")
            return

        if not path.exists():
            error_label.update(f"Path does not exist: {path_str}")
            return

        if not path.is_dir():
            error_label.update(f"Path is not a directory: {path_str}")
            return

        # Clear error and return the path
        error_label.update("")
        self.dismiss(str(path.resolve()))
