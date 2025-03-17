class PietInterpreter:
    """Interprets Piet code directly from the game board array, optimizing execution."""

    # Define the hue and lightness cycles as per Piet specifications
    HUE_CYCLE = ["red", "yellow", "green", "cyan", "blue", "magenta"]
    LIGHTNESS_CYCLE = ["light", "normal", "dark"]

    def __init__(self, board):
        """
        Initialize the interpreter with a game board.

        :param board: 2D list representing the game board with color names.
        """
        self.board = board
        self.stack = []
        self.position = (0, 0)  # Start at top-left
        self.direction = (1, 0)  # Start moving right
        self.running = True
        self.execution_cache = set()  # Stores executed (x, y) positions

    def get_color(self, x, y):
        """Return the color name at position (x, y) or None if out of bounds."""
        if 0 <= x < len(self.board[0]) and 0 <= y < len(self.board):
            return self.board[y][x]
        return None  # Treat out-of-bounds as no-op

    def is_valid(self, x, y):
        """
        Validate if the instruction at (x, y) follows Piet rules.

        Returns:
        - True: If execution is possible
        - False: If illegal instructions are detected
        """
        if not (0 <= x < len(self.board[0]) and 0 <= y < len(self.board)):
            return False  # Out-of-bounds is invalid
        
        color = self.get_color(x, y)
        return color in self.HUE_CYCLE or color in ["white", "black"]

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

        if prev_color in self.HUE_CYCLE and curr_color in self.HUE_CYCLE:
            prev_hue_index = self.HUE_CYCLE.index(prev_color)
            curr_hue_index = self.HUE_CYCLE.index(curr_color)
            hue_change = (curr_hue_index - prev_hue_index) % len(self.HUE_CYCLE)

            # Determine the command based on hue change
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
        if self.get_color(new_x, new_y) == "black":
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

    def get_current_codel_position(self):
        """
        Returns the current position of the interpreter as a tuple (x, y).
        """
        return self.position
