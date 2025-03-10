class PietInterpreter:
    """Interprets Piet code directly from the game board array, optimizing execution."""

    # Piet color cycle
    PIET_COLORS = [
        "\\033[31m", "\\033[33m", "\\033[32m", "\\033[36m", "\\033[34m", "\\033[35m"
    ]

    def __init__(self, board, colors):
        """
        Initialize the interpreter with a game board.

        :param board: 2D list representing the game board with symbols.
        :param colors: 2D list representing color codes of each block.
        """
        self.board = board
        self.colors = colors
        self.stack = []
        self.position = (0, 0)  # Start at top-left
        self.direction = (1, 0)  # Start moving right
        self.running = True
        self.execution_cache = set()  # Stores executed (x, y) positions

    def is_valid(self, x, y):
        """
        Validate if the instruction at (x, y) follows Piet rules.

        Returns:
        - True: If execution is possible
        - False: If illegal instructions are detected
        """
        if not (0 <= x < len(self.board[0]) and 0 <= y < len(self.board)):
            return False  # Out-of-bounds is invalid
        
        return self.get_color(x, y) in self.PIET_COLORS  # Allow only valid colors

    def get_color(self, x, y):
        """Return the color at position (x, y) or empty string if out of bounds."""
        if 0 <= x < len(self.board[0]) and 0 <= y < len(self.board):
            return self.colors[y][x]
        return ""  # Treat out-of-bounds as no-op

    def push(self, value):
        """Push a value onto the stack."""
        self.stack.append(value)

    def pop(self):
        """Pop a value from the stack, return 0 if empty."""
        return self.stack.pop() if self.stack else 0

    def execute_command(self, prev_color, curr_color):
        """
        Executes a command based on color transition.

        :param prev_color: The previous block's color
        :param curr_color: The current block's color
        """
        if prev_color == curr_color:  # No color change → Continue moving
            return

        if prev_color in self.PIET_COLORS and curr_color in self.PIET_COLORS:
            hue_change = self.PIET_COLORS.index(curr_color) - self.PIET_COLORS.index(prev_color)

            if hue_change == 1:  # Addition
                b, a = self.pop(), self.pop()
                self.push(a + b)
            elif hue_change == 2:  # Subtraction
                b, a = self.pop(), self.pop()
                self.push(a - b)
            elif hue_change == 3:  # Multiplication
                b, a = self.pop(), self.pop()
                self.push(a * b)
            elif hue_change == 4:  # Division (handle zero division)
                b, a = self.pop(), self.pop()
                self.push(a // b if b != 0 else 0)
            elif hue_change == 5:  # Modulus (handle zero division)
                b, a = self.pop(), self.pop()
                self.push(a % b if b != 0 else 0)

    def move(self):
        """Move in the current direction."""
        x, y = self.position
        dx, dy = self.direction
        new_x, new_y = x + dx, y + dy

        # Handle movement into black (blocked)
        if self.get_color(new_x, new_y) == "\033[30m":
            self.direction = (-dx, -dy)  # Reverse direction
            return

        if 0 <= new_x < len(self.board[0]) and 0 <= new_y < len(self.board):
            self.position = (new_x, new_y)
        else:  # If out of bounds, change direction
            self.direction = (-dx, -dy)  # Reverse direction

    def run_step(self, modified_x=None, modified_y=None):
        """
        Validate the next instruction and check if re-execution is needed.

        :param modified_x: X-coordinate of modification (if any).
        :param modified_y: Y-coordinate of modification (if any).
        :return: True if instruction is valid, False if invalid.
        """
        if not self.running:
            return False

        x, y = self.position

        # If the modification affects past execution, reset execution cache
        if (modified_x, modified_y) in self.execution_cache:
            self.execution_cache.clear()
            self.position = (0, 0)  # Restart from the beginning

        # Validate current position
        if not self.is_valid(x, y):
            return False

        # Move and execute command
        prev_color = self.get_color(x, y)
        self.move()
        curr_color = self.get_color(*self.position)
        self.execute_command(prev_color, curr_color)

        # Mark execution
        self.execution_cache.add((x, y))

        return True

    def run(self):
        """Execute the entire Piet program step by step."""
        while self.running:
            valid = self.run_step()
            if not valid:
                break  # Stop execution on invalid instruction

        print("Final Stack:", self.stack)
