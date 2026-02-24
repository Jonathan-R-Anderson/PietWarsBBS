"""
Evil BBS — Retro hacker BBS with PietWars integration.
Connects via telnet on port 1337.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import requests
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label, ListView, Rule, Input, Button
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


class LoginScreen(Screen):
    """Login gate: username + ID seed (hashed into network ID)."""

    BINDINGS = [("enter", "submit_login", "Login"), ("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="game_info_panel"):
            yield Static(
                "[bold bright_cyan]Network Login[/]\n"
                "[dim]Enter a username and secret ID seed[/dim]",
                id="game_title",
            )
            yield Rule()
            self.username_input = Input(placeholder="Username", id="login_username")
            yield self.username_input
            self.seed_input = Input(password=True, placeholder="ID seed (private)", id="login_seed")
            yield self.seed_input
            self.submit_button = Button("Enter BBS", id="login_submit")
            yield self.submit_button
            self.status = Static("", id="login_status")
            yield self.status
        yield Footer()

    def on_mount(self) -> None:
        self.username_input.focus()

    async def action_submit_login(self) -> None:
        if self.submit_button.disabled:
            logger.debug("Login submit ignored: already in progress")
            return
        logger.debug("Login submit triggered")
        username = self.username_input.value.strip()
        seed = self.seed_input.value.strip()
        logger.debug("Login attempt for username=%s seed_len=%d", username, len(seed))
        if not username or not seed:
            self.status.update("[red]Username and ID seed are required[/red]")
            logger.debug("Login rejected: missing username or seed")
            return
        self.submit_button.disabled = True
        self.status.update("[dim]Signing in...[/dim]")
        try:
            svc = kademlia.get_service()
            svc.set_identity(username, seed)
            logger.debug("Identity set for handle=%s", svc.get_local_handle())
        except Exception as exc:
            self.status.update(f"[red]P2P login failed: {exc}[/red]")
            self.submit_button.disabled = False
            logger.exception("Login failed in set_identity")
            return

        def _start_p2p() -> None:
            try:
                svc.start()
                self.app.call_from_thread(
                    self.status.update,
                    f"[green]Logged in as {svc.get_local_handle()}[/green]",
                )
            except Exception as exc:
                self.app.call_from_thread(
                    self.status.update,
                    f"[red]P2P startup failed: {exc}[/red]",
                )
                self.app.call_from_thread(setattr, self.submit_button, "disabled", False)

        threading.Thread(target=_start_p2p, daemon=True).start()
        logger.debug("P2P start thread launched; pushing MainMenuScreen")
        await self.app.push_screen(MainMenuScreen())
        logger.debug("MainMenuScreen pushed")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login_submit":
            await self.action_submit_login()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit login when Enter is pressed in username/seed fields."""
        if event.input.id in ("login_username", "login_seed"):
            await self.action_submit_login()


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


