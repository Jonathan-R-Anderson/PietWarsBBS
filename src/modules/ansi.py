from __future__ import annotations

import pathlib
from pathlib import Path
from typing import List

from textual.widget import Widget
from textual.reactive import reactive

try:
    from PIL import Image, ImageSequence
except Exception:  # pragma: no cover - Pillow missing
    Image = None  # type: ignore
    ImageSequence = None  # type: ignore


class ANSIWallpaper(Widget):
    """Widget that displays ANSI frames or renders a GIF as the background."""

    frame = reactive(0)

    def __init__(self, source: str, interval: float = 0.5, **kwargs):
        """Initialize wallpaper from a directory of .ans files or a GIF file."""

        super().__init__(**kwargs)
        self.source = Path(source)
        self.interval = interval
        self.ans_paths: List[Path] = []
        self.gif_frames: List[str] = []

    def on_mount(self) -> None:
        if self.source.is_dir():
            self.ans_paths = sorted(self.source.glob("*.ans"))
        elif self.source.suffix.lower() == ".gif" and Image is not None:
            width = self.size.width or 80
            try:
                img = Image.open(self.source)
                self.gif_frames = [self._image_to_ansi(frame.copy(), width)
                                   for frame in ImageSequence.Iterator(img)]
            except Exception:
                self.gif_frames = []

        if self.ans_paths or self.gif_frames:
            self.set_interval(self.interval, self._next_frame)
            self._next_frame()

    def _image_to_ansi(self, img: "Image.Image", width: int) -> str:
        """Convert a PIL image frame to an ANSI colored string."""

        img = img.convert("RGB")
        w, h = img.size
        aspect = 0.5  # terminal aspect ratio adjustment
        new_height = max(1, int(h * width / w * aspect))
        img = img.resize((width, new_height))
        lines = []
        for y in range(new_height):
            line = []
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                line.append(f"\x1b[48;2;{r};{g};{b}m ")
            line.append("\x1b[0m")
            lines.append("".join(line))
        return "\n".join(lines)

    def _next_frame(self) -> None:
        if self.gif_frames:
            self.frame = (self.frame + 1) % len(self.gif_frames)
            text = self.gif_frames[self.frame]
        elif self.ans_paths:
            self.frame = (self.frame + 1) % len(self.ans_paths)
            try:
                text = self.ans_paths[self.frame].read_text(errors="ignore")
            except Exception:
                text = ""
        else:
            return
        self.update(text)
