import time
import requests
import os
import curses

API_URL = "http://127.0.0.1:5000/get_board"  # Fetch JSON board state


COLOR_MAPPING = {
    curses.COLOR_RED: (255, 0, 0),
    curses.COLOR_GREEN: (0, 255, 0),
    curses.COLOR_YELLOW: (255, 255, 0),
    curses.COLOR_BLUE: (0, 0, 255),
    curses.COLOR_MAGENTA: (255, 0, 255),
    curses.COLOR_CYAN: (0, 255, 255),
}


def fetch_board():
    """Fetch latest board state from API."""
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            return response.json()  # Expecting a JSON response
    except requests.ConnectionError:
        return None  # Handle connection failure
    return None

def setup_curses(stdscr):
    """Initialize curses with custom RGB color handling."""
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()

    if not curses.has_colors() or not curses.can_change_color():
        stdscr.addstr(0, 0, "❌ Error: No color support or cannot modify colors.")
        stdscr.refresh()
        time.sleep(2)
        return

    curses.start_color()

    # ✅ Convert RGB (0-255) → Curses Scale (0-1000)
    def rgb_to_curses(value):
        return int((value / 255) * 1000)

    # ✅ Define custom colors
    for color_id, (r, g, b) in COLOR_MAPPING.items():
        curses.init_color(color_id, rgb_to_curses(r), rgb_to_curses(g), rgb_to_curses(b))

    # ✅ Define color pairs with custom colors
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)



def render_board(stdscr):
    """Continuously fetch & render the board in real-time using curses."""
    setup_curses(stdscr)

    while True:
        board_data = fetch_board()

        if board_data is None:
            stdscr.addstr(0, 0, "❌ Error: Unable to retrieve board data.", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(1)
            continue

        if "board" not in board_data or "colors" not in board_data:
            stdscr.addstr(0, 0, "⚠️ API returned invalid data.", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(1)
            continue

        stdscr.clear()

        grid = board_data["board"]
        colors = board_data["colors"]

        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                color_code = colors[row_idx][col_idx] if row_idx < len(colors) and col_idx < len(colors[0]) else ""
                color_pair = COLOR_MAPPING.get(color_code, 7)  # Default to white
                
                if cell.strip():  # Only draw non-empty characters
                    stdscr.addch(row_idx, col_idx * 2, "█", curses.color_pair(color_pair))

        stdscr.refresh()
        time.sleep(0.5)



if __name__ == "__main__":
    curses.wrapper(render_board)  # Run curses application