class WhosOnScreen(Screen):
    """Dedicated screen for active-user directory and direct invites."""

    BINDINGS = [
        ("q", "pop_screen", "Back"),
        ("escape", "pop_screen", "Back"),
        ("r", "refresh_directory", "Refresh"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.directory_handles: list[str] = []
        self.content: Static | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="game_info_panel"):
            self.content = Static("[dim]Loading directory...[/dim]", id="game_description")
            yield self.content
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_directory()
        self.set_interval(3.0, self.refresh_directory)

    def action_refresh_directory(self) -> None:
        self.refresh_directory()

    def refresh_directory(self) -> None:
        if not self.content:
            return
        try:
            svc = kademlia.get_service()
            me = svc.get_local_handle()
            users = [u for u in svc.list_active_users() if u.get("handle") != me]
            self.directory_handles = [u.get("handle", "") for u in users][:9]
            lines = ["[bold bright_cyan]Who’s On[/bold bright_cyan]"]
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
        if event.key.isdigit():
            idx = int(event.key) - 1
            if 0 <= idx < len(self.directory_handles):
                handle = self.directory_handles[idx]
                ok, msg = kademlia.get_service().invite_handle(handle)
                self.app.notify(msg, severity="information" if ok else "error")
                event.stop()


class MainMenuScreen(Screen):
    """Primary BBS menu presented to telnet users."""

    BINDINGS = [
        ("enter", "select_current", "Select"),
        ("w", "open_whos_on", "Who's On"),
        ("q", "app.quit", "Quit"),
    ]

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
        self._menu: FancyListView | None = None

    def compose(self) -> ComposeResult:
        logger.debug("Composing MainMenuScreen")
        yield ANSIWallpaper(self.app.wallpaper, id="wallpaper")
        yield Header(show_clock=False)

        yield BannerWidget(id="banner")
        yield Rule(id="banner_rule")

        with Horizontal(id="main_layout"):
            with Vertical(id="menu_panel"):
                yield Static("[bold bright_green]◈ MAIN MENU ◈[/]", id="menu_title")
                self._menu = FancyListView(
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
                yield self._menu

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
        await self._handle_menu_selection(label)

    async def action_select_current(self) -> None:
        """Fallback Enter handler for terminal/client combos that miss Selected events."""
        if not self._menu:
            return
        item = getattr(self._menu, "current", None)
        if item is None:
            try:
                idx = int(getattr(self._menu, "index", 0))
                items = list(self._menu.query(FancyMenuItem))
                if 0 <= idx < len(items):
                    item = items[idx]
            except Exception:
                item = None
        if not item:
            return
        label = getattr(item, "base_text", "")
        if self.app.select_sound:
            audio.play_sound(self.app.select_sound)
        await self._handle_menu_selection(label)

    async def action_open_whos_on(self) -> None:
        await self._open_whos_on()

    async def _handle_menu_selection(self, label: str) -> None:
        normalized = "".join(ch for ch in str(label).lower() if ch.isalnum() or ch.isspace()).strip()
        logger.debug("Main menu selected: %s (normalized=%s)", label, normalized)
        if normalized == "games":
            await self.app.push_screen(GameMenuScreen())
            return
        raw = str(label).lower()
        if (
            normalized in ("whos on", "who s on", "whose on", "whoon", "whoson")
            or ("who" in raw and "on" in raw)
        ):
            await self._open_whos_on()
            return
        body = self.CONTENT_MAP.get(label, f"[bold]{label}[/]\n\nComing soon.")
        self.content.update(body + "\n\n[dim]Press a menu item to continue.[/]")

    async def _open_whos_on(self) -> None:
        try:
            self.app.notify("Opening Who's On...", severity="information", timeout=0.8)
            await self.app.push_screen(WhosOnScreen())
        except Exception as exc:
            logger.exception("Failed to open Who's On screen")
            self.content.update(
                "[bold red]Failed to open Who's On[/]\n\n"
                f"[dim]{exc}[/dim]"
            )

    async def on_key(self, event: events.Key) -> None:
        key = event.key
        if key in ("enter", "return", "ctrl+m"):
            await self.action_select_current()
            event.stop()
            return

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.app.scroll_sound:
            audio.play_sound(self.app.scroll_sound)
        logger.debug("Highlight changed to: %s", getattr(event.item, "base_text", None))


class BBSApp(App):
    """Evil BBS Textual application."""

    CSS_PATH = str(Path(__file__).resolve().parent / "bbs_styles.css")

    BINDINGS = [
        ("w", "open_whos_on_global", "Who's On"),
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
        if self.background_music:
            audio.play_background(self.background_music)
        self.push_screen(LoginScreen())

    async def action_open_whos_on_global(self) -> None:
        """Global hard fallback: open Who's On from main menu regardless of focus."""
        if isinstance(self.screen, MainMenuScreen):
            await self.screen._open_whos_on()


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
