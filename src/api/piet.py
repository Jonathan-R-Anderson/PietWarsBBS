class PietInterpreter:
    """Interprets Piet code directly from the game board array."""
    
    # Define Piet color mappings (Hue cycle)
    PIET_COLORS = [
        "\033[31m", "\033[33m", "\033[32m", "\033[36m", "\033[34m", "\033[35m"
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

    def is_valid(self):
        """
        Validate if the board follows proper Piet rules.
        
        Returns:
        - True: If execution is possible
        - False: If illegal instructions are detected
        """
        x, y = self.position

        if not (0 <= x < len(self.board[0]) and 0 <= y < len(self.board)):
            return False  # Out-of-bounds is invalid
        
        curr_color = self.get_color(x, y)
        return curr_color in self.PIET_COLORS  # Only allow valid Piet colors

    def get_color(self, x, y):
        """Return the color at position (x, y) or empty string if out of bounds."""
        if 0 <= x < len(self.board[0]) and 0 <= y < len(self.board):
            return self.colors[y][x]
        return ""  # Treat out-of-bounds as no-op

    def get_symbol(self, x, y):
        """Return the symbol at (x, y), defaulting to empty space."""
        if 0 <= x < len(self.board[0]) and 0 <= y < len(self.board):
            return self.board[y][x]
        return " "  # No-op for out-of-bounds

    def push(self, value):
        """Push a value onto the stack."""
        self.stack.append(value)

    def pop(self):
        """Pop a value from the stack, return 0 if empty."""
        return self.stack.pop() if self.stack else 0

    def execute_command(self, prev_color, curr_color):
        """Determine and execute the Piet command based on color transition."""
        if prev_color == curr_color:  # No color change → Continue moving
            return

        # Get hue shifts from Piet color cycle
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
            elif hue_change == 4:  # Division
                b, a = self.pop(), self.pop()
                self.push(a // b if b != 0 else 0)
            elif hue_change == 5:  # Modulus
                b, a = self.pop(), self.pop()
                self.push(a % b if b != 0 else 0)

    def move(self):
        """Move in the current direction."""
        x, y = self.position
        dx, dy = self.direction
        new_x, new_y = x + dx, y + dy

        if 0 <= new_x < len(self.board[0]) and 0 <= new_y < len(self.board):
            self.position = (new_x, new_y)
        else:  # If out of bounds, change direction
            self.direction = (-dx, -dy)  # Reverse direction

    def run_step(self):
        """Execute one step of the Piet program."""
        if not self.running:
            return
        
        x, y = self.position
        prev_color = self.get_color(x, y)

        self.move()

        new_x, new_y = self.position
        curr_color = self.get_color(new_x, new_y)

        self.execute_command(prev_color, curr_color)

        # Stop if we reach bottom-right
        if self.position == (len(self.board[0]) - 1, len(self.board) - 1):
            self.running = False

    def run(self):
        """Execute the entire Piet program step by step."""
        while self.running:
            self.run_step()

        print("Final Stack:", self.stack)