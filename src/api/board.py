class GameBoard:
    """Manages a 2D grid where ANSI block shapes (codels) are placed."""

    def __init__(self, width=100, height=200):
        self.width = width
        self.height = height
        self.board = [["white" for _ in range(width)] for _ in range(height)]  # ✅ Default to white instead of " "
        self.board_loaded = False

    def set_color(self, x, y, color_code):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.board[y][x] = color_code  # ✅ Store the color name, not a space
            return True
        return False

    def clear_color(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.board[y][x] = "white"  # ✅ Use "white" instead of a blank space

    def to_json(self):
        """Return board as JSON for the API."""
        return {"board": self.board}  # ✅ Ensure colors are returned instead of spaces

    def render(self):
        """Render the board with actual ANSI colors in the terminal."""
        border = "+" + "-" * self.width + "+"
        board_str = [border]

        for row_idx, row in enumerate(self.board):
            line = "|"
            for col_idx, color in enumerate(row):
                ansi_color = self.get_ansi_color(color)
                line += f"{ansi_color}█\033[0m"  # ✅ Render block instead of space
            line += "|"
            board_str.append(line)

        board_str.append(border)
        return "\n".join(board_str)

    def get_ansi_color(self, color_name):
        """Convert color name to ANSI escape sequence."""
        COLOR_MAPPING = {
            "red": "\033[48;2;255;0;0m",
            "green": "\033[48;2;0;255;0m",
            "yellow": "\033[48;2;255;255;0m",
            "blue": "\033[48;2;0;0;255m",
            "magenta": "\033[48;2;255;0;255m",
            "cyan": "\033[48;2;0;255;255m",
            "white": "\033[48;2;255;255;255m",
            "black": "\033[48;2;0;0;0m",
        }
        return COLOR_MAPPING.get(color_name, "\033[48;2;255;255;255m")  # ✅ Default to white
