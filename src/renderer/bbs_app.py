from __future__ import annotations

import subprocess
import sys
import os
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label, ListView
try:
    # When executed as part of the package ``src.renderer`` use relative import
    from .fancy_menu import FancyListView, FancyMenuItem
except ImportError:  # pragma: no cover - fallback for running as script
    # Fallback when the module is executed directly without package context
    from fancy_menu import FancyListView, FancyMenuItem
from textual.containers import Horizontal, Container
from textual.screen import Screen

try:
    # Use relative imports when executed as part of the ``src`` package layout
    from ..modules.ansi import ANSIWallpaper
    from ..modules import audio
except ImportError:  # pragma: no cover - fallback for running as script
    # Allow running the module directly without package context
    from modules.ansi import ANSIWallpaper
    from modules import audio


class GameMenuScreen(Screen):
    """Sub-menu for launching games."""

    BINDINGS = [("q", "pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header("Game Selection")
        with Container():
            yield FancyListView(
                FancyMenuItem("PietWars", id="pietwars"),
                FancyMenuItem("Back", id="back"),
            )
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        """Handle selections from the game submenu."""
        # ``Label`` widgets in recent Textual versions no longer expose a
        # ``text`` attribute.  ``FancyMenuItem`` stores the original label text
        # on ``base_text`` so we can reliably retrieve the selection regardless
        # of how the underlying widget represents its contents.
        label = getattr(event.item, "base_text", event.item.query_one(Label).renderable.plain)
        if self.app.select_sound:
            audio.play_sound(self.app.select_sound)
        if label == "PietWars":
            await self.app.shutdown()
            subprocess.run([sys.executable, "-m", "src.renderer.render_game"])
        elif label == "Back":
            await self.app.pop_screen()


class MainMenuScreen(Screen):
    """Primary BBS menu shown to telnet users."""

    BINDINGS = [("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield ANSIWallpaper(self.app.wallpaper, id="wallpaper")
        yield Header("Evil BBS")
        with Horizontal(id="main_layout"):
            with Container(id="menu_panel"):
                yield FancyListView(
                    FancyMenuItem("ANSI Gallery"),
                    FancyMenuItem("Channels"),
                    FancyMenuItem("File Menu"),
                    FancyMenuItem("Games"),
                    FancyMenuItem("Mail"),
                    FancyMenuItem("Node Chat (IRC)"),
                    FancyMenuItem("System News"),
                    FancyMenuItem("Who's On"),
                    FancyMenuItem("Your Account"),
                    FancyMenuItem("Your Statistics"),
                )
            self.content = Static(
                "Welcome to Evil BBS! Select a menu option.", id="content"
            )
            yield self.content
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        """Handle selections from the main menu."""
        label = getattr(
            event.item, "base_text", event.item.query_one(Label).renderable.plain
        )
        if self.app.select_sound:
            audio.play_sound(self.app.select_sound)
        if label == "Games":
            await self.app.push_screen(GameMenuScreen())
        else:
            self.content.update(f"You opened {label}")

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:  # type: ignore[override]
        if self.app.scroll_sound:
            audio.play_sound(self.app.scroll_sound)


class BBSApp(App):
    """Textual BBS application with a fancy telnet menu."""

    CSS_PATH = "bbs_styles.css"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.background_music = os.getenv("BACKGROUND_MUSIC")
        self.select_sound = os.getenv("MENU_SELECT_SOUND")
        self.scroll_sound = os.getenv("MENU_SCROLL_SOUND")
        self.wallpaper = os.getenv("ANSI_WALLPAPER", "ansi")

    def on_mount(self) -> None:
        if self.background_music:
            audio.play_background(self.background_music)
        self.push_screen(MainMenuScreen())


if __name__ == "__main__":
    BBSApp().run()
