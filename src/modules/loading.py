"""Textual-based matrix loading animation."""

from __future__ import annotations

import os
import random
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.reactive import reactive
from textual.widgets import Header, Footer


def get_env_var(name: str, default, cast_type=str):
    """Retrieve environment variables safely with default values."""
    value = os.getenv(name, default)
    try:
        return cast_type(value)
    except ValueError:
        return default


class FallingChar:
    """Represents a single falling block with a fading trail."""

    matrix_chars = [
        get_env_var("block_1", "██"),
        get_env_var("block_2", "██"),
        get_env_var("block_3", "██"),
        get_env_var("block_4", "██"),
        get_env_var("block_5", "██"),
        get_env_var("block_6", "██"),
        get_env_var("block_7", "██"),
        get_env_var("block_8", "██"),
        get_env_var("block_9", "██"),
        get_env_var("block_10", "██"),
    ]

    def __init__(self, screen_width: int) -> None:
        self.min_speed = get_env_var("MIN_SPEED", 1, int)
        self.max_speed = get_env_var("MAX_SPEED", 5, int)
        self.trail_length = get_env_var("TRAIL_LENGTH", 6, int)
        self.reset(screen_width)

    def reset(self, screen_width: int) -> None:
        self.x = random.randint(0, max(1, screen_width - 1))
        self.y = 0
        self.speed = random.randint(self.min_speed, self.max_speed)
        self.offset = random.randint(0, self.speed)
        self.char = random.choice(self.matrix_chars)
        self.trail: list[tuple[int, int, str]] = []

    def should_advance(self, step: int) -> bool:
        return step % (self.speed + self.offset) == 0

    def step(self, width: int, height: int, step: int) -> list[tuple[int, int, str, int]]:
        """Advance the character and return positions to draw."""
        positions: list[tuple[int, int, str, int]] = []
        if not self.should_advance(step):
            return positions

        if self.y >= height - 1:
            self.reset(width)
            return positions

        # record current position for trail
        self.trail.append((self.y, self.x, self.char))
        if len(self.trail) > self.trail_length:
            self.trail.pop(0)

        # move down
        self.y += 1
        self.char = random.choice(self.matrix_chars)

        # build positions for trail
        for index, (y, x, char) in enumerate(reversed(self.trail)):
            fade = min(index, 2)
            positions.append((y, x, char, fade))

        # include head of drop
        positions.append((self.y, self.x, self.char, 0))
        return positions


class MatrixWidget(Widget):
    """Widget that renders the matrix-style falling blocks."""

    step = reactive(0)

    def on_mount(self) -> None:
        width = self.size.width or 80
        count = get_env_var("DROPPING_CHARS", 50, int)
        self.chars = [FallingChar(width) for _ in range(count)]
        self.set_interval(get_env_var("SLEEP_MILLIS", 0.05, float), self._tick)

    def _tick(self) -> None:
        self.step += 1
        self.refresh()

    def render(self) -> Text:
        width = self.size.width or 80
        height = self.size.height or 24
        grid = [[(" ", "") for _ in range(width)] for _ in range(height)]

        for fc in self.chars:
            for y, x, char, fade in fc.step(width, height, self.step):
                if 0 <= y < height and 0 <= x < width:
                    if fade == 0:
                        style = "bold bright_green"
                    elif fade == 1:
                        style = "green"
                    else:
                        style = "dim green"
                    grid[y][x] = (char, style)

        text = Text()
        for row in grid:
            for char, style in row:
                text.append(char, style=style)
            text.append("\n")
        return text


class MatrixApp(App):
    """Standalone app displaying the matrix animation."""

    CSS = """
    Screen { background: black; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield MatrixWidget()
        yield Footer()


if __name__ == "__main__":
    MatrixApp().run()
