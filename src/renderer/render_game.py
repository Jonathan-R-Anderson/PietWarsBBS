import requests
from functools import partial
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, Header, Footer
from textual.widget import Widget
from textual.reactive import reactive, Reactive
from textual.command import Provider, Hit, Hits
from textual.worker import Worker, WorkerState
from textual.timer import Timer
from textual import events
from textual import work
import asyncio
import aiohttp
from rich.console import RenderableType
from rich.text import Text
import thefuzz
import multiprocessing

class CodelOverlay(Widget):
    """Widget to display the index of the current codel."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.codel_position = None

    def set_codel_position(self, position: tuple[int, int]) -> None:
        """Set the current codel position and refresh the widget."""
        self.codel_position = position
        self.refresh()

    def render(self) -> RenderableType:
        if self.codel_position:
            x, y = self.codel_position
            return Text(f"Current Codel: ({x}, {y})", style="bold white on red")
        return Text("")

class Marquee(Static):
    def __init__(self, content: str, speed: float = 0.1, **kwargs):
        super().__init__(content, **kwargs)
        self.text = content
        self.speed = speed
        self.text_offset = 0

    def on_mount(self) -> None:
        self.set_interval(self.speed, self.scroll_text)

    def scroll_text(self) -> None:
        self.text_offset+=1
        if self.text_offset > len(self.text):
            self.text_offset = 0
        self.update(self.text[self.text_offset:] + " " + self.text[:self.text_offset])

class BoardView(VerticalScroll):
    """Scrollable and zoomable board display."""
    
    zoom_level = reactive(1)  # Initial zoom level
    current_codel_position = reactive((None, None))  # Position of the current codel
    flash_state = reactive(False)

    def on_mount(self) -> None:
        """Initialize and start updating the board."""
        self.static_widget = Static("")
        self.mount(self.static_widget)
        self.update_board()
        self.set_interval(1, self.update_board)
        self.animate_codel_highlight()

    def toggle_flash(self) -> None:
        self.flash_state = not self.flash_state

    def update_board(self) -> None:
        board_data = self.fetch_board()
        if not board_data:
            self.static_widget.update("[red]Failed to fetch board data.[/red]")
            return

        grid = board_data.get("board", [])
        dimensions = self.fetch_board_dimensions()

        if not dimensions:
            self.static_widget.update("[red]Failed to fetch board dimensions.[/red]")
            return

        board_str = ""
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                color = cell if cell else "white"
                block = "█" * self.zoom_level
                if (x, y) == self.current_codel_position:
                    if self.flash_state:
                        board_str += f"[bold][{color} on black]{block}[/][/]"
                    else:
                        board_str += f"[{color}]{block}[/]"
                else:
                    board_str += f"[{color}]{block}[/]"
            board_str += "\n"

        self.static_widget.update(board_str)

    def adjust_zoom(self, level: int) -> None:
        """Adjust the zoom level and update the board."""
        self.zoom_level = max(1, self.zoom_level + level)
        self.update_board()

    def fetch_board(self):
        """Fetch the latest board state from the API."""
        try:
            API_URL = "http://127.0.0.1:5000/get_board"
            response = requests.get(API_URL)
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            pass  
        return {"board": [["white" for _ in range(10)] for _ in range(10)]}  # Default 10x10 board

    def fetch_board_dimensions(self):
        """Fetch the board dimensions from the API."""
        try:
            API_URL = "http://127.0.0.1:5000/get_dimensions"
            response = requests.get(API_URL)
            if response.status_code == 200:
                return response.json()
        except requests.ConnectionError:
            pass  
        return {"rows": 10, "cols": 10}  # Default dimensions

    @work
    async def animate_codel_highlight(self) -> None:
        """Animate the highlight of the current codel to create a flashing effect."""
        while True:
            if self.current_codel_position != (None, None):
                self.flash_state = not self.flash_state
                self.refresh()
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(1)


    def render(self) -> RenderableType:
        """Render the board with the current codel highlighted."""
        grid = self.fetch_board().get("board", [])
        board_text = Text()

        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                color = cell if cell else "white"
                block = "█" * self.zoom_level
                if (x, y) == self.current_codel_position:
                    board_text.append(block, style=f"bold {color} on red")
                else:
                    board_text.append(block, style=color)
            board_text.append("\n")

        return board_text
    
class ZoomCommandProvider(Provider):
    """Command provider for zooming in and out."""

    async def search(self, query: str) -> Hits:
        """Search for zoom commands."""
        matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, BoardApp)

        commands = [
            ("zoom in", "Increase the zoom level", partial(app.zoom_in)),
            ("zoom out", "Decrease the zoom level", partial(app.zoom_out)),
        ]

        for command, help_text, callback in commands:
            score = matcher.match(command)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),
                    callback,
                    help=help_text,
                )
def f_ratio(query, command, manager):
    manager['f_ratio'] = thefuzz.ratio(query, command)

def p_ratio(query, command, manager):
    manager['p_ratio'] = thefuzz.partial_ratio(query, command)

def tso_ratio(query, command, manager):
    manager['tso_ratio'] = thefuzz.token_sort_ratio(query, command)

def tse_ratio(query, command, manager):
    manager['tse_ratio'] = thefuzz.token_set_ratio(query, command)

class PietCommandProvider(Provider):
    """Command provider for Piet interpreter controls."""


    async def search(self, query: str) -> Hits:
        """Search for Piet interpreter commands."""
        query = query.lower()
        #matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, BoardApp)

        commands = [
            ("start execution", "Start the Piet program execution", partial(app.start_execution)),
            ("stop execution", "Stop the Piet program execution", partial(app.stop_execution)),
            ("current codel", "Fetch the current codel being executed", partial(app.fetch_current_codel)),
            ("board status", "Fetch the status of the program being loaded", partial(app.board_status)),
            ("initialize piet", "Initialize the piet interpreter", partial(app.initialize_piet)),
            ("zoom in", "Increase the zoom level", partial(app.zoom_in)),
            ("zoom out", "Decrease the zoom level", partial(app.zoom_out)),
        ]
        '''
        for command, help_text, callback in commands:
            score = matcher.match(command)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),
                    callback,
                    help=help_text,
                )
        '''
        manager = multiprocessing.Manager()
        return_dict = manager.dict()


        for command, help_text, callback in commands:
            f_ratio = multiprocessing.Process(target=f_ratio, args=(query, command, manager))
            p_ratio = multiprocessing.Process(target=p_ratio, args=(query, command, manager))
            tso_ratio = multiprocessing.Process(target=tso_ratio, args=(query, command, manager))
            tse_ratio = multiprocessing.Process(target=tse_ratio, args=(query, command, manager))
            f_ratio.start()
            p_ratio.start()
            tso_ratio.start()
            tse_ratio.start()
            f_ratio.join()
            p_ratio.join()
            tso_ratio.join()
            tse_ratio.join()
            score = sum(return_dict.values())

            if score > 0:  # Case-insensitive prefix check
                yield Hit(
                    1.0,  # Assign a fixed score since we're not using fuzzy matching
                    command,  # The command itself
                    callback,  # The function to execute
                    help=help_text,  # Help text for the command
                )

class BoardApp(App):
    """Textual App to display the board with zoom and command palette."""

    CSS = '\n'.join(open("styles.css").readlines())

    COMMANDS = {PietCommandProvider}

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Header()
        with Container():
            self.board_view = BoardView(id="left_panel")
            yield self.board_view
            self.codel_overlay = CodelOverlay(id="codel_overlay")
            yield self.codel_overlay
            yield Static("Middle Panel Content", id="middle_panel")
            yield Static("Right Panel Content", id="right_panel")

        self.marquee = Marquee("Piet Program Output: ", id="marquee")
        yield self.marquee
        yield Footer()


    def on_mount(self) -> None:
        """Set up recurring tasks on mount."""
        self.set_interval(1, self.update_marquee)  # Update marquee every second
        self.set_interval(0.5, self.update_current_codel)  # Update current codel every half second

    def update_current_codel(self) -> None:
        """Fetch the current codel position from the API and update the board view."""
        try:
            API_URL = "http://127.0.0.1:5000/current_codel"
            response = requests.get(API_URL)
            if response.status_code == 200:
                data = response.json()
                current_codel = data.get('current_codel', None)
                if current_codel:
                    self.board_view.current_codel_position = tuple(current_codel)
                    #self.codel_overlay.set_codel_position(tuple(current_codel))
        except requests.ConnectionError:
            pass  # Handle connection errors if necessary

    def update_marquee(self) -> None:
        """Fetch the latest program output and update the marquee."""
        try:
            API_URL = "http://127.0.0.1:5000/get_output"
            response = requests.get(API_URL)
            if response.status_code == 200:
                output = response.json().get('output', '')
                self.marquee.text = f"Piet Program Output: {output}"
            else:
                self.marquee.text = "Error fetching program output."
        except requests.ConnectionError:
            self.marquee.text = "Failed to connect to API."

    def zoom_in(self) -> None:
        """Increase the zoom level."""
        self.board_view.adjust_zoom(1)

    def zoom_out(self) -> None:
        """Decrease the zoom level."""
        self.board_view.adjust_zoom(-1)

    def refresh_current_codel(self) -> None:
        """Fetch and display the current codel being executed."""
        try:
            API_URL = "http://127.0.0.1:5000/current_codel"
            response = requests.get(API_URL)
            if response.status_code == 200:
                data = response.json()
                current_codel = data.get('current_codel', 'Unknown')
                self.notify(f"Current codel: {current_codel}")
            else:
                self.notify(f"Error fetching current codel: {response.status_code}")
        except requests.ConnectionError:
            self.notify("Failed to connect to API.")
        except ValueError:
            self.notify("Invalid response received from API.")


    def start_execution(self) -> None:
        """Start the Piet program execution via API."""
        try:
            API_URL = "http://127.0.0.1:5000/start_execution"
            response = requests.get(API_URL)
            if response.status_code == 200:
                self.notify("Execution started.")
                self.refresh_current_codel()
                # Assuming the API returns the initial output
                initial_output = response.json().get('output', '')
                self.marquee.text = f"Piet Program Output: {initial_output}"
            else:
                self.notify(f"Error: {response.json().get('error', 'Unknown error')}")
        except requests.ConnectionError:
            self.notify("Failed to connect to API.")

    def stop_execution(self) -> None:
        """Stop the Piet program execution via API."""
        try:
            API_URL = "http://127.0.0.1:5000/stop_execution"
            response = requests.get(API_URL)
            if response.status_code == 200:
                self.notify("Execution stopped.")
            else:
                self.notify(f"Error: {response.json().get('error', 'Unknown error')}")
        except requests.ConnectionError:
            self.notify("Failed to connect to API.")

    def board_status(self) -> None:
        try:
            BOARD_STATUS_API_URL = "http://127.0.0.1:5000/board_status"
            response = requests.get(BOARD_STATUS_API_URL)
            if (response.status_code == 200):
                self.notify("Status: Loaded")
            else:
                self.notify("Status: Not loaded")
        except requests.ConnectionError:
            self.notify("Failed to connect to API.")
        except ValueError:
            self.notify("Invalid JSON response from API.")
        

    def initialize_piet(self) -> None:
        try:
            LOAD_PIET_API_URL = "http://127.0.0.1:5000/load_piet"
            response = requests.get(LOAD_PIET_API_URL)
            if (response.status_code == 200):
                self.notify("Piet interpreter started")
            else:
                self.notify("Error: Interpreter not loaded")
        except requests.ConnectionError:
            self.notify("Failed to connect to API.")
        except ValueError:
            self.notify("Invalid JSON response from API.")

        
    def fetch_current_codel(self) -> None:
        """Fetch the current codel being executed via API."""
        try:
            CODEL_API_URL = "http://127.0.0.1:5000/current_codel"
            response = requests.get(CODEL_API_URL)
            if response.status_code == 200:
                data = response.json()
                current_codel = data.get('current_codel', 'Unknown')
                self.notify(f"Current codel: {current_codel}")
            else:
                self.notify(f"Error: {response.status_code} - {response.text}")

        except requests.ConnectionError:
            self.notify("Failed to connect to API.")
        except ValueError:
            self.notify("Invalid JSON response from API.")




if __name__ == "__main__":
    BoardApp().run()
