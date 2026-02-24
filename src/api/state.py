from dataclasses import dataclass, field
import threading
from typing import Optional, Tuple


@dataclass
class AppState:
    """Container for shared application state used by API routes."""
    interpreter: Optional[object] = None
    interpreter_lock: threading.Lock = field(default_factory=threading.Lock)
    execution_thread: Optional[threading.Thread] = None
    execution_lock: threading.Lock = field(default_factory=threading.Lock)
    stop_execution_flag: threading.Event = field(
        default_factory=threading.Event
    )
    interpreter_output: str = ""
    output_lock: threading.Lock = field(default_factory=threading.Lock)
    terminal_sizes: dict = field(default_factory=dict)
    previous_terminal_size: Tuple[Optional[int], Optional[int]] = (None, None)
    battle_manager: Optional[object] = None


state = AppState()
