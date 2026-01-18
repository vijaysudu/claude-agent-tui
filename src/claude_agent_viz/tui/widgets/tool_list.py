"""Tool list widget for displaying tool uses in a session."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...store.models import ToolUse, ToolStatus


# Status indicators
STATUS_ICONS = {
    ToolStatus.PENDING: ("", "yellow"),
    ToolStatus.RUNNING: ("", "blue"),
    ToolStatus.COMPLETED: ("", "green"),
    ToolStatus.ERROR: ("", "red"),
}

# Tool type icons
TOOL_ICONS = {
    "Read": "",
    "Edit": "",
    "Write": "",
    "Bash": "",
    "Grep": "",
    "Glob": "",
    "Task": "",
    "WebFetch": "",
    "AskUserQuestion": "",
}


class ToolList(OptionList):
    """Widget for displaying a list of tool uses."""

    DEFAULT_CSS = """
    ToolList {
        height: 100%;
        width: 100%;
        border: solid $primary;
    }

    ToolList:focus {
        border: solid $accent;
    }

    ToolList > .option-list--option-highlighted {
        background: $accent;
    }
    """

    class ToolSelected(Message):
        """Message sent when a tool is selected."""

        def __init__(self, tool_use_id: str) -> None:
            super().__init__()
            self.tool_use_id = tool_use_id

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tools: dict[str, ToolUse] = {}

    def set_tools(self, tools: list[ToolUse]) -> None:
        """Update the list of tools.

        Args:
            tools: List of tool uses to display.
        """
        self._tools = {t.tool_use_id: t for t in tools}
        self.clear_options()

        for tool in tools:
            option_text = self._format_tool(tool)
            self.add_option(Option(option_text, id=tool.tool_use_id))

    def _format_tool(self, tool: ToolUse) -> Text:
        """Format a tool use for display.

        Args:
            tool: The tool use to format.

        Returns:
            Formatted text for display.
        """
        text = Text()

        # Status icon
        icon, color = STATUS_ICONS.get(tool.status, ("", "white"))
        text.append(f"{icon} ", style=color)

        # Tool icon
        tool_icon = TOOL_ICONS.get(tool.tool_name, "")
        text.append(f"{tool_icon} ", style="dim")

        # Tool name
        text.append(tool.tool_name, style="bold")

        # Preview (truncated)
        if tool.preview:
            preview = tool.preview[:40] + "..." if len(tool.preview) > 40 else tool.preview
            text.append(f"  {preview}", style="dim")

        return text

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight (single click/arrow key)."""
        if event.option_id:
            self.post_message(self.ToolSelected(str(event.option_id)))

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle option selection (click on already-highlighted item)."""
        if event.option_id:
            self.post_message(self.ToolSelected(str(event.option_id)))
