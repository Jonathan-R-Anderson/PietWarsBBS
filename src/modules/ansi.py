from __future__ import annotations

import pathlib
from textual.widget import Widget
from textual.reactive import reactive

class ANSIWallpaper(Widget):
    """Widget that cycles through ANSI files as an animated background."""

    frame = reactive(0)

    def __init__(self, directory: str, interval: float = 0.5, **kwargs):
        super().__init__(**kwargs)
        self.directory = pathlib.Path(directory)
        self.interval = interval
        self.frames = sorted(self.directory.glob("*.ans"))

    def on_mount(self) -> None:
        if self.frames:
            self.set_interval(self.interval, self._next_frame)

    def _next_frame(self) -> None:
        if not self.frames:
            return
        self.frame = (self.frame + 1) % len(self.frames)
        try:
            text = self.frames[self.frame].read_text(errors="ignore")
        except Exception:
            text = ""
        self.update(text)
