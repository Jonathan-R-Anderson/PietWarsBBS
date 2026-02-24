"""
PietWars Battle Engine — Corewar-style multi-player combat.

Layout (2-player example, ZONE_SIZE=10, board 40×20):

  ┌────────────┬────────────────────┬────────────┐
  │  P1 ZONE   │    ARENA (center)  │  P2 ZONE   │
  │  (cols 0-9)│   (cols 10-29)     │ (cols 30-39│
  └────────────┴────────────────────┴────────────┘

Each player's Piet program is placed in their edge zone.
Interpreters start at the zone/arena boundary and execute
inward.  When an interpreter enters the arena it claims
(paints) each cell it visits.  Stepping onto an opponent's
claimed cell reverses the interpreter and costs health.
Last interpreter alive wins.
"""

import threading
import time
from typing import Dict, List, Optional

from piet import PietInterpreter
from player import Player, PLAYER_COLORS, PLAYER_ZONES, AVAILABLE_SLOTS

ZONE_SIZE = 10          # Width/height of each player's edge zone
COLLISION_DAMAGE = 10   # Health lost per collision with opponent territory
MAX_CONSECUTIVE_REVERSALS = 50  # Die if stuck this long


class BattleManager:
    def __init__(self, board):
        self.board = board
        self.players: Dict[str, Player] = {}
        self.interpreters: Dict[str, PietInterpreter] = {}
        self.arena_ownership: Dict[tuple, str] = {}   # (x,y) → player_id
        self.running = False
        self.winner: Optional[str] = None
        self.battle_thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()
        self.step_count = 0

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register_player(self, player_id: str, name: str) -> dict:
        with self.lock:
            if player_id not in AVAILABLE_SLOTS:
                return {"error": f"Invalid player id. Use one of: {AVAILABLE_SLOTS}"}
            if player_id in self.players:
                return {"error": "Player already registered"}
            if len(self.players) >= 4:
                return {"error": "Maximum 4 players reached"}

            zone = PLAYER_ZONES[player_id]
            mark_color = PLAYER_COLORS[player_id]
            player = Player(
                id=player_id,
                name=name,
                mark_color=mark_color,
                zone=zone,
            )
            self.players[player_id] = player

            bounds = self.get_zone_bounds(zone)
            return {
                "success": True,
                "player_id": player_id,
                "zone": zone,
                "mark_color": mark_color,
                "zone_bounds": {
                    "x_start": bounds[0],
                    "x_end": bounds[1],
                    "y_start": bounds[2],
                    "y_end": bounds[3],
                },
            }

    def unregister_player(self, player_id: str) -> dict:
        with self.lock:
            if player_id not in self.players:
                return {"error": "Player not found"}
            del self.players[player_id]
            self.interpreters.pop(player_id, None)
            return {"success": True}

    # ------------------------------------------------------------------ #
    # Zone geometry helpers                                                #
    # ------------------------------------------------------------------ #

    def get_zone_bounds(self, zone: str):
        """Return (x_start, x_end, y_start, y_end) for the given zone."""
        w, h = self.board.width, self.board.height
        if zone == "left":
            return (0, ZONE_SIZE, 0, h)
        elif zone == "right":
            return (w - ZONE_SIZE, w, 0, h)
        elif zone == "top":
            return (0, w, 0, ZONE_SIZE)
        elif zone == "bottom":
            return (0, w, h - ZONE_SIZE, h)
        return (0, w, 0, h)

    def get_arena_bounds(self):
        """Return (x_start, x_end, y_start, y_end) of the central arena."""
        w, h = self.board.width, self.board.height
        return (ZONE_SIZE, w - ZONE_SIZE, ZONE_SIZE, h - ZONE_SIZE)

    def is_in_arena(self, x: int, y: int) -> bool:
        ax0, ax1, ay0, ay1 = self.get_arena_bounds()
        return ax0 <= x < ax1 and ay0 <= y < ay1

    def get_start_pos(self, zone: str):
        """Interpreter starts at the zone edge facing into the arena."""
        w, h = self.board.width, self.board.height
        if zone == "left":
            return (ZONE_SIZE - 1, h // 2), (1, 0)
        elif zone == "right":
            return (w - ZONE_SIZE, h // 2), (-1, 0)
        elif zone == "top":
            return (w // 2, ZONE_SIZE - 1), (0, 1)
        elif zone == "bottom":
            return (w // 2, h - ZONE_SIZE), (0, -1)
        return (0, 0), (1, 0)

    # ------------------------------------------------------------------ #
    # Board helpers                                                        #
    # ------------------------------------------------------------------ #

    def reset_arena(self):
        """Clear all arena cells back to white and wipe ownership map."""
        with self.lock:
            ax0, ax1, ay0, ay1 = self.get_arena_bounds()
            for y in range(ay0, ay1):
                for x in range(ax0, ax1):
                    self.board.set_color(x, y, "white")
            self.arena_ownership.clear()

    def get_zone_layout(self) -> dict:
        """Return zone boundary info for each registered player."""
        result = {}
        for pid, player in self.players.items():
            bounds = self.get_zone_bounds(player.zone)
            result[pid] = {
                "zone": player.zone,
                "mark_color": player.mark_color,
                "x_start": bounds[0],
                "x_end": bounds[1],
                "y_start": bounds[2],
                "y_end": bounds[3],
            }
        arena = self.get_arena_bounds()
        result["arena"] = {
            "x_start": arena[0],
            "x_end": arena[1],
            "y_start": arena[2],
            "y_end": arena[3],
        }
        return result

    # ------------------------------------------------------------------ #
    # Battle lifecycle                                                      #
    # ------------------------------------------------------------------ #

    def initialize_interpreters(self):
        with self.lock:
            for pid, player in self.players.items():
                start_pos, start_dir = self.get_start_pos(player.zone)
                interp = PietInterpreter(self.board.board)
                interp.position = start_pos
                interp.direction = start_dir
                player.start_pos = start_pos
                player.start_dir = start_dir
                player.health = 100
                player.alive = True
                player.steps = 0
                player.consecutive_reversals = 0
                self.interpreters[pid] = interp

    def start_battle(self) -> dict:
        with self.lock:
            if self.running:
                return {"error": "Battle already running"}
            if len(self.players) < 2:
                return {"error": "Need at least 2 players to start"}

        self.reset_arena()
        self.initialize_interpreters()
        self.winner = None
        self.step_count = 0

        with self.lock:
            self.running = True

        self.battle_thread = threading.Thread(
            target=self._battle_loop, daemon=True
        )
        self.battle_thread.start()
        return {"success": True, "message": "Battle started!", "players": list(self.players.keys())}

    def stop_battle(self) -> dict:
        with self.lock:
            self.running = False
        if self.battle_thread:
            self.battle_thread.join(timeout=2)
        return {"success": True, "message": "Battle stopped"}

    def _battle_loop(self):
        while True:
            with self.lock:
                if not self.running:
                    break
            winner = self._battle_step()
            if winner is not None:
                with self.lock:
                    self.winner = winner
                    self.running = False
                break
            time.sleep(0.15)

    def _battle_step(self) -> Optional[str]:
        """
        Advance all alive interpreters by one tick.
        Returns winner player_id (or "draw") when the battle ends,
        None while the battle continues.
        """
        with self.lock:
            self.step_count += 1
            alive = [pid for pid, p in self.players.items() if p.alive]

            if len(alive) <= 1:
                return alive[0] if alive else "draw"

            for pid in alive:
                player = self.players[pid]
                interp = self.interpreters[pid]

                # Execute one step
                ok = interp.step()
                if not ok:
                    player.alive = False
                    continue

                player.steps += 1
                x, y = interp.position

                # --- Arena combat ---
                if self.is_in_arena(x, y):
                    cell_key = (x, y)
                    owner = self.arena_ownership.get(cell_key)
                    if owner is None:
                        # Unclaimed cell: claim it
                        self.arena_ownership[cell_key] = pid
                        self.board.set_color(x, y, player.mark_color)
                    elif owner != pid:
                        # Collision with opponent's territory
                        player.health -= COLLISION_DAMAGE
                        # Bounce back
                        dx, dy = interp.direction
                        interp.direction = (-dx, -dy)
                        player.consecutive_reversals += 1
                        if (player.health <= 0 or
                                player.consecutive_reversals >= MAX_CONSECUTIVE_REVERSALS):
                            player.alive = False
                    else:
                        # Own territory
                        player.consecutive_reversals = 0
                else:
                    player.consecutive_reversals = 0

            # Check win condition
            alive_after = [pid for pid, p in self.players.items() if p.alive]
            if len(alive_after) == 1:
                return alive_after[0]
            if len(alive_after) == 0:
                return "draw"
            return None

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict:
        with self.lock:
            players_info = {}
            for pid, player in self.players.items():
                pos = None
                if pid in self.interpreters:
                    pos = list(self.interpreters[pid].position)
                players_info[pid] = {
                    "name": player.name,
                    "alive": player.alive,
                    "health": player.health,
                    "steps": player.steps,
                    "position": pos,
                    "mark_color": player.mark_color,
                    "zone": player.zone,
                    "consecutive_reversals": player.consecutive_reversals,
                }
            return {
                "running": self.running,
                "winner": self.winner,
                "step_count": self.step_count,
                "arena_claimed_cells": len(self.arena_ownership),
                "players": players_info,
            }

    def get_zone_layout(self) -> dict:
        """Return zone boundaries for the UI to overlay player zone info."""
        result = {}
        for pid, player in self.players.items():
            b = self.get_zone_bounds(player.zone)
            result[pid] = {
                "zone": player.zone, "mark_color": player.mark_color,
                "x_start": b[0], "x_end": b[1],
                "y_start": b[2], "y_end": b[3],
            }
        ab = self.get_arena_bounds()
        result["arena"] = {
            "x_start": ab[0], "x_end": ab[1],
            "y_start": ab[2], "y_end": ab[3],
        }
        return result
