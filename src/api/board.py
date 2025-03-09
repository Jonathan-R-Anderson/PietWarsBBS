class GameBoard:
    """Manages a 2D grid where ANSI block shapes (codels) are placed."""

    def __init__(self, width=10, height=20):
        self.width = width
        self.height = height
        self.board = [[" " for _ in range(width)] for _ in range(height)]
        self.colors = [["" for _ in range(width)] for _ in range(height)]  # Store ANSI color codes separately

    def set_color(self, x, y, color_code):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.board[y][x] = color_code
            return True
        return False

    def clear_color(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.board[y][x] = " "

    def to_json(self):
        return {"board": self.board, "colors": self.colors}

    def render(self):
        """Render the board with actual ANSI colors in the terminal."""
        border = "+" + "-" * self.width + "+"
        board_str = [border]

        for row_idx, row in enumerate(self.board):
            line = "|"
            for col_idx, cell in enumerate(row):
                color = self.colors[row_idx][col_idx] or ""  # Get color escape code
                line += f"{color}{cell}\033[0m"  # Apply color & reset after each cell
            line += "|"
            board_str.append(line)

        board_str.append(border)
        return "\n".join(board_str)