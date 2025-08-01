from dataclasses import dataclass, field
import threading

@dataclass
class AppState:
    """Container for shared application state used by API routes."""
    interpreter: object | None = None
    interpreter_lock: threading.Lock = field(default_factory=threading.Lock)
    execution_thread: threading.Thread | None = None
    execution_lock: threading.Lock = field(default_factory=threading.Lock)
    stop_execution_flag: threading.Event = field(default_factory=threading.Event)
    interpreter_output: str = ""
    output_lock: threading.Lock = field(default_factory=threading.Lock)
    terminal_sizes: dict = field(default_factory=dict)
    previous_terminal_size: tuple[int | None, int | None] = (None, None)

state = AppState()
