"""Command list widget for displaying Claude custom commands."""

from __future__ import annotations

from rich.text import Text

from ...store.config_models import Command
from .config_list import ConfigList


class CommandList(ConfigList[Command]):
    """Widget for displaying a list of Claude custom commands."""

    TITLE = "Commands"
    ICON = ""

    @property
    def item_type(self) -> str:
        return "command"

    def _format_item(self, item: Command) -> Text:
        """Format a command for display."""
        text = Text()

        # Command name with slash
        text.append(f"/{item.name}", style="cyan bold")

        # Description preview
        if item.description:
            desc = item.description[:40]
            if len(item.description) > 40:
                desc += "..."
            text.append(f"  {desc}", style="dim")

        return text

    def _get_item_id(self, item: Command) -> str:
        """Get unique ID for a command."""
        return item.name
