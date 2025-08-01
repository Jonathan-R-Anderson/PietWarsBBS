from __future__ import annotations

import subprocess
import sys
import os
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ListView, ListItem, Label
from textual.containers import Horizontal, Container
from textual.screen import Screen

from modules.ansi import ANSIWallpaper
from modules import audio


class GameMenuScreen(Screen):
    """Sub-menu for launching games."""

    BINDINGS = [("q", "pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header("Game Selection")
        with Container():
            yield ListView(
                ListItem(Label("PietWars", id="pietwars")),
                ListItem(Label("Back", id="back")),
            )
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        label = event.item.query_one(Label).text
        if self.app.select_sound:
            audio.play_sound(self.app.select_sound)
        if label == "PietWars":
            await self.app.shutdown()
            subprocess.run([sys.executable, "-m", "src.renderer.render_game"])
        elif label == "Back":
            await self.app.pop_screen()


class BBSApp(App):
    """Simple anonymous-style BBS interface with a menu."""

    CSS_PATH = "bbs_styles.css"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.background_music = os.getenv("BACKGROUND_MUSIC")
        self.select_sound = os.getenv("MENU_SELECT_SOUND")
        self.wallpaper_dir = os.getenv("ANSI_WALLPAPER_DIR", "ansi")

    def on_mount(self) -> None:
        if self.background_music:
            audio.play_background(self.background_music)

    def compose(self) -> ComposeResult:
        yield ANSIWallpaper(self.wallpaper_dir, id="wallpaper")
        yield Header("PietChan BBS")
        with Horizontal(id="main_layout"):
            with Container(id="menu_panel"):
                yield ListView(
                    ListItem(Label("/p/ Programming")),
                    ListItem(Label("/g/ Games")),
                    ListItem(Label("Quit")),
                )
            self.content = Static("Welcome to PietChan! Select a board from the menu.", id="content")
            yield self.content
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        label = event.item.query_one(Label).text
        if self.select_sound:
            audio.play_sound(self.select_sound)
        if label.endswith("Games"):
            await self.push_screen(GameMenuScreen())
        elif label == "Quit":
            await self.action_quit()
        else:
            self.content.update(f"You opened {label}")


if __name__ == "__main__":
    BBSApp().run()
