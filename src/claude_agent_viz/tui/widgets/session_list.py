"""Session list widget for displaying Claude sessions."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...store.models import Session


class SessionList(OptionList):
    """Widget for displaying a list of Claude sessions."""

    DEFAULT_CSS = """
    SessionList {
        height: 100%;
        width: 100%;
        border: solid $primary;
    }

    SessionList:focus {
        border: solid $accent;
    }

    SessionList > .option-list--option-highlighted {
        background: $accent;
    }
    """

    class SessionSelected(Message):
        """Message sent when a session is selected."""

        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sessions: dict[str, Session] = {}

    def set_sessions(self, sessions: list[Session]) -> None:
        """Update the list of sessions.

        Args:
            sessions: List of sessions to display.
        """
        self._sessions = {s.session_id: s for s in sessions}
        self.clear_options()

        for session in sessions:
            option_text = self._format_session(session)
            self.add_option(Option(option_text, id=session.session_id))

    def _format_session(self, session: Session) -> Text:
        """Format a session for display.

        Args:
            session: The session to format.

        Returns:
            Formatted text for display.
        """
        text = Text()

        # Active indicator
        if session.is_active:
            text.append(" ", style="green bold")
        else:
            text.append("  ", style="dim")

        # Project name (derived from path)
        project_name = session.project_name
        if project_name and project_name != "unknown":
            text.append(project_name[:20], style="cyan bold")
            text.append("\n")
        else:
            text.append(session.display_name, style="bold")
            text.append("\n")

        # Summary (first user message)
        if session.summary:
            summary = session.summary.strip().replace("\n", " ")[:50]
            text.append(f"  {summary}", style="dim italic")
            if len(session.summary.strip()) > 50:
                text.append("...", style="dim")
            text.append("\n")

        # Tool count and timestamp
        tool_info = f"  {session.tool_count} tools"
        text.append(tool_info, style="dim")

        # Relative time if available
        if session.start_time:
            time_str = self._format_relative_time(session.start_time)
            text.append(f" | {time_str}", style="dim")

        return text

    def _format_relative_time(self, timestamp: str) -> str:
        """Format a timestamp as relative time.

        Args:
            timestamp: ISO format timestamp.

        Returns:
            Relative time string like '2h ago'.
        """
        from datetime import datetime

        try:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            delta = now - dt

            seconds = delta.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                mins = int(seconds / 60)
                return f"{mins}m ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours}h ago"
            else:
                days = int(seconds / 86400)
                return f"{days}d ago"
        except Exception:
            return ""

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight (single click/arrow key)."""
        if event.option_id:
            self.post_message(self.SessionSelected(str(event.option_id)))
