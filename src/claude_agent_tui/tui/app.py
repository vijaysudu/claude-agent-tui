"""Main TUI application for Claude Agent Visualizer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane

from .widgets.session_list import SessionList
from .widgets.tool_list import ToolList
from .widgets.detail_panel import DetailPanel
from .widgets.config_list import ConfigList
from .widgets.skill_list import SkillList
from .widgets.hook_list import HookList
from .widgets.command_list import CommandList
from .widgets.agent_list import AgentList
from .widgets.mcp_server_list import MCPServerList
from .screens.new_session_screen import NewSessionScreen
from ..state import AppState
from ..store.config_models import Skill, Hook, Command, Agent, MCPServer
from ..spawner.terminal import spawn_session


class ClaudeAgentVizApp(App):
    """Main application for visualizing Claude agent sessions."""

    TITLE = "Claude Agent Visualizer"
    SUB_TITLE = "Monitor and interact with Claude sessions"

    CSS = """
    #main-layout {
        height: 1fr;
    }

    #content-area {
        height: 1fr;
    }

    .sidebar {
        width: 35;
        height: 100%;
    }

    .main-content {
        width: 1fr;
        height: 100%;
    }

    .sessions-panel {
        height: 40%;
        border: solid $primary;
    }

    .tools-panel {
        height: 60%;
        border: solid $primary;
    }

    .detail-area {
        height: 100%;
        width: 100%;
    }

    #status-indicator {
        height: 1;
        background: $primary-background;
        padding: 0 1;
        color: $text;
    }

    /* Tabbed sidebar styling */
    .sidebar TabbedContent {
        height: 100%;
    }

    .sidebar ContentSwitcher {
        height: 1fr;
    }

    .sidebar TabPane {
        padding: 0;
        height: 100%;
    }

    #sessions-tab {
        height: 100%;
    }

    #config-tab {
        height: 100%;
        padding: 0;
    }

    #config-scroll {
        height: 100%;
        scrollbar-gutter: stable;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("n", "new_session", "New Session", show=True),
        Binding("c", "resume_session", "Resume", show=True),
        Binding("k", "kill_session", "Kill Session", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "back_to_session", "Back", show=True),
        Binding("question_mark", "help", "Help", show=True, key_display="?"),
    ]

    def __init__(
        self,
        sessions_dir: Path | None = None,
        demo_mode: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the application.

        Args:
            sessions_dir: Directory containing session JSONL files.
            demo_mode: Whether to run in demo mode with sample data.
        """
        super().__init__(**kwargs)
        self.sessions_dir = sessions_dir
        self.demo_mode = demo_mode
        self.state = AppState()
        self._watcher = None

        # Register state update callback
        self.state.add_update_listener(self._on_state_update)

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()

        with Vertical(id="main-layout"):
            with Horizontal(id="content-area"):
                # Sidebar with tabbed navigation
                with Vertical(classes="sidebar"):
                    with TabbedContent():
                        # Sessions tab
                        with TabPane("Sessions", id="sessions-tab"):
                            with Container(classes="sessions-panel"):
                                yield Static(" Sessions", classes="panel-title")
                                yield SessionList(id="session-list")

                            with Container(classes="tools-panel"):
                                yield Static(" Tools", classes="panel-title")
                                yield ToolList(id="tool-list")

                        # Config tab
                        with TabPane("Config", id="config-tab"):
                            with VerticalScroll(id="config-scroll"):
                                yield SkillList(id="skill-list")
                                yield HookList(id="hook-list")
                                yield CommandList(id="command-list")
                                yield AgentList(id="agent-list")
                                yield MCPServerList(id="mcp-server-list")

                # Main content area
                with Container(classes="main-content"):
                    yield DetailPanel(id="detail-panel", classes="detail-area")

            # Status indicator (above footer)
            yield Static(
                self._get_status_text(),
                id="status-indicator",
                classes="status-indicator",
            )

        yield Footer()

    def on_mount(self) -> None:
        """Handle application mount."""
        if self.demo_mode:
            self._load_demo_data()
        elif self.sessions_dir:
            self._load_sessions()
            self._start_watcher()

        # Load Claude configuration
        self._load_configs()

    def on_unmount(self) -> None:
        """Handle application unmount."""
        self._stop_watcher()
        # Clean up any spawned processes to prevent orphans
        results = self.state.cleanup_spawned_processes()
        for pid, success in results:
            if success:
                self.log.info(f"Cleaned up spawned process {pid}")
            else:
                self.log.warning(f"Failed to clean up process {pid} (may have already exited)")

    def _start_watcher(self) -> None:
        """Start watching for new session files."""
        if not self.sessions_dir or self.demo_mode:
            return

        try:
            from ..discovery.watcher import SessionWatcher

            self._watcher = SessionWatcher(
                directory=self.sessions_dir,
                on_change=self._on_session_file_changed,
                on_new=self._on_session_file_created,
            )
            self._watcher.start()
        except ImportError:
            # watchdog not installed
            pass

    def _stop_watcher(self) -> None:
        """Stop the file watcher."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def _on_session_file_changed(self, path: Path) -> None:
        """Handle session file modification."""
        # Skip subagent files
        if "subagents" in str(path):
            return
        # Reload the session and refresh UI
        self.call_from_thread(self._reload_session, path)

    def _on_session_file_created(self, path: Path) -> None:
        """Handle new session file creation."""
        # Skip subagent files
        if "subagents" in str(path):
            return
        # Load the new session and refresh UI
        self.call_from_thread(self._load_new_session, path)

    def _reload_session(self, path: Path) -> None:
        """Reload a session from file (called from main thread)."""
        from ..state import get_active_claude_directories

        active_dirs = get_active_claude_directories()
        self.state.load_session(path, active_dirs)
        self._fix_active_session_detection(active_dirs)
        self._update_session_list()
        self._update_status()

        # If the reloaded session is currently selected, refresh tool list and detail panel
        selected = self.state.selected_session
        if selected and selected.session_path == path:
            self._update_tool_list()
            # Refresh detail panel with updated session or tool data
            if self.state.selected_tool_id:
                self._update_detail_panel()
            else:
                self._show_session_details()

    def _load_new_session(self, path: Path) -> None:
        """Load a new session file (called from main thread)."""
        from ..state import get_active_claude_directories

        active_dirs = get_active_claude_directories()
        self.state.load_session(path, active_dirs)
        self._fix_active_session_detection(active_dirs)
        self._update_session_list()
        self._update_status()

    def _get_status_text(self) -> str:
        """Get the status bar text."""
        active_count = len([s for s in self.state.sessions if s.is_active])
        return f" Active Sessions: {active_count}"

    def _update_status(self) -> None:
        """Update the status indicator."""
        try:
            status = self.query_one("#status-indicator", Static)
            status.update(self._get_status_text())
        except Exception:
            pass

    def _on_state_update(self) -> None:
        """Handle state updates."""
        self._update_status()

    def _load_sessions(self) -> None:
        """Load sessions from the sessions directory."""
        if not self.sessions_dir or not self.sessions_dir.exists():
            return

        from ..discovery.parser import parse_sessions_in_directory
        from ..state import get_active_claude_directories

        # Get active Claude directories once for all sessions
        active_directories = get_active_claude_directories()

        parsed = parse_sessions_in_directory(self.sessions_dir)
        for p in parsed:
            self.state.load_session(p.session_path, active_directories)

        # Fix: Only the most recent session per active directory should be active
        # Group sessions by their resolved project path
        self._fix_active_session_detection(active_directories)

        # Update session list
        self._update_session_list()

    def _fix_active_session_detection(self, active_directories: set[str]) -> None:
        """Ensure sessions are marked active based on running Claude processes.

        Uses PIDs from pgrep to identify active Claude processes, then matches
        them to the most recently modified session files in each directory.

        If there are N PIDs in a directory, we mark the N most recently modified
        sessions in that directory as active.
        """
        from pathlib import Path
        from ..state import get_active_claude_processes

        # Get active processes (directory -> list of PIDs)
        active_processes = get_active_claude_processes()

        # Resolve active directories to their PIDs
        resolved_active: dict[str, list[int]] = {}
        for d, pids in active_processes.items():
            try:
                resolved_active[str(Path(d).resolve())] = pids
            except (OSError, ValueError):
                continue

        # First pass: mark all sessions inactive, then selectively activate
        for session in self.state.sessions:
            session.is_active = False
            session.pid = None

        # For each active directory, find sessions and mark N as active
        # where N = number of PIDs in that directory
        for resolved_path, pids in resolved_active.items():
            # Find sessions matching this directory
            matching_sessions = []
            for session in self.state.sessions:
                if not session.project_path:
                    continue
                try:
                    session_path = str(Path(session.project_path).resolve())
                    if session_path == resolved_path:
                        matching_sessions.append(session)
                except (OSError, ValueError):
                    continue

            if not matching_sessions:
                continue

            # Sort by file modification time - most recent first
            def get_mtime(s):
                try:
                    return s.session_path.stat().st_mtime
                except (OSError, AttributeError):
                    return 0

            matching_sessions.sort(key=get_mtime, reverse=True)

            # Mark N sessions as active, where N = number of PIDs
            # The most recently modified sessions are assumed to correspond
            # to the active processes
            num_active = min(len(pids), len(matching_sessions))
            for i in range(num_active):
                matching_sessions[i].is_active = True
                matching_sessions[i].pid = pids[i]

    def _load_demo_data(self) -> None:
        """Load demo data for testing."""
        from ..demo import create_demo_sessions

        sessions = create_demo_sessions()
        self.state.sessions = sessions

        self._update_session_list()

    def _update_session_list(self) -> None:
        """Update the session list widget."""
        try:
            session_list = self.query_one("#session-list", SessionList)
            session_list.set_sessions(self.state.filtered_sessions)
        except Exception:
            pass

    def _update_tool_list(self) -> None:
        """Update the tool list widget."""
        try:
            tool_list = self.query_one("#tool-list", ToolList)
            session = self.state.selected_session
            if session:
                tool_list.set_tools(session.tool_uses)
            else:
                tool_list.set_tools([])
        except Exception:
            pass

    def _update_detail_panel(self) -> None:
        """Update the detail panel widget."""
        try:
            detail_panel = self.query_one("#detail-panel", DetailPanel)
            tool = self.state.selected_tool
            detail_panel.show_tool(tool)
        except Exception:
            pass

    def _show_session_details(self) -> None:
        """Show session details in the detail panel."""
        try:
            detail_panel = self.query_one("#detail-panel", DetailPanel)
            session = self.state.selected_session
            detail_panel.show_session(session)
        except Exception:
            pass

    def _show_welcome(self) -> None:
        """Show welcome/base state in the detail panel."""
        try:
            detail_panel = self.query_one("#detail-panel", DetailPanel)
            detail_panel.show_welcome()
        except Exception:
            pass

    def _load_configs(self) -> None:
        """Load Claude configuration items."""
        self.state.load_configs()
        self._update_config_lists()

    def _update_config_lists(self) -> None:
        """Update all config list widgets."""
        try:
            skill_list = self.query_one("#skill-list", SkillList)
            skill_list.set_items(self.state.skills)
        except Exception:
            pass

        try:
            hook_list = self.query_one("#hook-list", HookList)
            hook_list.set_items(self.state.hooks)
        except Exception:
            pass

        try:
            command_list = self.query_one("#command-list", CommandList)
            command_list.set_items(self.state.commands)
        except Exception:
            pass

        try:
            agent_list = self.query_one("#agent-list", AgentList)
            agent_list.set_items(self.state.agents)
        except Exception:
            pass

        try:
            mcp_server_list = self.query_one("#mcp-server-list", MCPServerList)
            mcp_server_list.set_items(self.state.mcp_servers)
        except Exception:
            pass

    def _show_config_details(self) -> None:
        """Show selected config item details in the detail panel."""
        detail_panel = self.query_one("#detail-panel", DetailPanel)
        item = self.state.get_selected_config()

        if isinstance(item, Skill):
            detail_panel.show_skill(item)
        elif isinstance(item, Hook):
            detail_panel.show_hook(item)
        elif isinstance(item, Command):
            detail_panel.show_command(item)
        elif isinstance(item, Agent):
            detail_panel.show_agent(item)
        elif isinstance(item, MCPServer):
            detail_panel.show_mcp_server(item)

    def on_session_list_session_selected(
        self, event: SessionList.SessionSelected
    ) -> None:
        """Handle session selection."""
        # Clear config selection when selecting a session
        self.state.clear_config_selection()
        self.state.select_session(event.session_id)
        self._update_tool_list()
        # Show session info in detail panel
        self._show_session_details()

    def on_tool_list_tool_selected(self, event: ToolList.ToolSelected) -> None:
        """Handle tool selection."""
        self.state.select_tool(event.tool_use_id)
        self._update_detail_panel()

    def on_config_list_item_selected(self, event: ConfigList.ItemSelected) -> None:
        """Handle config item selection."""
        self.state.select_config_item(event.item_type, event.item_id)
        self._show_config_details()

    def on_detail_panel_reply_submitted(
        self, event: DetailPanel.ReplySubmitted
    ) -> None:
        """Handle reply submission from detail panel."""
        session = self.state.selected_session
        if not session:
            return

        # Get the project path for the session
        cwd = session.project_path or os.getcwd()

        from ..spawner.terminal import spawn_resume_session
        result = spawn_resume_session(
            cwd=cwd,
            session_id=event.session_id,
        )

        if result.success:
            self.notify("Opening terminal to resume session...", severity="information")
        else:
            self.notify(f"Failed to resume: {result.error}", severity="error")

    def action_new_session(self) -> None:
        """Spawn a new Claude session."""
        # Show dialog to get project directory
        self.push_screen(NewSessionScreen(default_path=os.getcwd()), self._on_new_session_path)

    def _on_new_session_path(self, path: str | None) -> None:
        """Handle the result from NewSessionScreen."""
        if path is None:
            # User cancelled
            return

        result = spawn_session(path)
        if result.success:
            self.notify(f"New Claude session started in {path}", severity="information")
        else:
            self.notify(
                f"Failed to start session: {result.error}",
                severity="error",
            )

    def action_kill_session(self) -> None:
        """Kill the currently selected session."""
        session = self.state.selected_session
        if not session:
            self.notify("No session selected", severity="warning")
            return

        from ..process import kill_session, find_claude_processes, kill_by_pid

        # First try to find by session ID
        success, message = kill_session(session.session_id)

        if success:
            self.notify(f"Session killed: {message}", severity="information")
            session.is_active = False
            session.pid = None
            self._update_session_list()
        else:
            # If no matching session found, show running processes
            processes = find_claude_processes()
            if processes:
                # Try to kill by PID if we have one stored
                if session.pid:
                    success, message = kill_by_pid(session.pid)
                    if success:
                        self.notify(f"Session killed: {message}", severity="information")
                        session.is_active = False
                        session.pid = None
                        self._update_session_list()
                        return

                # Show info about running processes
                proc_info = ", ".join(f"PID {p.pid}" for p in processes[:3])
                self.notify(
                    f"Could not match session. Running Claude processes: {proc_info}",
                    severity="warning",
                )
            else:
                self.notify("No running Claude sessions found", severity="information")

    def action_back_to_session(self) -> None:
        """Go back: tool view → session view → config view → base state."""
        if self.state.selected_tool_id:
            # From tool view, go back to session view
            self.state.selected_tool_id = None
            self._show_session_details()
        elif self.state.selected_session_id:
            # From session view, go back to base state (nothing selected)
            self.state.selected_session_id = None
            self._update_tool_list()  # Clear tools list
            self._show_welcome()
        elif self.state.selected_config_id:
            # From config view, go back to base state
            self.state.clear_config_selection()
            self._show_welcome()

    def action_refresh(self) -> None:
        """Refresh the session list."""
        if self.demo_mode:
            self._load_demo_data()
        else:
            self._load_sessions()
        self.notify("Sessions refreshed", severity="information")

    def action_resume_session(self) -> None:
        """Resume the selected session."""
        session = self.state.selected_session
        if not session:
            self.notify("No session selected", severity="warning")
            return

        # Get the project path for the session
        cwd = session.project_path or os.getcwd()

        from ..spawner.terminal import spawn_resume_session
        result = spawn_resume_session(
            cwd=cwd,
            session_id=session.session_id,
        )

        if result.success:
            self.notify("Opening terminal to resume session...", severity="information")
        else:
            self.notify(f"Failed to resume: {result.error}", severity="error")

    def action_help(self) -> None:
        """Show help information."""
        help_text = """
[bold]Claude Agent Visualizer[/bold]

[bold]Keybindings:[/bold]
  [cyan]n[/cyan] - Start new Claude session
  [cyan]c[/cyan] - Resume selected session
  [cyan]k[/cyan] - Kill selected session
  [cyan]r[/cyan] - Refresh sessions
  [cyan]ESC[/cyan] - Back to session view
  [cyan]q[/cyan] - Quit
  [cyan]?[/cyan] - Show this help

[bold]Active Sessions:[/bold]
  Sessions with a running Claude process are shown with a green indicator.
  New sessions and resumes open in your preferred terminal emulator.
"""
        self.notify(help_text, timeout=10)
