class GameBoard:
    """Manages a 2D grid where ANSI block shapes (codels) are placed."""

    def __init__(self, width=100, height=200):
        self.width = width
        self.height = height
        self.board = [["white" for _ in range(width)] for _ in range(height)]  # ✅ Default to white instead of " "
        self.board_loaded = False
        self.revision = 0
        self._changes = []  # (revision, x, y, color)
        self._max_changes = 50000

    def _record_change(self, x, y, color_code):
        self.revision += 1
        self._changes.append((self.revision, x, y, color_code))
        if len(self._changes) > self._max_changes:
            # Trim oldest history while keeping latest revisions contiguous.
            self._changes = self._changes[-self._max_changes:]

    def set_color(self, x, y, color_code):
        if 0 <= x < self.width and 0 <= y < self.height:
            if self.board[y][x] != color_code:
                self.board[y][x] = color_code  # ✅ Store the color name, not a space
                self._record_change(x, y, color_code)
            return True
        return False

    def clear_color(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            if self.board[y][x] != "white":
                self.board[y][x] = "white"  # ✅ Use "white" instead of a blank space
                self._record_change(x, y, "white")

    def get_changes_since(self, since_revision):
        """
        Return board changes newer than since_revision.
        Returns (changes, too_old).
        """
        if not self._changes:
            return [], False
        earliest_revision = self._changes[0][0]
        if since_revision < earliest_revision - 1:
            return [], True
        changes = [
            {"revision": rev, "x": x, "y": y, "color": color}
            for rev, x, y, color in self._changes
            if rev > since_revision
        ]
        return changes, False

    def to_json(self):
        """Return board as JSON for the API."""
        return {"board": self.board, "revision": self.revision}  # ✅ Ensure colors are returned instead of spaces

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
