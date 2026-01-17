"""Status bar widget for Claude Agent Visualizer.

Shows global statistics at the top of the screen.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from ...state import AppState


class StatusBar(Widget):
    """Status bar showing session and agent counts."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    StatusBar .title {
        color: $primary;
        text-style: bold;
    }

    StatusBar .stats {
        color: $text;
    }

    StatusBar .alert {
        color: $warning;
        text-style: bold;
    }

    StatusBar .separator {
        color: $text-muted;
    }
    """

    sessions_count: reactive[int] = reactive(0)
    agents_count: reactive[int] = reactive(0)
    pending_inputs: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Claude Agent Visualizer", classes="title")
            yield Static(" | ", classes="separator")
            yield Static(id="sessions-stat", classes="stats")
            yield Static(" | ", classes="separator")
            yield Static(id="agents-stat", classes="stats")
            yield Static(id="alert-stat", classes="alert")

    def on_mount(self) -> None:
        """Update stats on mount."""
        self._update_display()

    def watch_sessions_count(self, count: int) -> None:
        """React to sessions count change."""
        self._update_display()

    def watch_agents_count(self, count: int) -> None:
        """React to agents count change."""
        self._update_display()

    def watch_pending_inputs(self, count: int) -> None:
        """React to pending inputs change."""
        self._update_display()

    def _update_display(self) -> None:
        """Update the display with current values."""
        try:
            sessions_widget = self.query_one("#sessions-stat", Static)
            sessions_widget.update(f"Sessions: {self.sessions_count}")

            agents_widget = self.query_one("#agents-stat", Static)
            agents_widget.update(f"Agents: {self.agents_count}")

            alert_widget = self.query_one("#alert-stat", Static)
            if self.pending_inputs > 0:
                alert_widget.update(f" | {self.pending_inputs} awaiting input")
            else:
                alert_widget.update("")
        except Exception:
            # Widget might not be mounted yet
            pass

    def update_from_state(self, state: AppState) -> None:
        """Update stats from application state."""
        self.sessions_count = len(state.active_sessions)
        self.agents_count = state.total_agents
        self.pending_inputs = state.pending_inputs
