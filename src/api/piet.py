class PietInterpreter:
    """Interprets Piet code directly from the game board array."""

    HUE_CYCLE = ["red", "yellow", "green", "cyan", "blue", "magenta"]
    LIGHTNESS_CYCLE = ["light", "normal", "dark"]
    MAX_REVERSALS = 8  # Consecutive reversals before termination (stuck detection)

    def __init__(self, board):
        self.board = board
        self.stack = []
        self.position = (0, 0)
        self.direction = (1, 0)
        self.running = True
        self.execution_cache = set()
        self.reversal_count = 0  # Consecutive reversals; resets on successful move

    def get_color(self, x, y):
        if 0 <= x < len(self.board[0]) and 0 <= y < len(self.board):
            return self.board[y][x]
        return None

    def is_valid(self, x, y):
        if not (0 <= x < len(self.board[0]) and 0 <= y < len(self.board)):
            return False
        color = self.get_color(x, y)
        return color in self.HUE_CYCLE or color in ["white", "black"]

    def push(self, value):
        self.stack.append(value)

    def pop(self):
        return self.stack.pop() if self.stack else 0

    def execute_command(self, prev_color, curr_color):
        if prev_color == curr_color:
            return

        if prev_color in self.HUE_CYCLE and curr_color in self.HUE_CYCLE:
            prev_idx = self.HUE_CYCLE.index(prev_color)
            curr_idx = self.HUE_CYCLE.index(curr_color)
            hue_change = (curr_idx - prev_idx) % len(self.HUE_CYCLE)

            if hue_change == 1:  # ADD
                b, a = self.pop(), self.pop()
                self.push(a + b)
            elif hue_change == 2:  # SUBTRACT
                b, a = self.pop(), self.pop()
                self.push(a - b)
            elif hue_change == 3:  # MULTIPLY
                b, a = self.pop(), self.pop()
                self.push(a * b)
            elif hue_change == 4:  # DIVIDE
                b, a = self.pop(), self.pop()
                self.push(a // b if b != 0 else 0)
            elif hue_change == 5:  # MODULO
                b, a = self.pop(), self.pop()
                self.push(a % b if b != 0 else 0)

    def move(self):
        x, y = self.position
        dx, dy = self.direction
        new_x, new_y = x + dx, y + dy

        if self.get_color(new_x, new_y) == "black":
            self.direction = (-dx, -dy)
            self.reversal_count += 1
            return

        if 0 <= new_x < len(self.board[0]) and 0 <= new_y < len(self.board):
            self.position = (new_x, new_y)
            self.reversal_count = 0  # Successful move; reset reversal counter
        else:
            self.direction = (-dx, -dy)
            self.reversal_count += 1

    def run_step(self, modified_x=None, modified_y=None):
        if not self.running:
            return False

        # Stuck detection: too many consecutive reversals
        if self.reversal_count >= self.MAX_REVERSALS:
            self.running = False
            return False

        x, y = self.position

        if (modified_x, modified_y) in self.execution_cache:
            self.execution_cache.clear()
            self.position = (0, 0)

        if not self.is_valid(x, y):
            self.running = False
            return False

        prev_color = self.get_color(x, y)
        self.move()
        curr_color = self.get_color(*self.position)
        self.execute_command(prev_color, curr_color)

        self.execution_cache.add((x, y))
        return True

    def step(self) -> bool:
        """Execute one step. Returns False when execution should stop."""
        if not self.running:
            return False
        result = self.run_step()
        if not result:
            self.running = False
        return result

    def has_terminated(self) -> bool:
        """Return True if the interpreter has stopped executing."""
        return not self.running

    def run(self):
        """Execute the entire Piet program step by step."""
        while self.running:
            if not self.run_step():
                break
        print("Final Stack:", self.stack)

    def get_current_codel_position(self):
        return self.position
