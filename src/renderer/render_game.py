"""
PietWars Board Renderer
Displays the battle board, player status, and color palette via Textual.
"""
import os
import asyncio
import sys
import requests
from functools import partial
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal, Vertical
from textual.widgets import Static, Header, Footer, Label, Rule
from textual import events
from textual.widget import Widget
from textual.reactive import reactive
from textual.command import Provider, Hit, Hits
from textual import work
from rich.text import Text
from rich.console import RenderableType

API_BASE = os.getenv("API_BASE_URL", "http://api:5000")
DEFAULT_VIRTUAL_COLS = 183
DEFAULT_VIRTUAL_ROWS = 43
_SESSION = requests.Session()

BOARD_COLORS = ["white", "red", "green", "blue", "yellow", "magenta", "cyan", "black"]

# Player display names and symbols
PLAYER_META = {
    "p1": {"name": "Player 1", "color": "bright_red",     "symbol": "◆"},
    "p2": {"name": "Player 2", "color": "bright_blue",    "symbol": "◆"},
    "p3": {"name": "Player 3", "color": "bright_green",   "symbol": "◆"},
    "p4": {"name": "Player 4", "color": "bright_yellow",  "symbol": "◆"},
}

# Rich markup for palette swatches
COLOR_SWATCH = {
    "white":   "[on white]  [/]",
    "red":     "[on red]  [/]",
    "green":   "[on green]  [/]",
    "blue":    "[on blue]  [/]",
    "yellow":  "[on yellow]  [/]",
    "magenta": "[on magenta]  [/]",
    "cyan":    "[on cyan]  [/]",
    "black":   "[on black]  [/]",
}


