from __future__ import annotations

from textual.widgets import ListView, ListItem, Label
from textual.reactive import reactive


class FancyMenuItem(ListItem):
    """List item with simple slide and color animation when highlighted."""

    highlighted = reactive(False)

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(Label(text), **kwargs)
        self.styles.background = "black"
        self.styles.color = "green"

    def set_highlighted(self, value: bool) -> None:
        self.highlighted = value

    def watch_highlighted(self, highlighted: bool) -> None:
        if highlighted:
            self.styles.animate("offset_x", 2, duration=0.2)
            self.styles.animate("background", "green", duration=0.2)
            self.styles.animate("color", "black", duration=0.2)
        else:
            self.styles.animate("offset_x", 0, duration=0.2)
            self.styles.animate("background", "black", duration=0.2)
            self.styles.animate("color", "green", duration=0.2)


class FancyListView(ListView):
    """List view that animates items when highlighted."""

    def on_mount(self) -> None:
        self.current: FancyMenuItem | None = None
        if self.children:
            first = self.children[0]
            if isinstance(first, FancyMenuItem):
                first.set_highlighted(True)
                self.current = first

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:  # type: ignore[override]
        if self.current and isinstance(self.current, FancyMenuItem):
            self.current.set_highlighted(False)
        if event.item and isinstance(event.item, FancyMenuItem):
            event.item.set_highlighted(True)
            self.current = event.item
