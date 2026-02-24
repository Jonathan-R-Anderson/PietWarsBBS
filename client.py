#!/usr/bin/env python3
"""
PietWars Board Client
─────────────────────
A terminal-based client for interacting with the PietWars API.
Supports both single-player Piet painting and Corewar-style battle mode.

Usage:
    python client.py [--host HOST] [--port PORT]

Controls:
    Arrow keys      Move cursor
    1-8             Select color  (1=white 2=red 3=green 4=blue
                                   5=yellow 6=magenta 7=cyan 8=black)
    Space / Enter   Place selected color at cursor
    d               Delete / clear cell (set to white)
    r               Refresh board from API
    p               Initialize Piet interpreter
    s               Start single-player execution
    x               Stop single-player execution
    J <id> <name>   Join battle  (e.g.  J p1 Alice)
    B               Start battle
    N               Stop battle
    I               Show battle status
    q               Quit
"""

import curses
import requests
import argparse
import sys
import time

# ── Color definitions ──────────────────────────────────────────────────────

COLORS = ["white", "red", "green", "blue", "yellow", "magenta", "cyan", "black"]

# Standard ANSI terminal color indices
_CIDX = {
    "black":   0,
    "red":     1,
    "green":   2,
    "yellow":  3,
    "blue":    4,
    "magenta": 5,
    "cyan":    6,
    "white":   7,
}

# Player display info
PLAYER_META = {
    "p1": ("P1", "red"),
    "p2": ("P2", "blue"),
    "p3": ("P3", "green"),
    "p4": ("P4", "yellow"),
}

CELL_W = 2   # terminal columns per board cell


# ── API helpers ────────────────────────────────────────────────────────────

def api(base, method, path, **kwargs):
    """Make an API request.  Returns (ok, response_dict, message_str)."""
    try:
        r = requests.request(method, f"{base}{path}", timeout=4, **kwargs)
        try:
            data = r.json()
        except Exception:
            data = {}
        ok = r.status_code in (200, 201)
        msg = (data.get("message") or data.get("error") or
               ("OK" if ok else f"HTTP {r.status_code}"))
        return ok, data, msg
    except requests.ConnectionError:
        return False, {}, "Connection error — is the API running?"
    except Exception as e:
        return False, {}, str(e)


def fetch_board(base):
    """Fetch board grid, width, height."""
    _, dims, _ = api(base, "GET", "/get_dimensions")
    w = dims.get("cols", 10)
    h = dims.get("rows", 10)
    _, bdata, _ = api(base, "GET", "/get_board")
    grid = bdata.get("board") or [["white"] * w for _ in range(h)]
    return grid, w, h


# ── Curses drawing helpers ─────────────────────────────────────────────────

def draw_title(stdscr, base, max_x):
    title = f" ◈ PIET WARS CLIENT  [{base}] ◈ "
    try:
        stdscr.addstr(0, 0, title[:max_x - 1].ljust(max_x - 1),
                      curses.color_pair(10) | curses.A_BOLD)
    except curses.error:
        pass


def draw_board(stdscr, board, bw, bh, cursor_x, cursor_y,
               view_x, view_y, board_h, board_w):
    for sy in range(board_h):
        gy = view_y + sy
        for sx in range(board_w):
            gx = view_x + sx
            if gy >= bh or gx >= bw:
                break
            row = board[gy] if gy < len(board) else []
            color = (row[gx] if gx < len(row) else "white") or "white"
            pair = (COLORS.index(color) + 1) if color in COLORS else 1
            attr = curses.color_pair(pair)
            if gx == cursor_x and gy == cursor_y:
                attr = curses.color_pair(9) | curses.A_BOLD
            try:
                stdscr.addstr(1 + sy, sx * CELL_W, "  ", attr)
            except curses.error:
                pass


def draw_palette(stdscr, sel_color, cursor_x, cursor_y, pal_y, max_x):
    px = 2
    try:
        stdscr.addstr(pal_y, 0, "Colors:", curses.color_pair(12) | curses.A_BOLD)
    except curses.error:
        pass
    for i, c in enumerate(COLORS, 1):
        pair = i
        marker = "►" if c == sel_color else " "
        label = f"{i}"
        try:
            stdscr.addstr(pal_y, px,     marker, curses.color_pair(12) | curses.A_BOLD)
            stdscr.addstr(pal_y, px + 1, "  ",   curses.color_pair(pair))
            stdscr.addstr(pal_y, px + 3, label,  curses.color_pair(12))
        except curses.error:
            pass
        px += 6
    try:
        info = f"  cursor:({cursor_x},{cursor_y})  color:[{sel_color}]"
        stdscr.addstr(pal_y + 1, 0, info[:max_x - 1], curses.color_pair(12))
    except curses.error:
        pass


