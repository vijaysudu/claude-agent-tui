"""MCP server list widget for displaying MCP servers."""

from __future__ import annotations

from rich.text import Text

from ...store.config_models import MCPServer
from .config_list import ConfigList


class MCPServerList(ConfigList[MCPServer]):
    """Widget for displaying a list of MCP servers."""

    TITLE = "MCP Servers"
    ICON = ""

    @property
    def item_type(self) -> str:
        return "mcp_server"

    def _format_item(self, item: MCPServer) -> Text:
        """Format an MCP server for display."""
        text = Text()

        # Server name
        text.append(item.name, style="green bold")

        # Command preview
        cmd = item.command
        if item.args:
            cmd += " " + " ".join(item.args[:2])
            if len(item.args) > 2:
                cmd += " ..."
        if len(cmd) > 35:
            cmd = cmd[:32] + "..."
        text.append(f"\n  {cmd}", style="dim")

        return text

    def _get_item_id(self, item: MCPServer) -> str:
        """Get unique ID for an MCP server."""
        return item.name
