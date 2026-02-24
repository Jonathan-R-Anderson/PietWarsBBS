"""
Evil BBS — Retro hacker BBS with PietWars integration.
Connects via telnet on port 1337.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label, ListView, Rule
from textual.containers import Container, Horizontal, Vertical
from textual import events
try:
    from .fancy_menu import FancyListView, FancyMenuItem
except ImportError:
    from fancy_menu import FancyListView, FancyMenuItem
from textual.screen import Screen
from textual.reactive import reactive

SRC_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from logging_config import setup_logging

try:
    from ..modules.ansi import ANSIWallpaper
    from ..modules import audio
    from ..modules import kademlia
except ImportError:
    from modules.ansi import ANSIWallpaper
    from modules import audio
    from modules import kademlia

logger = setup_logging(__name__)

API_BASE = os.getenv("API_BASE_URL", "http://api:5000")

BANNER_LINES = [
    "[bold bright_green] ███████╗██╗   ██╗██╗██╗    [/][bold bright_cyan]    ██████╗ ██████╗ ███████╗[/]",
    "[bold bright_green] ██╔════╝██║   ██║██║██║    [/][bold bright_cyan]    ██╔══██╗██╔══██╗██╔════╝[/]",
    "[bold green] █████╗  ██║   ██║██║██║    [/][bold cyan]    ██████╔╝██████╔╝███████╗[/]",
    "[bold green] ██╔══╝  ╚██╗ ██╔╝██║██║    [/][bold cyan]    ██╔══██╗██╔══██╗╚════██║[/]",
    "[bold bright_green] ███████╗ ╚████╔╝ ██║███████╗[/][bold bright_cyan]    ██████╔╝██████╔╝███████║[/]",
    "[bold bright_green] ╚══════╝  ╚═══╝  ╚═╝╚══════╝[/][bold bright_cyan]    ╚═════╝ ╚═════╝ ╚══════╝[/]",
    "",
    "[dim]   ─── E S O T E R I C   P R O G R A M M I N G   B A T T L E S Y S T E M ───[/]",
]

TICKER_MESSAGES = (
    "◈ Welcome to EVIL BBS — Where esoteric meets spectacular ◈  "
    "◈ PietWars: Express yourself in color. Destroy your enemies in code. ◈  "
    "◈ Piet is a language where programs look like abstract paintings ◈  "
    "◈ Upload a PNG. Watch it execute. Challenge your rivals. ◈  "
    "◈ Navigate with ↑↓ and Enter. Press Q to quit. ◈  "
)


class BannerWidget(Static):
    """Pulsing ASCII art header."""

    def on_mount(self) -> None:
        self.update("\n".join(BANNER_LINES))


class ClockWidget(Static):
    """Live clock — updates every second."""

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        now = datetime.now()
        self.update(
            f"[bold yellow]◷[/bold yellow]  "
            f"[cyan]{now.strftime('%Y-%m-%d')}[/cyan]  "
            f"[bold white]{now.strftime('%H:%M:%S')}[/bold white]"
        )


class ApiStatusWidget(Static):
    """Shows whether the game API is reachable."""

    def on_mount(self) -> None:
        self._check()
        self.set_interval(5.0, self._check)

    def _check(self) -> None:
        try:
            r = requests.get(f"{API_BASE}/get_dimensions", timeout=2)
            if r.status_code == 200:
                d = r.json()
                board = f"{d.get('cols','?')}×{d.get('rows','?')}"
                self.update(
                    f"[bold bright_green]● API ONLINE[/]  "
                    f"[dim]board {board}[/dim]"
                )
                return
        except Exception:
            pass
        self.update("[bold red]○ API OFFLINE[/bold red]")


class BattleStatusWidget(Static):
    """Polls /battle/status and shows a compact summary."""

    def on_mount(self) -> None:
        self._poll()
        self.set_interval(2.0, self._poll)

    def _poll(self) -> None:
        try:
            r = requests.get(f"{API_BASE}/battle/status", timeout=2)
            if r.status_code == 200:
                data = r.json()
                running = data.get("running", False)
                winner  = data.get("winner")
                n       = len(data.get("players", {}))
                if winner:
                    self.update(f"[bold yellow]★ WINNER: {winner.upper()} ★[/]")
                elif running:
                    self.update(f"[bold bright_green]⚔  BATTLE LIVE — {n} fighters[/]")
                elif n > 0:
                    self.update(f"[yellow]⚔  {n} player(s) ready[/yellow]")
                else:
                    self.update("[dim]No battle in progress[/dim]")
                return
        except Exception:
            pass
        self.update("[dim]Battle: unavailable[/dim]")


class TickerWidget(Static):
    """Scrolling marquee at the bottom of the screen."""

    _offset = 0

    def on_mount(self) -> None:
        self.set_interval(0.1, self._scroll)

    def _scroll(self) -> None:
        t = TICKER_MESSAGES
        display = t[self._offset:] + t[:self._offset]
        self.update(f"[bold green]{display[:200]}[/bold green]")
        self._offset = (self._offset + 1) % len(t)


class GameMenuScreen(Screen):
    """Sub-menu for game selection."""

    BINDINGS = [("q", "pop_screen", "Back"), ("escape", "pop_screen", "Back")]

    GAME_INFO = (
        "[bold bright_cyan]◈ PIET WARS — BATTLE MODE ◈[/]\n\n"
        "[green]A Corewar-style battle fought in the language of color.[/]\n\n"
        "Players load their [bold]Piet programs[/] into edge zones\n"
        "surrounding a central [bold]battle arena[/].\n"
        "Programs execute simultaneously — interpreters that\n"
        "enter enemy territory take damage and may reverse.\n\n"
        "[yellow]Slots:[/]  P1[red]■[/]  P2[blue]■[/]  P3[green]■[/]  P4[yellow]■[/]\n\n"
        "[dim]Use client.py to place your Piet program,\n"
        "then start the battle from here or via the API.[/]"
    )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="game_layout"):
            with Container(id="game_menu_panel"):
                yield Static(
                    "[bold bright_green]◈ GAME SELECTION ◈[/]\n"
                    "[dim]Choose your battleground[/]",
                    id="game_title",
                )
                yield Rule()
                yield FancyListView(
                    FancyMenuItem("PietWars", id="pietwars"),
                    FancyMenuItem("Back",     id="back"),
                )
            with Container(id="game_info_panel"):
                yield Static(self.GAME_INFO, id="game_description")
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        label = getattr(event.item, "base_text", event.item.query_one(Label).renderable.plain)
        if self.app.select_sound:
            audio.play_sound(self.app.select_sound)
        logger.debug("Game menu selected: %s", label)
        if label == "PietWars":
            render_path = str(Path(__file__).resolve().parent / "render_game.py")
            self.app._launch_after_exit = render_path
            self.app.exit()
        elif label == "Back":
            self.app.pop_screen()


class MainMenuScreen(Screen):
    """Primary BBS menu presented to telnet users."""

    BINDINGS = [("q", "app.quit", "Quit")]

    CONTENT_MAP = {
        "ANSI Gallery":    "[bold]ANSI Gallery[/]\n\nView retro ANSI artwork.",
        "Channels":        "[bold]Channels[/]\n\nMessage boards and discussions.",
        "File Menu":       "[bold]File Menu[/]\n\nUpload and download files.",
        "Games":           "[bold]Games[/]\n\nEnter the arena!",
        "Mail":            "[bold]Mail[/]\n\nPrivate messages.",
        "Node Chat (IRC)": "[bold]IRC Chat[/]\n\nReal-time node chat.",
        "System News":     "[bold]System News[/]\n\nLatest announcements.",
        "Who's On":        "[bold]Who's On[/]\n\nSee connected users.",
        "Your Account":    "[bold]Your Account[/]\n\nProfile and settings.",
        "Your Statistics": "[bold]Your Statistics[/]\n\nGame scores and history.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.directory_handles: list[str] = []

    def compose(self) -> ComposeResult:
        logger.debug("Composing MainMenuScreen")
        yield ANSIWallpaper(self.app.wallpaper, id="wallpaper")
        yield Header(show_clock=False)

        yield BannerWidget(id="banner")
        yield Rule(id="banner_rule")

        with Horizontal(id="main_layout"):
            with Vertical(id="menu_panel"):
                yield Static("[bold bright_green]◈ MAIN MENU ◈[/]", id="menu_title")
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

            with Vertical(id="content_area"):
                with Container(id="sysinfo_panel"):
                    yield ClockWidget(id="clock")
                    yield Rule()
                    yield ApiStatusWidget(id="api_status")
                    yield Rule()
                    yield BattleStatusWidget(id="battle_status")

                self.content = Static(
                    "[bold bright_green]Welcome to EVIL BBS![/]\n\n"
                    "[green]The premier destination for esoteric\n"
                    "programming enthusiasts and digital artists.[/]\n\n"
                    "[dim]Use ↑↓ to navigate, Enter to select.[/]",
                    id="content",
                )
                yield self.content

        yield TickerWidget(id="ticker")
        yield Footer()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        label = getattr(
            event.item, "base_text", event.item.query_one(Label).renderable.plain
        )
        if self.app.select_sound:
            audio.play_sound(self.app.select_sound)
        logger.debug("Main menu selected: %s", label)
        if label == "Games":
            await self.app.push_screen(GameMenuScreen())
        elif label == "Who's On":
            self._show_directory()
        else:
            body = self.CONTENT_MAP.get(label, f"[bold]{label}[/]\n\nComing soon.")
            self.content.update(body + "\n\n[dim]Press a menu item to continue.[/]")

    def _show_directory(self) -> None:
        try:
            svc = kademlia.get_service()
            me = svc.get_local_handle()
            users = [u for u in svc.list_active_users() if u.get("handle") != me]
            self.directory_handles = [u.get("handle", "") for u in users][:9]
            lines = ["[bold bright_cyan]Active Users[/]"]
            lines.append(f"[dim]You are {me}[/dim]")
            lines.append("")
            if not self.directory_handles:
                lines.append("[dim]No other active users discovered yet[/dim]")
            else:
                for i, handle in enumerate(self.directory_handles, start=1):
                    lines.append(f"[yellow]{i}[/yellow]. [green]{handle}[/green]")
                lines.append("")
                lines.append("[dim]Press 1-9 to send direct invite[/dim]")
            self.content.update("\n".join(lines))
        except Exception:
            self.directory_handles = []
            self.content.update("[dim]Directory unavailable[/dim]")

    async def on_key(self, event: events.Key) -> None:
        if not self.directory_handles:
            return
        key = event.key
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(self.directory_handles):
                handle = self.directory_handles[idx]
                ok, msg = kademlia.get_service().invite_handle(handle)
                self.app.notify(msg, severity="information" if ok else "error")
                event.stop()

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.app.scroll_sound:
            audio.play_sound(self.app.scroll_sound)
        logger.debug("Highlight changed to: %s", getattr(event.item, "base_text", None))


class BBSApp(App):
    """Evil BBS Textual application."""

    CSS_PATH = str(Path(__file__).resolve().parent / "bbs_styles.css")

    BINDINGS = [
        ("up",    "cursor_up",   "Up"),
        ("down",  "cursor_down", "Down"),
        ("enter", "select",      "Select"),
        ("q",     "quit",        "Quit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.background_music   = os.getenv("BACKGROUND_MUSIC")
        self.select_sound       = os.getenv("MENU_SELECT_SOUND")
        self.scroll_sound       = os.getenv("MENU_SCROLL_SOUND")
        self.wallpaper          = os.getenv("ANSI_WALLPAPER", "ansi")
        self._launch_after_exit = None

    def on_mount(self) -> None:
        logger.debug("Mounting BBSApp")
        try:
            kademlia.start_service()
        except Exception as exc:
            logger.warning("P2P directory service did not start: %s", exc)
        if self.background_music:
            audio.play_background(self.background_music)
        self.push_screen(MainMenuScreen())


if __name__ == "__main__":
    app = BBSApp()
    app.run()
    if getattr(app, "_launch_after_exit", None):
        env = os.environ.copy()
        try:
            size = os.get_terminal_size()
            env["COLUMNS"] = str(size.columns)
            env["LINES"] = str(size.lines)
        except OSError:
            # Keep existing environment values if terminal size is unavailable.
            pass
        subprocess.run([sys.executable, app._launch_after_exit], env=env)
