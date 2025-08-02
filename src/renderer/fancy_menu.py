from __future__ import annotations

from textual.widgets import ListView, ListItem, Label
from textual.reactive import reactive


class FancyMenuItem(ListItem):
    """List item with slide, color animation, and a highlight arrow."""

    highlighted = reactive(False)

    def __init__(self, text: str, **kwargs) -> None:
        self.label = Label(text)
        super().__init__(self.label, **kwargs)
        self.base_text = text
        self.styles.background = "black"
        self.styles.color = "green"

    def set_highlighted(self, value: bool) -> None:
        self.highlighted = value

    def watch_highlighted(self, highlighted: bool) -> None:
        if highlighted:
            # Support Textual versions prior to 0.5 where ``offset`` was split
            # into ``offset_x`` and ``offset_y``. Animating ``offset`` with a
            # tuple causes an AnimationError on those versions, so we animate
            # ``offset_x`` directly instead of the tuple. Newer versions use
            # ``offset`` which expects a Coordinate tuple.
            if hasattr(self.styles, "offset_x"):
                self.styles.animate("offset_x", 2, duration=0.2)
            else:  # Textual >= 0.5
                self.styles.animate("offset", (2, 0), duration=0.2)
            self.styles.animate("background", "green", duration=0.2)
            self.styles.animate("color", "black", duration=0.2)
            self.label.update(f"> {self.base_text}")
        else:
            if hasattr(self.styles, "offset_x"):
                self.styles.animate("offset_x", 0, duration=0.2)
            else:
                self.styles.animate("offset", (0, 0), duration=0.2)
            self.styles.animate("background", "black", duration=0.2)
            self.styles.animate("color", "green", duration=0.2)
            self.label.update(self.base_text)


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
