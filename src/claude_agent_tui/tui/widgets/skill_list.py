"""Skill list widget for displaying Claude skills."""

from __future__ import annotations

from rich.text import Text

from ...store.config_models import Skill
from .config_list import ConfigList


class SkillList(ConfigList[Skill]):
    """Widget for displaying a list of Claude skills."""

    TITLE = "Skills"
    ICON = ""

    @property
    def item_type(self) -> str:
        return "skill"

    def _format_item(self, item: Skill) -> Text:
        """Format a skill for display."""
        text = Text()

        # Plugin indicator
        if item.is_from_plugin:
            text.append(" ", style="cyan")
        else:
            text.append("  ")

        # Skill name
        text.append(item.display_name, style="bold")

        # Description preview
        if item.description:
            desc = item.description[:35]
            if len(item.description) > 35:
                desc += "..."
            text.append(f"  {desc}", style="dim")

        return text

    def _get_item_id(self, item: Skill) -> str:
        """Get unique ID for a skill."""
        if item.is_from_plugin and item.plugin_name:
            return f"{item.plugin_name}:{item.name}"
        return item.name
