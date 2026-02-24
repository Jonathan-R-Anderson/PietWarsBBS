from dataclasses import dataclass, field
from typing import Optional, Tuple

# Player slot → mark color used to paint arena cells
PLAYER_COLORS = {
    "p1": "red",
    "p2": "blue",
    "p3": "green",
    "p4": "yellow",
}

# Player slot → which edge zone they occupy
PLAYER_ZONES = {
    "p1": "left",
    "p2": "right",
    "p3": "top",
    "p4": "bottom",
}

AVAILABLE_SLOTS = list(PLAYER_ZONES.keys())


@dataclass
class Player:
    id: str                          # "p1" / "p2" / "p3" / "p4"
    name: str
    mark_color: str                  # Color painted into arena on visit
    zone: str                        # "left" / "right" / "top" / "bottom"
    health: int = 100
    alive: bool = True
    steps: int = 0
    consecutive_reversals: int = 0
    start_pos: Tuple[int, int] = (0, 0)
    start_dir: Tuple[int, int] = (1, 0)
