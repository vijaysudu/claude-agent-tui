"""Base config list widget with collapsible container."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from rich.text import Text
from textual.containers import Container
from textual.message import Message
from textual.widgets import Collapsible, OptionList
from textual.widgets.option_list import Option

T = TypeVar("T")


class ConfigList(Container, Generic[T]):
    """Base widget for displaying a collapsible list of config items.

    Subclasses should override:
    - TITLE: The title shown in the collapsible header
    - ICON: Icon to show next to the title
    - _format_item: How to format each item for display
    - _get_item_id: How to get the unique ID for each item
    """

    TITLE: str = "Config"
    ICON: str = ""

    DEFAULT_CSS = """
    ConfigList {
        height: auto;
        width: 100%;
        margin-bottom: 1;
    }

    ConfigList Collapsible {
        padding: 0;
        border: none;
    }

    ConfigList CollapsibleTitle {
        padding: 0 1;
        background: $surface;
    }

    ConfigList CollapsibleTitle:hover {
        background: $surface-lighten-1;
    }

    ConfigList OptionList {
        height: auto;
        max-height: 15;
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }

    ConfigList OptionList:focus {
        border: none;
    }

    ConfigList OptionList > .option-list--option-highlighted {
        background: $accent;
    }
    """

    class ItemSelected(Message):
        """Message sent when a config item is selected."""

        def __init__(self, item_type: str, item_id: str) -> None:
            super().__init__()
            self.item_type = item_type
            self.item_id = item_id

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._items: dict[str, T] = {}
        self._option_list: OptionList | None = None
        self._collapsible: Collapsible | None = None

    def compose(self):
        """Compose the widget layout."""
        title = f"{self.ICON} {self.TITLE}" if self.ICON else self.TITLE
        self._collapsible = Collapsible(title=title, collapsed=True)
        with self._collapsible:
            self._option_list = OptionList()
            yield self._option_list

    def on_mount(self) -> None:
        """Handle mount event."""
        if self._option_list:
            self._option_list.can_focus = True

    @property
    def item_type(self) -> str:
        """Get the item type for this list (used in messages)."""
        return self.TITLE.lower().rstrip("s")  # "Skills" -> "skill"

    def set_items(self, items: list[T]) -> None:
        """Update the list of items.

        Args:
            items: List of items to display.
        """
        self._items = {self._get_item_id(item): item for item in items}

        if self._option_list:
            self._option_list.clear_options()
            for item in items:
                option_text = self._format_item(item)
                self._option_list.add_option(
                    Option(option_text, id=self._get_item_id(item))
                )

        # Update title with count
        if self._collapsible:
            title = f"{self.ICON} {self.TITLE}" if self.ICON else self.TITLE
            self._collapsible.title = f"{title} ({len(items)})"

    def _format_item(self, item: T) -> Text:
        """Format an item for display.

        Override in subclasses.

        Args:
            item: The item to format.

        Returns:
            Formatted text for display.
        """
        return Text(str(item))

    def _get_item_id(self, item: T) -> str:
        """Get the unique ID for an item.

        Override in subclasses.

        Args:
            item: The item to get ID for.

        Returns:
            Unique string ID.
        """
        return str(id(item))

    def get_item(self, item_id: str) -> T | None:
        """Get an item by its ID.

        Args:
            item_id: The item's unique ID.

        Returns:
            The item or None if not found.
        """
        return self._items.get(item_id)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight."""
        if event.option_id:
            self.post_message(
                self.ItemSelected(self.item_type, str(event.option_id))
            )

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle option selection."""
        if event.option_id:
            self.post_message(
                self.ItemSelected(self.item_type, str(event.option_id))
            )

    def expand_list(self) -> None:
        """Expand the collapsible."""
        if self._collapsible:
            self._collapsible.collapsed = False

    def collapse_list(self) -> None:
        """Collapse the collapsible."""
        if self._collapsible:
            self._collapsible.collapsed = True