def _get(path: str, timeout: int = 2):
    try:
        r = _SESSION.get(f"{API_BASE}{path}", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _request_xterm_resize(cols: int, rows: int) -> None:
    """Ask xterm-compatible terminals to resize in character cells."""
    try:
        # CSI 8 ; rows ; cols t  (xterm window manipulation)
        sys.stdout.write(f"\x1b[8;{rows};{cols}t")
        sys.stdout.flush()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Widgets
# ─────────────────────────────────────────────────────────────────────────────

class BoardView(VerticalScroll):
    """Scrollable, zoomable board renderer."""

    zoom_level = reactive(1)
    current_codel_position = reactive((None, None))
    player_positions = reactive({}) # pid -> (x, y)
    flash_state = reactive(False)
    layout_data = reactive(None)
    prev_grid = None
    write_history = {} # (x, y) -> cycle_since_change

    def on_mount(self) -> None:
        self._row_widgets = []
        self._prev_row_markup = []
        self._current_grid = []
        self._prev_cursor = (None, None)
        self._prev_flash = self.flash_state
        self._prev_player_positions = {}
        self._prev_layout = None
        self._prev_zoom = self.zoom_level
        self._layout_refresh_counter = 0
        self._board_revision = -1
        self._preview_widget = Static("", id="resize_preview")
        self._preview_widget.styles.display = "none"
        self.mount(self._preview_widget)
        self._refresh_board()
        self.set_interval(1.0, self._refresh_board)
        self._start_flash()

    def _is_resize_drag_active(self) -> bool:
        return bool(getattr(self.app, "_resize_drag_active", False))

    def _build_preview_markup(self, cols: int, rows: int) -> str:
        w = max(12, min(40, cols // 5))
        h = max(6, min(16, rows // 4))
        top = "┌" + ("─" * (w - 2)) + "┐"
        mid = "│" + (" " * (w - 2)) + "│"
        bottom = "└" + ("─" * (w - 2)) + "┘"
        lines = [top]
        for _ in range(h - 2):
            lines.append(mid)
        lines.append(bottom)
        return (
            "[bold green]Resize Preview[/bold green]\n"
            f"[dim]Target: {cols}x{rows}[/dim]\n\n"
            + "\n".join(lines)
        )

    def set_resize_preview(self, active: bool, cols: int, rows: int) -> None:
        if active:
            self._preview_widget.update(self._build_preview_markup(cols, rows))
            self._preview_widget.styles.display = "block"
            for row_widget in self._row_widgets:
                row_widget.styles.display = "none"
        else:
            self._preview_widget.styles.display = "none"
            for row_widget in self._row_widgets:
                row_widget.styles.display = "block"
            if self._current_grid:
                self._render(self._current_grid)
        self.refresh(layout=True)

    def _ensure_row_widgets(self, count: int) -> None:
        while len(self._row_widgets) < count:
            row_widget = Static("")
            self._row_widgets.append(row_widget)
            self._prev_row_markup.append("")
            self.mount(row_widget)
        while len(self._row_widgets) > count:
            row_widget = self._row_widgets.pop()
            row_widget.remove()
            self._prev_row_markup.pop()

    def _refresh_board(self) -> None:
        if self._is_resize_drag_active():
            return
        data = _get(f"/get_board_changes?since={self._board_revision}")
        if not data:
            data = _get("/get_board")
        if not data:
            return

        if data.get("full") or self._board_revision < 0:
            grid = data.get("board", [])
            self._current_grid = [row[:] for row in grid]
            self._board_revision = int(data.get("revision", self._board_revision))
        else:
            if not self._current_grid:
                full = _get("/get_board")
                if not full:
                    return
                self._current_grid = [row[:] for row in full.get("board", [])]
                self._board_revision = int(full.get("revision", self._board_revision))
            for change in data.get("changes", []):
                x = change.get("x")
                y = change.get("y")
                color = change.get("color")
                if (
                    isinstance(x, int) and isinstance(y, int) and
                    0 <= y < len(self._current_grid) and
                    0 <= x < len(self._current_grid[y])
                ):
                    self._current_grid[y][x] = color
            self._board_revision = int(data.get("revision", self._board_revision))

        grid = self._current_grid
        self._layout_refresh_counter += 1
        if self.layout_data is None or self._layout_refresh_counter >= 5:
            self.layout_data = _get("/battle/layout")
            self._layout_refresh_counter = 0
        self._render(grid)

    def _rows_from_positions(self, player_positions: dict) -> set:
        rows = set()
        for info in (player_positions or {}).values():
            if isinstance(info, dict):
                pos = info.get("position")
                if pos and len(pos) >= 2:
                    try:
                        rows.add(int(pos[1]))
                    except (TypeError, ValueError):
                        pass
        return rows

    def _render_row(self, y: int, row, pos_map: dict, ax0: int, ax1: int, ay0: int, ay1: int) -> str:
        cx, cy = self.current_codel_position
        z = self.zoom_level
        line = []
        for x, cell in enumerate(row):
            color = cell if cell else "white"
            if z == 1:
                # Compact mode: 1 char per cell so full board fits smaller terminals.
                block = "·" if color == "white" else "■"
            else:
                block = "■" * z

            is_cursor = (x == cx and y == cy)
            is_arena = (ax0 <= x < ax1 and ay0 <= y < ay1)
            player_at = pos_map.get((x, y))

            if is_cursor:
                if self.flash_state:
                    chunk = f"[bold][{color} on white]{block}[/][/]"
                else:
                    chunk = f"[bold][{color} on black]{block}[/][/]"
            elif player_at:
                p_color = PLAYER_META.get(player_at, {}).get("color", "white")
                chunk = f"[bold white on {p_color}]{block}[/]"
            elif is_arena and color == "white":
                chunk = f"[dim #333333]{block}[/]"
            else:
                render_color = f"bright_{color}" if color in ["red", "blue", "green", "yellow"] else color
                if is_arena and color != "white":
                    chunk = f"[bold][{render_color}]{block}[/][/]"
                else:
                    chunk = f"[{render_color}]{block}[/]"

            line.append(chunk)
        return "".join(line)

    def _render(self, grid) -> None:
        if self._is_resize_drag_active():
            return
        layout = self.layout_data or {}
        arena = layout.get("arena", {})
        ax0 = arena.get("x_start", -1)
        ax1 = arena.get("x_end", -1)
        ay0 = arena.get("y_start", -1)
        ay1 = arena.get("y_end", -1)

        height = len(grid)
        self._ensure_row_widgets(height)

        # Build reverse player position map: (x,y) -> pid.
        pos_map = {tuple(pos): pid for pid, info in self.player_positions.items() 
                   if (pos := info.get("position"))}

        full_rerender = (
            self.prev_grid is None
            or len(self.prev_grid) != len(grid)
            or self.layout_data != self._prev_layout
            or self.zoom_level != self._prev_zoom
            or len(self._prev_row_markup) != height
        )

        dirty_rows = set()
        if full_rerender:
            dirty_rows = set(range(height))
        else:
            for y in range(height):
                if grid[y] != self.prev_grid[y]:
                    dirty_rows.add(y)
            old_cursor = self._prev_cursor
            new_cursor = self.current_codel_position
            for cursor in (old_cursor, new_cursor):
                if cursor and len(cursor) >= 2 and cursor[1] is not None:
                    dirty_rows.add(int(cursor[1]))
            if self._prev_flash != self.flash_state:
                for cursor in (old_cursor, new_cursor):
                    if cursor and len(cursor) >= 2 and cursor[1] is not None:
                        dirty_rows.add(int(cursor[1]))
            dirty_rows |= self._rows_from_positions(self._prev_player_positions)
            dirty_rows |= self._rows_from_positions(self.player_positions)

        for y in sorted(r for r in dirty_rows if 0 <= r < height):
            row_markup = self._render_row(y, grid[y], pos_map, ax0, ax1, ay0, ay1)
            if row_markup != self._prev_row_markup[y]:
                self._row_widgets[y].update(row_markup)
                self._prev_row_markup[y] = row_markup

        self.prev_grid = [row[:] for row in grid]
        self._prev_cursor = self.current_codel_position
        self._prev_flash = self.flash_state
        self._prev_player_positions = dict(self.player_positions)
        self._prev_layout = layout
        self._prev_zoom = self.zoom_level

    def adjust_zoom(self, delta: int) -> None:
        self.zoom_level = max(1, min(4, self.zoom_level + delta))
        if self._current_grid:
            self._render(self._current_grid)

    @work
    async def _start_flash(self) -> None:
        while True:
            if self.current_codel_position != (None, None) and not self._is_resize_drag_active():
                self.flash_state = not self.flash_state
                if self._current_grid:
                    self._render(self._current_grid)
            await asyncio.sleep(0.5)


class StatusPanel(Static):
    """Execution state + codel position."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._running = False
        self._pos = (0, 0)
        self._output = ""

    def update_state(self, running: bool, pos, output: str) -> None:
        self._running = running
        self._pos = pos or (0, 0)
        self._output = output
        status = "[bold bright_green]◉ RUNNING[/]" if running else "[bold red]○ STOPPED[/]"
        x, y = self._pos
        out_preview = (self._output or "")[:50]
        self.update(
            f"  {status}\n"
            f"  [cyan]Codel:[/cyan] [yellow]({x}, {y})[/yellow]\n"
            f"  [cyan]Output:[/cyan] [white]{out_preview}[/white]"
        )


class BattlePanel(Static):
    """Live player health and status for the battle."""

    def __init__(self, **kwargs):
        super().__init__("[dim]No battle data[/dim]", **kwargs)

    def update_battle(self, status: dict) -> None:
        if not status:
            self.update("[dim]No battle data[/dim]")
            return

        running = status.get("running", False)
        winner = status.get("winner")
        steps = status.get("step_count", 0)
        arena_cells = status.get("arena_claimed_cells", 0)
        arena = status.get("arena", {}) or {}

        lines = []

        if winner:
            color = PLAYER_META.get(winner, {}).get("color", "white")
            pname = PLAYER_META.get(winner, {}).get("name", winner.upper())
            lines.append(f"[bold bright_yellow]╔══════════════════════════════╗[/]")
            lines.append(f"[bold bright_yellow]║  WINNER: {pname:^18}  ║[/]")
            lines.append(f"[bold bright_yellow]╚══════════════════════════════╝[/]")
        elif running:
            lines.append(f"[bold bright_green]▶ BATTLE ACTIVE[/]")
        else:
            lines.append("[bold yellow]⏸ BATTLE IDLE[/]")

        lines.append(f"Cycle      : [yellow]{steps:>18}[/]")
        lines.append(f"Processes  : [white]{sum(p.get('alive', 0) for p in status.get('players', {}).values()):>18}[/]")
        
        total_cells = (
            (arena.get("x_end", 0) - arena.get("x_start", 0))
            * (arena.get("y_end", 0) - arena.get("y_start", 0))
            if arena
            else 1
        )
        lines.append(f"Coverage   : [white]{(arena_cells / total_cells * 100):>17.1f}%[/]")
        
        # Mini ownership bar
        bar_width = 30
        filled = int((arena_cells / total_cells) * bar_width) if total_cells > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"[bright_white][{bar}][/]")
        lines.append("")

        for pid, info in status.get("players", {}).items():
            meta = PLAYER_META.get(pid, {"name": pid, "color": "white", "symbol": "■"})
            color = meta["color"]
            name = info.get("name", pid)
            health = info.get("health", 0)
            alive = info.get("alive", False)
            pos = info.get("position", [0, 0]) or [0, 0]
            steps_p = info.get("steps", 0)

            health_bar_size = 15
            h_filled = int((health / 100) * health_bar_size)
            health_bar = ("█" * h_filled).ljust(health_bar_size, "░")
            
            status_tag = "[bold green]LIVE[/]" if alive else "[bold red]DEAD[/]"
            lines.append(
                f"[bold white on {color}] Player {pid[-1]} [/] [bold]{name:<14}[/] {status_tag}\n"
                f"  PC: [cyan]{pos[0]:>2},{pos[1]:>2}[/] | Steps: [yellow]{steps_p:05}[/]\n"
                f"  HP: [{color}]{health_bar}[/] {health:>3}%"
            )
            lines.append("  " + "─" * 28)

        self.update("\n".join(lines))


class PalettePanel(Static):
    """Color palette swatches."""

    def on_mount(self) -> None:
        COLOR_TO_HEX = {
            "white": "00", "red": "01", "green": "02", "blue": "03",
            "yellow": "04", "magenta": "05", "cyan": "06", "black": "07"
        }
        swatches = " ".join(f"[{c}]{COLOR_TO_HEX[c]}[/]" for c in BOARD_COLORS)
        self.update(
            "[bold #444444]═══ PALETTE ═══[/]\n"
            + swatches
        )


class OutputTicker(Static):
    """Scrolling program output."""

    _text = ""
    _offset = 0

    def on_mount(self) -> None:
        self.set_interval(0.12, self._scroll)

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self._offset = 0

    def _scroll(self) -> None:
        if not self._text:
            self.update("[dim]  ► Piet output will appear here ...[/dim]")
            return
        t = self._text
        display = t[self._offset:] + "   ·   " + t[:self._offset]
        self.update(f"[bold cyan]► [/][bright_green]{display[:180]}[/]")
        self._offset = (self._offset + 1) % max(1, len(t))


class ResizeHandle(Static):
    """Drag handle to apply a virtual terminal size fallback."""

    def __init__(self, **kwargs):
        super().__init__("◀ cols ▶   ▲ rows ▼   ↘ drag", **kwargs)
        self._dragging = False
        self._last_x = 0
        self._last_y = 0

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.capture_mouse(True)
        self._last_x = getattr(event, "screen_x", getattr(event, "x", 0))
        self._last_y = getattr(event, "screen_y", getattr(event, "y", 0))
        app = self.app
        if isinstance(app, BoardApp):
            app.begin_resize_drag()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        x = getattr(event, "screen_x", getattr(event, "x", 0))
        y = getattr(event, "screen_y", getattr(event, "y", 0))
        dx = int(x - self._last_x)
        dy = int(y - self._last_y)
        if dx or dy:
            app = self.app
            if isinstance(app, BoardApp):
                app.adjust_virtual_terminal(dx=dx, dy=dy)
            self._last_x = x
            self._last_y = y
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.capture_mouse(False)
            app = self.app
            if isinstance(app, BoardApp):
                app.end_resize_drag()
            event.stop()

    def on_click(self, event: events.Click) -> None:
        """Click zones for reliable resize when drag events are inconsistent."""
        x = int(getattr(event, "x", 0))
        width = max(1, int(self.size.width))
        app = self.app
        if not isinstance(app, BoardApp):
            return

        if x < width * 0.25:
            app.adjust_virtual_terminal(dx=-2, dy=0)
        elif x < width * 0.5:
            app.adjust_virtual_terminal(dx=2, dy=0)
        elif x < width * 0.75:
            app.adjust_virtual_terminal(dx=0, dy=1)
        else:
            app.adjust_virtual_terminal(dx=0, dy=-1)
        event.stop()


class PietCommandProvider(Provider):
    """Command palette for Piet and battle controls."""

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, BoardApp)

        commands = [
            ("zoom in",           "Increase board zoom",             app.zoom_in),
            ("zoom out",          "Decrease board zoom",             app.zoom_out),
            ("start execution",   "Start single-player Piet run",    app.start_execution),
            ("stop execution",    "Stop single-player Piet run",     app.stop_execution),
            ("initialize piet",   "Load Piet interpreter",           app.initialize_piet),
            ("board status",      "Show board loaded status",        app.board_status),
            ("current codel",     "Display current codel position",  app.fetch_current_codel),
            ("start battle",      "Start the Corewar battle",        app.start_battle),
            ("stop battle",       "Stop the Corewar battle",         app.stop_battle),
        ]

        for name, help_text, callback in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    partial(callback),
                    help=help_text,
                )


# ─────────────────────────────────────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────────────────────────────────────

class BoardApp(App):
    """PietWars board viewer and battle controller."""

    CSS_PATH = str(Path(__file__).parent / "styles.css")
    COMMANDS = {PietCommandProvider}
    BINDINGS = [
        ("+", "zoom_in",      "Zoom In"),
        ("-", "zoom_out",     "Zoom Out"),
        ("ctrl+left", "terminal_cols_down", "Cols -"),
        ("ctrl+right", "terminal_cols_up", "Cols +"),
        ("ctrl+up", "terminal_rows_down", "Rows -"),
        ("ctrl+down", "terminal_rows_up", "Rows +"),
        ("h", "terminal_cols_down", "Cols -"),
        ("l", "terminal_cols_up", "Cols +"),
        ("k", "terminal_rows_up", "Rows +"),
        ("j", "terminal_rows_down", "Rows -"),
        ("s", "start_exec",   "Start Piet"),
        ("x", "stop_exec",    "Stop Piet"),
        ("p", "init_piet",    "Init Piet"),
        ("b", "start_battle", "Start Battle"),
        ("n", "stop_battle",  "Stop Battle"),
        ("r", "refresh",      "Refresh"),
        ("q", "quit",         "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_layout"):
            # ── Left: board ──
            self.board_view = BoardView(id="board_panel")
            yield self.board_view

            # ── Right: info panels ──
            with Vertical(id="right_panel"):
                yield Static(
                    "[bold bright_cyan]◈ PIET WARS ◈[/bold bright_cyan]",
                    id="game_title"
                )
                yield Rule()
                self.status_panel = StatusPanel(id="status_panel")
                yield self.status_panel
                yield Rule()
                self.battle_panel = BattlePanel(id="battle_panel")
                yield self.battle_panel
                yield Rule()
                self.palette = PalettePanel(id="palette_panel")
                yield self.palette

        with Horizontal(id="resize_bar"):
            yield Static("[dim]Resize: click zones, drag handle, or H/L/K/J[/dim]", id="resize_hint")
            self.resize_handle = ResizeHandle(id="resize_handle")
            yield self.resize_handle

        self.ticker = OutputTicker(id="output_ticker")
        yield self.ticker
        yield Footer()

    def on_mount(self) -> None:
        _request_xterm_resize(DEFAULT_VIRTUAL_COLS, DEFAULT_VIRTUAL_ROWS)
        self._virtual_cols = DEFAULT_VIRTUAL_COLS
        self._virtual_rows = DEFAULT_VIRTUAL_ROWS
        self._resize_drag_active = False
        self._last_battle_status = {}
        self._apply_virtual_layout()
        self._push_virtual_terminal_size()
        self.set_interval(1.0,  self._poll_status)
        self.set_interval(0.75, self._poll_codel)
        self.set_interval(1.0,  self._poll_battle)

    # ── Polling ──

    def _poll_status(self) -> None:
        if self._resize_drag_active:
            return
        out_data = _get("/get_output")
        output = out_data.get("output", "") if out_data else ""
        battle_data = self._last_battle_status or (_get("/battle/status") or {})
        if battle_data:
            self._last_battle_status = battle_data
        self.status_panel.update_state(
            running=bool(battle_data.get("running", False)),
            pos=self.board_view.current_codel_position,
            output=output,
        )
        if output:
            self.ticker.set_text(f"Piet Output: {output}")

    def _poll_codel(self) -> None:
        if self._resize_drag_active:
            return
        data = _get("/current_codel")
        if data and data.get("current_codel"):
            pos = tuple(data["current_codel"])
            self.board_view.current_codel_position = pos

    def _poll_battle(self) -> None:
        if self._resize_drag_active:
            return
        data = _get("/battle/status")
        if data:
            self._last_battle_status = data
            self.battle_panel.update_battle(data)
            self.board_view.player_positions = data.get("players", {})
            # Check for winner
            winner = data.get("winner")
            if winner and not getattr(self, "_winner_notified", False):
                self._winner_notified = True
                meta = PLAYER_META.get(winner, {})
                name = meta.get("name", winner.upper())
                self.notify(f"🏆 {name} WINS THE BATTLE!", severity="information", timeout=10)

    # ── Actions ──

    def action_zoom_in(self)    -> None: self.zoom_in()
    def action_zoom_out(self)   -> None: self.zoom_out()
    def action_start_exec(self) -> None: self.start_execution()
    def action_stop_exec(self)  -> None: self.stop_execution()
    def action_init_piet(self)  -> None: self.initialize_piet()
    def action_start_battle(self) -> None: self.start_battle()
    def action_stop_battle(self)  -> None: self.stop_battle()
    def action_terminal_cols_up(self) -> None: self.adjust_virtual_terminal(dx=2, dy=0)
    def action_terminal_cols_down(self) -> None: self.adjust_virtual_terminal(dx=-2, dy=0)
    def action_terminal_rows_up(self) -> None: self.adjust_virtual_terminal(dx=0, dy=1)
    def action_terminal_rows_down(self) -> None: self.adjust_virtual_terminal(dx=0, dy=-1)

    def action_refresh(self) -> None:
        self.board_view._refresh_board()
        self.notify("Board refreshed", timeout=1)

    def zoom_in(self)  -> None: self.board_view.adjust_zoom(1)
    def zoom_out(self) -> None: self.board_view.adjust_zoom(-1)

    def start_execution(self) -> None:
        ok, msg = self._api_get("/start_execution")
        self.notify(msg, severity="information" if ok else "error")

    def stop_execution(self) -> None:
        ok, msg = self._api_get("/stop_execution")
        self.notify(msg, severity="warning" if ok else "error")

    def initialize_piet(self) -> None:
        ok, msg = self._api_get("/load_piet")
        self.notify(msg, severity="information" if ok else "error")

    def board_status(self) -> None:
        data = _get("/board_status")
        if data:
            loaded = data.get("loaded", False)
            self.notify(
                "Board: LOADED ✓" if loaded else "Board: not loaded yet",
                severity="information" if loaded else "warning"
            )

    def fetch_current_codel(self) -> None:
        data = _get("/current_codel")
        if data:
            self.notify(f"Codel: {data.get('current_codel')}", severity="information")

    def start_battle(self) -> None:
        ok, msg = self._api_get("/battle/start")
        self._winner_notified = False
        self.notify(msg, severity="information" if ok else "error")

    def stop_battle(self) -> None:
        ok, msg = self._api_get("/battle/stop")
        self.notify(msg, severity="warning" if ok else "error")

    def adjust_virtual_terminal(self, dx: int = 0, dy: int = 0) -> None:
        new_cols = max(20, min(300, self._virtual_cols + dx))
        new_rows = max(10, min(120, self._virtual_rows + dy))
        if (new_cols, new_rows) == (self._virtual_cols, self._virtual_rows):
            return
        self._virtual_cols, self._virtual_rows = new_cols, new_rows
        if self._resize_drag_active:
            self.board_view.set_resize_preview(True, self._virtual_cols, self._virtual_rows)
            return
        self._apply_virtual_layout()
        self._push_virtual_terminal_size()
        self.notify(
            f"Virtual viewport {self._virtual_cols}x{self._virtual_rows}",
            severity="information",
            timeout=1.0,
        )

    def begin_resize_drag(self) -> None:
        self._resize_drag_active = True
        self.board_view.set_resize_preview(True, self._virtual_cols, self._virtual_rows)

    def end_resize_drag(self) -> None:
        self._resize_drag_active = False
        self._apply_virtual_layout()
        self._push_virtual_terminal_size()
        self.board_view.set_resize_preview(False, self._virtual_cols, self._virtual_rows)
        self.board_view._refresh_board()

    def _apply_virtual_layout(self) -> None:
        """
        Apply virtual dimensions to in-app layout.
        This gives a real visual resize effect even when telnet can't resize
        the outer terminal window.
        """
        try:
            board_panel = self.query_one("#board_panel", BoardView)
            right_panel = self.query_one("#right_panel", Vertical)
        except Exception:
            return

        # Keep layout inside the *actual* visible terminal size by using
        # percentages, not absolute columns. This avoids clipped/off-screen UI.
        baseline = 183.0
        delta = (float(self._virtual_cols) - baseline) / baseline
        board_pct = int(max(55, min(85, 72 + (delta * 20))))
        right_pct = 100 - board_pct

        board_panel.styles.width = f"{board_pct}%"
        right_panel.styles.width = f"{right_pct}%"
        self.refresh(layout=True)

    def _push_virtual_terminal_size(self) -> None:
        try:
            _SESSION.post(
                f"{API_BASE}/set_terminal_size",
                json={"rows": int(self._virtual_rows), "cols": int(self._virtual_cols)},
                timeout=1.5,
            )
        except Exception:
            pass

    def _api_get(self, path: str) -> tuple:
        try:
            r = _SESSION.get(f"{API_BASE}{path}", timeout=2)
            try:
                data = r.json()
            except Exception:
                data = {}
            ok = r.status_code == 200
            msg = data.get("message") or data.get("error") or ("OK" if ok else f"HTTP {r.status_code}")
            return ok, msg
        except Exception as e:
            return False, f"Cannot reach API: {e}"


if __name__ == "__main__":
    BoardApp().run()
