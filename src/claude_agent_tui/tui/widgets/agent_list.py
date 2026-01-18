"""Agent list widget for displaying Claude agents."""

from __future__ import annotations

from rich.text import Text

from ...store.config_models import Agent
from .config_list import ConfigList


# Valid Rich color names (subset that works reliably)
VALID_COLORS = {
    "red", "green", "blue", "cyan", "magenta", "yellow", "white", "black",
    "bright_red", "bright_green", "bright_blue", "bright_cyan",
    "bright_magenta", "bright_yellow", "bright_white", "bright_black",
    "grey", "gray", "dark_red", "dark_green", "dark_blue",
}

# Map common color names to valid Rich colors
COLOR_MAP = {
    "orange": "bright_red",
    "purple": "magenta",
    "pink": "bright_magenta",
    "brown": "dark_red",
    "gold": "yellow",
    "lime": "bright_green",
    "teal": "cyan",
    "navy": "dark_blue",
}


def get_valid_color(color: str | None) -> str | None:
    """Convert a color name to a valid Rich color, or None if invalid."""
    if not color:
        return None
    color_lower = color.lower()
    if color_lower in VALID_COLORS:
        return color_lower
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    return None


class AgentList(ConfigList[Agent]):
    """Widget for displaying a list of Claude agents."""

    TITLE = "Agents"
    ICON = ""

    @property
    def item_type(self) -> str:
        return "agent"

    def _format_item(self, item: Agent) -> Text:
        """Format an agent for display."""
        text = Text()

        # Plugin indicator
        if item.is_from_plugin:
            text.append(" ", style="cyan")
        else:
            text.append("  ")

        # Agent name (with color if specified and valid)
        name_style = "bold"
        valid_color = get_valid_color(item.color)
        if valid_color:
            name_style = f"{valid_color} bold"
        text.append(item.display_name, style=name_style)

        # Model indicator
        if item.model and item.model != "inherit":
            text.append(f" [{item.model}]", style="dim")

        # Description preview
        if item.description:
            desc = item.description[:30]
            if len(item.description) > 30:
                desc += "..."
            text.append(f"\n  {desc}", style="dim")

        return text

    def _get_item_id(self, item: Agent) -> str:
        """Get unique ID for an agent."""
        if item.is_from_plugin and item.plugin_name:
            return f"{item.plugin_name}:{item.name}"
        return item.name
