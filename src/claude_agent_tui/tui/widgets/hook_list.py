"""Hook list widget for displaying Claude hooks."""

from __future__ import annotations

from rich.text import Text

from ...store.config_models import Hook
from .config_list import ConfigList


# Hook type colors
HOOK_TYPE_COLORS = {
    "UserPromptSubmit": "cyan",
    "PreToolUse": "yellow",
    "PostToolUse": "green",
    "Notification": "blue",
    "Stop": "red",
}


class HookList(ConfigList[Hook]):
    """Widget for displaying a list of Claude hooks."""

    TITLE = "Hooks"
    ICON = ""

    @property
    def item_type(self) -> str:
        return "hook"

    def _format_item(self, item: Hook) -> Text:
        """Format a hook for display."""
        text = Text()

        # Hook type with color
        color = HOOK_TYPE_COLORS.get(item.hook_type, "white")
        text.append(f"{item.hook_type}", style=f"{color} bold")

        # Matcher if present
        if item.matcher:
            text.append(f" [{item.matcher}]", style="dim")

        # Command preview
        cmd_preview = item.command[:30]
        if len(item.command) > 30:
            cmd_preview += "..."
        text.append(f"\n  $ {cmd_preview}", style="dim")

        return text

    def _get_item_id(self, item: Hook) -> str:
        """Get unique ID for a hook."""
        # Create ID from type and matcher/command
        if item.matcher:
            return f"{item.hook_type}:{item.matcher}"
        return f"{item.hook_type}:{hash(item.command) % 10000}"
