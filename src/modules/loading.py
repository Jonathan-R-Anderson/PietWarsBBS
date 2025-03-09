import random
import curses
import locale
import os

# Set up locale for character encoding
locale.setlocale(locale.LC_ALL, '')
encoding = locale.getpreferredencoding()

def get_env_var(name, default, cast_type=str):
    """Retrieve environment variables safely with default values."""
    value = os.getenv(name, default)
    try:
        return cast_type(value)
    except ValueError:
        return default

# Simple pseudo-random number generator
def random_number_generator():
    """Basic PRNG that generates pseudo-random numbers."""
    seed = 9328475634
    while True:
        seed ^= (seed << 21) & 0xFFFFFFFFFFFFFFFF
        seed ^= (seed >> 35)
        seed ^= (seed << 4) & 0xFFFFFFFFFFFFFFFF
        yield seed

random_gen = random_number_generator()

def randint(_min, _max):
    """Generate a random integer within a given range."""
    num = next(random_gen)
    return (_min + (num % (_max - _min)))

class FallingChar:
    """Represents a single ANSI block with a fading trail effect."""

    matrix_chars = list([get_env_var("block_1", "██"), get_env_var("block_2", "██"),
                         get_env_var("block_3", "██"), get_env_var("block_4", "██"),
                         get_env_var("block_5", "██"), get_env_var("block_6", "██"),
                         get_env_var("block_7", "██"), get_env_var("block_8", "██"),
                         get_env_var("block_9", "██"), get_env_var("block_10", "██")])

    def __init__(self, screen_width):
        self.x = 0
        self.y = 0
        self.speed = 1
        self.char = ' '
        self.trail = []  # Stores previous positions for the fading trail
        self.trail_length = get_env_var("TRAIL_LENGTH", 6, int)  # Length of the trail effect
        self.min_speed = get_env_var("MIN_SPEED", 1, int)
        self.max_speed = get_env_var("MAX_SPEED", 5, int)
        self.reset(screen_width)

    def reset(self, screen_width):
        """Reset character properties to start from the top."""
        self.char = random.choice(self.matrix_chars)
        self.x = randint(1, screen_width - 1)
        self.y = 0
        self.trail.clear()  # Reset trail when restarting
        self.speed = randint(self.min_speed, self.max_speed)
        self.offset = randint(0, self.speed)  # Offset to create staggered movement

    def tick(self, screen, step_count):
        """Move the character downward and create a fading trail."""
        height, width = screen.getmaxyx()

        if self.should_advance(step_count):
            if self.out_of_bounds(width, height):
                return
            
            # Append current position to the trail
            self.trail.append((self.y, self.x, self.char))
            
            # Keep the trail within its max length
            if len(self.trail) > self.trail_length:
                self.trail.pop(0)  # Remove the oldest trail character
            
            # Draw the trail with fading effect
            self.draw_trail(screen)
            
            # Move down
            self.y += 1

            # Choose new character and draw the main block
            self.char = random.choice(self.matrix_chars)
            highlight_color = curses.color_pair(get_env_var("COLOR_CHAR_HIGHLIGHT", 2, int)) if get_env_var("USE_COLORS", False, bool) else curses.A_REVERSE
            if not self.out_of_bounds(width, height):
                screen.addstr(self.y, self.x, self.char, highlight_color)

    def draw_trail(self, screen):
        """Draw the fading trail behind the main falling character."""
        if not self.trail:
            return

        fade_colors = [
            curses.color_pair(get_env_var("COLOR_TRAIL_FADE_1", 3, int)),  # Lightest fade
            curses.color_pair(get_env_var("COLOR_TRAIL_FADE_2", 4, int)),  # Medium fade
            curses.color_pair(get_env_var("COLOR_TRAIL_FADE_3", 5, int)),  # Darkest fade
        ] if get_env_var("USE_COLORS", False, bool) else [curses.A_DIM, curses.A_NORMAL, curses.A_BOLD]

        # Apply fading effect to each trail segment
        for index, (y, x, char) in enumerate(self.trail):
            fade_index = min(index, len(fade_colors) - 1)  # Get the fade level based on index
            try:
                screen.addstr(y, x, char, fade_colors[fade_index])
            except curses.error:
                pass  # Prevent errors when drawing out of bounds

    def out_of_bounds(self, width, height):
        """Reset if character goes beyond screen dimensions."""
        if self.x >= width - 2 or self.y >= height - 2:
            self.reset(width)
            return True
        return False

    def should_advance(self, steps):
        """Determine if the character should move down on this step."""
        return steps % (self.speed + self.offset) == 0

class WindowAnimation:
    """Represents an animated expanding and contracting window effect."""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.step = 0
        self.window_size = get_env_var("WINDOW_SIZE", 10, int)
        self.animation_speed = get_env_var("WINDOW_ANIMATION_SPEED", 1, int)

    def tick(self, screen, steps):
        """Handle window animation expansion."""
        if self.step > self.window_size:
            self.clear_frame(screen)
            return False
        
        # Clear characters inside the window frame
        for i in range(self.animation_speed):
            self.draw_frame(screen, self.step + i, ' ')
        
        # Clear last animation step
        self.clear_frame(screen)
        
        # Expand frame
        self.step += self.animation_speed
        self.draw_frame(screen, self.step)
        return True

    def draw_frame(self, screen, step, clear_char=None):
        """Draw or clear the animation frame."""
        h, w = screen.getmaxyx()
        attrs = curses.A_REVERSE if clear_char is None else curses.A_NORMAL

        if get_env_var("USE_COLORS", False, bool) and attrs == curses.A_REVERSE:
            attrs = curses.color_pair(get_env_var("COLOR_WINDOW", 3, int))

        x1, y1 = self.x - step, self.y - step
        x2, y2 = self.x + step, self.y + step

        for y in (y1, y2):
            for x in range(x1, x2 + 1):
                if 0 <= x < w and 0 <= y < h - 1:
                    screen.addstr(y, x, clear_char or ' ', attrs)

        for x in (x1, x2):
            for y in range(y1, y2 + 1):
                if 0 <= x < w and 0 <= y < h - 1:
                    screen.addstr(y, x, clear_char or ' ', attrs)

    def clear_frame(self, screen):
        """Remove the last drawn frame."""
        self.draw_frame(screen, self.step, ' ')

