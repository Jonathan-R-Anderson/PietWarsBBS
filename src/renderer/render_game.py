import time
import requests
import os
import curses

API_URL = "http://127.0.0.1:5000/get_board"  # Fetch JSON board state

# Define ANSI color mappings (adjustable)
COLOR_MAP = {
    "\033[31m": 1,  # Red
    "\033[32m": 2,  # Green
    "\033[34m": 3,  # Blue
    "\033[33m": 4,  # Yellow
    "\033[35m": 5,  # Magenta
    "\033[36m": 6,  # Cyan
    "\033[37m": 7,  # White (Default)
    "": 7           # Default White for unknown colors
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
    """Initialize curses settings with proper color handling."""
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()
    curses.start_color()

    # Use default terminal background (-1) to prevent conflicts
    curses.init_pair(1, curses.COLOR_RED, -1)      # Red
    curses.init_pair(2, curses.COLOR_GREEN, -1)    # Green
    curses.init_pair(3, curses.COLOR_BLUE, -1)     # Blue
    curses.init_pair(4, curses.COLOR_YELLOW, -1)   # Yellow
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # Magenta
    curses.init_pair(6, curses.COLOR_CYAN, -1)     # Cyan
    curses.init_pair(7, curses.COLOR_WHITE, -1)    # Default White

def render_board(stdscr):
    """Continuously fetch & render the board in real-time using curses."""
    setup_curses(stdscr)

    while True:
        board_data = fetch_board()

        if board_data is None:
            stdscr.addstr(0, 0, "❌ Error: Unable to retrieve board data.", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(1)
            continue  # Retry after 1 second

        if "board" not in board_data or "colors" not in board_data:
            stdscr.addstr(0, 0, "⚠️ API returned invalid data.", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(1)
            continue  # Retry after 1 second

        stdscr.clear()

        grid = board_data["board"]
        colors = board_data["colors"]

        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                color_code = colors[row_idx][col_idx] if row_idx < len(colors) and col_idx < len(colors[0]) else ""
                color_pair = COLOR_MAP.get(color_code, 7)  # Default to white if unknown
                
                if cell.strip():  # Only draw non-empty characters
                    stdscr.addch(row_idx, col_idx * 2, "█", curses.color_pair(color_pair))

        stdscr.refresh()
        time.sleep(0.5)


if __name__ == "__main__":
    curses.wrapper(render_board)  # Run curses application
