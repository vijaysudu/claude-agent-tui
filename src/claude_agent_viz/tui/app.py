"""Main Textual application for Claude Agent Visualizer.

This is the entry point for the TUI dashboard.
"""

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer

from ..discovery import SessionWatcher
from ..state import AppState
from .widgets.detail_panel import DetailPanel
from .widgets.session_tree import SessionTree
from .widgets.status_bar import StatusBar


# Refresh interval in seconds
REFRESH_INTERVAL = 5.0


class ClaudeAgentVizApp(App):
    """Claude Agent Visualizer TUI application."""

    TITLE = "Claude Agent Visualizer"

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
    }

    #tree-container {
        width: 40%;
        min-width: 30;
    }

    #detail-container {
        width: 60%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("n", "new_session", "New Session"),
        Binding("space", "toggle_expand", "Expand/Collapse"),
        Binding("tab", "next_session", "Next Session"),
        Binding("shift+tab", "prev_session", "Prev Session"),
        Binding("?", "show_help", "Help"),
    ]

    def __init__(self, state: AppState | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state = state or AppState()
        self._demo_mode = state is not None
        self._watcher: SessionWatcher | None = None
        self._refresh_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Horizontal(id="main-container"):
            yield SessionTree(id="tree-container")
            yield DetailPanel(id="detail-container")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app when it mounts."""
        # Set up state observer
        self.state.add_observer(self._on_state_change)

        # Initial data load
        if not self._demo_mode:
            self._load_initial_data()
            # Start background tasks
            self.run_worker(self._start_file_watcher())
            self.run_worker(self._periodic_refresh())
        else:
            self._update_from_state()

    def _load_initial_data(self) -> None:
        """Load initial session data from files."""
        from ..logging import get_logger
        log = get_logger("app")

        try:
            count = self.state.refresh_from_files(max_sessions=30, max_age_hours=24)
            log.info(f"Loaded {count} sessions from files")
            self._update_from_state()
            self.notify(f"Loaded {count} sessions")
        except Exception as e:
            log.error(f"Failed to load sessions: {e}")
            self.notify(f"Failed to load sessions: {e}", severity="error")

    async def _start_file_watcher(self) -> None:
        """Start watching for session file changes."""
        from ..logging import get_logger
        log = get_logger("app")

        try:
            watcher = SessionWatcher(
                on_session_change=self._on_session_change,
                on_new_session=self._on_new_session,
            )
            await watcher.start()
            self._watcher = watcher
            log.info("File watcher started")
        except Exception as e:
            log.error(f"Failed to start file watcher: {e}")
            # Continue without watcher - periodic refresh will still work

    async def _periodic_refresh(self) -> None:
        """Periodically refresh session data."""
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            try:
                self.state.refresh_from_files(max_sessions=30, max_age_hours=24)
                self.call_from_thread(self._update_from_state)
            except Exception:
                pass

    def _on_session_change(self, session_info) -> None:
        """Handle session file change from watcher."""
        self.state.update_session(session_info)
        self.call_from_thread(self._update_from_state)

    def _on_new_session(self, session_info) -> None:
        """Handle new session from watcher."""
        self.state.update_session(session_info)
        self.call_from_thread(self._update_from_state)

    def _on_state_change(self) -> None:
        """Called when state changes."""
        self._update_from_state()

    def _update_from_state(self) -> None:
        """Update all widgets from current state."""
        # Update status bar
        status_bar = self.query_one(StatusBar)
        status_bar.update_from_state(self.state)

        # Update tree
        tree = self.query_one(SessionTree)
        tree.update_from_state(self.state)

    def on_session_tree_node_selected(self, event: SessionTree.NodeSelected) -> None:
        """Handle tree node selection."""
        detail_panel = self.query_one(DetailPanel)
        detail_panel.show(event.data)

    # --- Actions ---

    def action_refresh(self) -> None:
        """Manually refresh session data."""
        try:
            count = self.state.refresh_from_files(max_sessions=30, max_age_hours=24)
            self._update_from_state()
            self.notify(f"Refreshed {count} sessions")
        except Exception as e:
            self.notify(f"Refresh failed: {e}", severity="error")

    def action_new_session(self) -> None:
        """Spawn a new Claude Code session."""
        from ..spawner import spawn_session, detect_terminal

        # For now, spawn in current working directory
        # TODO: Add directory picker dialog
        import os
        cwd = os.getcwd()

        terminal = detect_terminal()
        if terminal.value == "unknown":
            self.notify("No supported terminal found", severity="error")
            return

        try:
            if spawn_session(cwd, terminal):
                self.notify(f"Spawned new session in {terminal.value}")
            else:
                self.notify("Failed to spawn session", severity="error")
        except Exception as e:
            self.notify(f"Error spawning session: {e}", severity="error")

    def action_toggle_expand(self) -> None:
        """Toggle expand/collapse of selected tree node."""
        tree = self.query_one(SessionTree)
        if tree.cursor_node:
            tree.cursor_node.toggle()

    def action_next_session(self) -> None:
        """Jump to next session in tree."""
        tree = self.query_one(SessionTree)
        for node in tree.root.children:
            if tree.cursor_node and node.line > tree.cursor_node.line:
                tree.select_node(node)
                break

    def action_prev_session(self) -> None:
        """Jump to previous session in tree."""
        tree = self.query_one(SessionTree)
        prev_node = None
        for node in tree.root.children:
            if tree.cursor_node and node.line >= tree.cursor_node.line:
                break
            prev_node = node
        if prev_node:
            tree.select_node(prev_node)

    def action_show_help(self) -> None:
        """Show help information."""
        help_text = (
            "Keybindings:\n"
            "  q: Quit\n"
            "  r: Refresh sessions\n"
            "  n: New session in current directory\n"
            "  space: Expand/collapse node\n"
            "  tab/shift+tab: Navigate sessions"
        )
        self.notify(help_text, timeout=10)

    async def action_quit(self) -> None:
        """Quit the app and clean up."""
        # Stop file watcher if running
        if self._watcher:
            await self._watcher.stop()
        self.exit()


def run_app(state: AppState | None = None) -> None:
    """Run the visualizer application."""
    app = ClaudeAgentVizApp(state=state)
    app.run()