def draw_status(stdscr, msg, status_y, max_x):
    try:
        stdscr.addstr(status_y, 0,
                      f" {msg[:max_x - 2]}".ljust(max_x - 1)[:max_x - 1],
                      curses.color_pair(11))
    except curses.error:
        pass


def draw_help(stdscr, help_y, max_x):
    help_text = (
        "  Arrows:move  1-8:color  Spc/Enter:place  d:del  r:refresh"
        "  p:init  s:start  x:stop  B:battle  I:info  q:quit"
    )
    try:
        stdscr.addstr(help_y, 0, help_text[:max_x - 1], curses.color_pair(12) | curses.A_DIM)
    except curses.error:
        pass


# ── Main loop ──────────────────────────────────────────────────────────────

def run(stdscr, base):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()

    # Pairs 1-8: board colors (black fg on color bg)
    for i, color in enumerate(COLORS, 1):
        try:
            curses.init_pair(i, 0, _CIDX[color])
        except Exception:
            pass

    # Special pairs
    try:
        curses.init_pair(9,  curses.COLOR_WHITE,  curses.COLOR_BLUE)   # cursor
        curses.init_pair(10, curses.COLOR_WHITE,  curses.COLOR_BLACK)  # title
        curses.init_pair(11, curses.COLOR_BLACK,  curses.COLOR_GREEN)  # status
        curses.init_pair(12, curses.COLOR_GREEN,  curses.COLOR_BLACK)  # text/help
    except Exception:
        pass

    board, bw, bh = fetch_board(base)
    cursor_x, cursor_y = 0, 0
    sel_color = "red"
    message = f"Connected  board: {bw}×{bh}"
    view_x, view_y = 0, 0

    # Input command buffer for multi-key commands (e.g. "J p1 Alice")
    cmd_buf = ""
    cmd_mode = False

    stdscr.timeout(100)   # non-blocking getch (100 ms)

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        TITLE_H   = 1
        PALETTE_H = 2
        STATUS_H  = 1
        HELP_H    = 1
        CHROME    = TITLE_H + PALETTE_H + STATUS_H + HELP_H
        board_h   = max(1, max_y - CHROME)
        board_w   = max(1, max_x // CELL_W)

        # Auto-scroll viewport
        if cursor_x - view_x >= board_w:
            view_x = cursor_x - board_w + 1
        if cursor_x < view_x:
            view_x = cursor_x
        if cursor_y - view_y >= board_h:
            view_y = cursor_y - board_h + 1
        if cursor_y < view_y:
            view_y = cursor_y

        pal_y    = TITLE_H + board_h
        stat_y   = pal_y + PALETTE_H
        help_y   = stat_y + STATUS_H

        draw_title(stdscr, base, max_x)
        draw_board(stdscr, board, bw, bh, cursor_x, cursor_y,
                   view_x, view_y, board_h, board_w)
        draw_palette(stdscr, sel_color, cursor_x, cursor_y, pal_y, max_x)

        if cmd_mode:
            draw_status(stdscr, f"CMD> {cmd_buf}_", stat_y, max_x)
        else:
            draw_status(stdscr, message, stat_y, max_x)

        draw_help(stdscr, help_y, max_x)
        stdscr.refresh()

        key = stdscr.getch()

        # ── Command mode (multi-char) ──────────────────────────
        if cmd_mode:
            if key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                parts = cmd_buf.strip().split()
                cmd_buf = ""
                cmd_mode = False
                if parts and parts[0].upper() == "J":
                    pid  = parts[1] if len(parts) > 1 else "p1"
                    name = parts[2] if len(parts) > 2 else pid
                    ok, _, msg = api(base, "POST", "/battle/join",
                                     json={"player_id": pid, "name": name})
                    message = msg
                else:
                    message = f"Unknown command: {cmd_buf}"
            elif key == 27:  # Escape
                cmd_buf = ""
                cmd_mode = False
                message = "Command cancelled"
            elif key != -1:
                cmd_buf += chr(key) if 32 <= key < 127 else ""
            continue

        # ── Normal mode ────────────────────────────────────────
        if key == -1:
            continue

        if key == ord('q'):
            break

        elif key == curses.KEY_UP:
            cursor_y = max(0, cursor_y - 1)
        elif key == curses.KEY_DOWN:
            cursor_y = min(bh - 1, cursor_y + 1)
        elif key == curses.KEY_LEFT:
            cursor_x = max(0, cursor_x - 1)
        elif key == curses.KEY_RIGHT:
            cursor_x = min(bw - 1, cursor_x + 1)

        elif ord('1') <= key <= ord('8'):
            sel_color = COLORS[key - ord('1')]

        elif key in (ord(' '), ord('\n'), curses.KEY_ENTER):
            ok, _, msg = api(base, "POST", "/set_color",
                             json={"x": cursor_x, "y": cursor_y, "color": sel_color})
            if ok:
                if cursor_y < len(board) and cursor_x < len(board[cursor_y]):
                    board[cursor_y][cursor_x] = sel_color
                message = f"Placed {sel_color} at ({cursor_x},{cursor_y})"
            else:
                message = f"Error: {msg}"

        elif key == ord('d'):
            ok, _, msg = api(base, "POST", "/clear_color",
                             json={"x": cursor_x, "y": cursor_y})
            if ok:
                if cursor_y < len(board) and cursor_x < len(board[cursor_y]):
                    board[cursor_y][cursor_x] = "white"
                message = f"Cleared ({cursor_x},{cursor_y})"
            else:
                message = f"Error: {msg}"

        elif key == ord('r'):
            board, bw, bh = fetch_board(base)
            message = f"Refreshed  board: {bw}×{bh}"

        elif key == ord('p'):
            ok, _, msg = api(base, "GET", "/load_piet")
            message = msg

        elif key == ord('s'):
            ok, _, msg = api(base, "GET", "/start_execution")
            message = msg

        elif key == ord('x'):
            ok, _, msg = api(base, "GET", "/stop_execution")
            message = msg

        # ── Battle commands ────────────────────────────────────

        elif key == ord('J'):
            # Enter command mode to type  J <player_id> <name>
            cmd_mode = True
            cmd_buf = "J "
            message = "Enter: J <player_id> <name>  (ids: p1 p2 p3 p4)"

        elif key == ord('B'):
            ok, _, msg = api(base, "GET", "/battle/start")
            message = msg

        elif key == ord('N'):
            ok, _, msg = api(base, "GET", "/battle/stop")
            message = msg

        elif key == ord('I'):
            ok, data, msg = api(base, "GET", "/battle/status")
            if ok:
                players = data.get("players", {})
                running = data.get("running", False)
                winner  = data.get("winner", "none")
                lines = [f"Battle: {'RUNNING' if running else 'STOPPED'}  winner:{winner}"]
                for pid, info in players.items():
                    hp    = info.get("health", "?")
                    alive = "ALIVE" if info.get("alive") else "DEAD"
                    pos   = info.get("position", [0,0])
                    lines.append(
                        f"  {pid.upper()} {info.get('name',pid)}: {alive} HP={hp} pos={pos}"
                    )
                message = " | ".join(lines)
            else:
                message = msg

        elif key == ord('L'):
            # Show zone layout
            ok, data, msg = api(base, "GET", "/battle/layout")
            if ok:
                parts = []
                for k, v in data.items():
                    parts.append(
                        f"{k}: x{v.get('x_start',0)}-{v.get('x_end',0)} "
                        f"y{v.get('y_start',0)}-{v.get('y_end',0)}"
                    )
                message = "  ".join(parts)
            else:
                message = msg


def main():
    parser = argparse.ArgumentParser(description="PietWars board client")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=5000, type=int)
    args = parser.parse_args()
    base = f"http://{args.host}:{args.port}"

    # Quick connectivity check
    try:
        requests.get(f"{base}/get_dimensions", timeout=3)
    except Exception:
        print(f"Error: Cannot reach API at {base}")
        print("Make sure Docker is running:  docker-compose up -d")
        sys.exit(1)

    curses.wrapper(lambda s: run(s, base))


if __name__ == "__main__":
    main()
