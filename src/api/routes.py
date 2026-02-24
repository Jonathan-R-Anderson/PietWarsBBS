import sys
import os
from flask import request, jsonify
from piet import PietInterpreter
from PIL import Image
import requests as req_lib
import numpy as np
import threading
import time

from state import state

COLOR_MAPPING = {
    (255, 0, 0): "red",
    (0, 255, 0): "green",
    (0, 0, 255): "blue",
    (255, 255, 0): "yellow",
    (255, 0, 255): "magenta",
    (0, 255, 255): "cyan",
    (255, 255, 255): "white",
    (0, 0, 0): "black",
}


def closest_color(rgb):
    r, g, b = rgb
    closest_name = None
    min_distance = float("inf")
    for (cr, cg, cb), color_name in COLOR_MAPPING.items():
        distance = np.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)
        if distance < min_distance:
            min_distance = distance
            closest_name = color_name
    return closest_name


def validate_modification(board, x, y, new_color):
    return True


def modify_board(board, x, y, color):
    if validate_modification(board, x, y, color):
        success = board.set_color(x, y, color)
        return {"success": success, "board": board.board}, 200 if success else 400
    return {"error": "Invalid Piet instruction"}, 400


def register_routes(app, board, battle_manager=None):
    """Registers API routes for the game board and battle system."""

    # ------------------------------------------------------------------ #
    # Board / color routes                                                 #
    # ------------------------------------------------------------------ #

    @app.route("/set_color", methods=["POST"])
    def set_color():
        data = request.json
        x, y, color = data.get("x"), data.get("y"), data.get("color")
        if x is None or y is None or color is None:
            return jsonify({"error": "Missing x, y, or color"}), 400
        result, status = modify_board(board, x, y, color)
        if status == 200:
            board.board_loaded = True
        return jsonify(result), status

    @app.route("/clear_color", methods=["POST"])
    def clear_color():
        data = request.json
        x, y = data.get("x"), data.get("y")
        if x is None or y is None:
            return jsonify({"error": "Missing x or y"}), 400
        board.clear_color(x, y)
        return jsonify({"success": True, "board": board.board}), 200

    @app.route("/get_board", methods=["GET"])
    def get_board():
        return jsonify({"board": board.board, "revision": board.revision}), 200

    @app.route("/get_board_changes", methods=["GET"])
    def get_board_changes():
        try:
            since = int(request.args.get("since", "-1"))
        except ValueError:
            return jsonify({"error": "Invalid since revision"}), 400

        changes, too_old = board.get_changes_since(since)
        if too_old or since < 0:
            return jsonify({
                "full": True,
                "revision": board.revision,
                "board": board.board,
                "changes": [],
            }), 200

        return jsonify({
            "full": False,
            "revision": board.revision,
            "changes": changes,
        }), 200

    @app.route("/get_dimensions", methods=["GET"])
    def get_dimensions():
        return jsonify({"rows": board.height, "cols": board.width}), 200

    @app.route("/render", methods=["GET"])
    def render_board():
        return f"<pre>{board.render()}</pre>", 200

    @app.route("/set_terminal_size", methods=["POST"])
    def set_terminal_size():
        data = request.json
        rows = data.get("rows")
        cols = data.get("cols")
        if rows is None or cols is None:
            return jsonify({"error": "Missing terminal size parameters"}), 400
        if not isinstance(rows, int) or not isinstance(cols, int) or rows <= 0 or cols <= 0:
            return jsonify({"error": "Invalid terminal size values"}), 400
        client_ip = request.remote_addr
        state.terminal_sizes[client_ip] = {"rows": rows, "cols": cols}
        return jsonify({"message": "Terminal size updated", "rows": rows, "cols": cols}), 200

    @app.route("/get_terminal_size", methods=["GET"])
    def get_terminal_size():
        client_ip = request.remote_addr
        terminal_size = state.terminal_sizes.get(client_ip, {"rows": 100, "cols": 200})
        return jsonify(terminal_size)

    @app.route("/upload_image", methods=["POST"])
    def upload_image():
        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        terminal_size_response = req_lib.get("http://localhost:5000/get_terminal_size")
        if terminal_size_response.status_code != 200:
            return jsonify({"error": "Unable to fetch terminal size"}), 500

        terminal_size = terminal_size_response.json()
        rows, cols = terminal_size.get("rows", 0), terminal_size.get("cols", 0)

        if rows <= 0 or cols <= 0:
            return jsonify({"error": "Invalid terminal size received"}), 400

        if state.previous_terminal_size == (None, None) or state.previous_terminal_size != (rows, cols):
            state.previous_terminal_size = (rows, cols)

        image = Image.open(request.files["image"]).convert("RGB")
        image = image.resize((max(1, cols), max(1, rows)))
        width, height = image.size

        for y in range(height):
            for x in range(width):
                pixel = image.getpixel((x, y))
                color_name = closest_color(pixel)
                if color_name:
                    board.set_color(x, y, color_name)

        board.board_loaded = True
        return jsonify({"message": "Image processed successfully"}), 200

    # ------------------------------------------------------------------ #
    # Piet interpreter routes                                              #
    # ------------------------------------------------------------------ #

    @app.route('/start_execution', methods=['GET'])
    def start_execution():
        if state.interpreter is None:
            return jsonify({"error": "Interpreter not initialized"}), 400
        if state.execution_thread and state.execution_thread.is_alive():
            return jsonify({"message": "Execution is already running"}), 400

        state.stop_execution_flag.clear()

        def execute_program():
            while not state.interpreter.has_terminated() and not state.stop_execution_flag.is_set():
                with state.execution_lock:
                    state.interpreter.step()
                time.sleep(0.1)

        state.execution_thread = threading.Thread(target=execute_program, daemon=True)
        state.execution_thread.start()
        return jsonify({"message": "Execution started"}), 200

    @app.route('/stop_execution', methods=['GET'])
    def stop_execution():
        if state.execution_thread and state.execution_thread.is_alive():
            state.stop_execution_flag.set()
            state.execution_thread.join(timeout=3)
            return jsonify({"message": "Execution stopped"}), 200
        return jsonify({"message": "No execution is currently running"}), 400

    @app.route('/current_codel', methods=['GET'])
    def current_codel():
        if state.interpreter is None:
            return jsonify({"current_codel": None, "initialized": False}), 200
        with state.execution_lock:
            codel_position = state.interpreter.get_current_codel_position()
            return jsonify({"current_codel": list(codel_position), "initialized": True}), 200

    @app.route('/load_piet', methods=['GET'])
    def load_piet():
        if board.board_loaded:
            with state.interpreter_lock:
                state.interpreter = PietInterpreter(board.board)
                return jsonify({"message": "Interpreter initialized"}), 200
        return jsonify({"error": "Board is not loaded"}), 400

    @app.route('/get_output', methods=['GET'])
    def get_output():
        with state.output_lock:
            if state.interpreter_output:
                return jsonify({"output": state.interpreter_output}), 200
        return jsonify({"error": "No output available"}), 204

    @app.route('/board_status', methods=['GET'])
    def board_status():
        return jsonify({"loaded": board.board_loaded}), 200

    # ------------------------------------------------------------------ #
    # Battle / Corewar routes                                              #
    # ------------------------------------------------------------------ #

    if battle_manager is None:
        return  # No battle manager; skip battle routes

    @app.route('/battle/join', methods=['POST'])
    def join_game():
        data = request.json or {}
        player_id = data.get('player_id')
        name = data.get('name', player_id)
        if not player_id:
            return jsonify({"error": "Missing player_id"}), 400
        result = battle_manager.register_player(player_id, name)
        return jsonify(result), 200 if "success" in result else 400

    @app.route('/battle/leave', methods=['POST'])
    def leave_game():
        data = request.json or {}
        player_id = data.get('player_id')
        if not player_id:
            return jsonify({"error": "Missing player_id"}), 400
        result = battle_manager.unregister_player(player_id)
        return jsonify(result), 200 if "success" in result else 400

    @app.route('/battle/upload_program/<player_id>', methods=['POST'])
    def upload_player_program(player_id):
        """Upload a PNG image as a player's zone program."""
        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        player = battle_manager.players.get(player_id)
        if not player:
            return jsonify({"error": f"Player {player_id} not registered"}), 404

        bounds = battle_manager.get_zone_bounds(player.zone)
        x0, x1, y0, y1 = bounds
        zone_w = x1 - x0
        zone_h = y1 - y0

        image = Image.open(request.files["image"]).convert("RGB")
        image = image.resize((zone_w, zone_h))

        for y in range(zone_h):
            for x in range(zone_w):
                pixel = image.getpixel((x, y))
                color_name = closest_color(pixel)
                if color_name:
                    board.set_color(x0 + x, y0 + y, color_name)

        board.board_loaded = True
        return jsonify({"message": f"Program uploaded for {player_id}"}), 200

    @app.route('/battle/set_color/<player_id>', methods=['POST'])
    def set_player_color(player_id):
        """Set a color within a player's zone."""
        data = request.json or {}
        x, y, color = data.get('x'), data.get('y'), data.get('color')
        if x is None or y is None or color is None:
            return jsonify({"error": "Missing x, y, or color"}), 400

        player = battle_manager.players.get(player_id)
        if not player:
            return jsonify({"error": f"Player {player_id} not found"}), 404

        bounds = battle_manager.get_zone_bounds(player.zone)
        x0, x1, y0, y1 = bounds
        if not (x0 <= x < x1 and y0 <= y < y1):
            return jsonify({"error": "Coordinates outside player zone"}), 400

        board.set_color(x, y, color)
        board.board_loaded = True
        return jsonify({"success": True}), 200

    @app.route('/battle/start', methods=['GET'])
    def start_battle():
        result = battle_manager.start_battle()
        return jsonify(result), 200 if "success" in result else 400

    @app.route('/battle/stop', methods=['GET'])
    def stop_battle():
        result = battle_manager.stop_battle()
        return jsonify(result), 200

    @app.route('/battle/status', methods=['GET'])
    def battle_status():
        return jsonify(battle_manager.get_status()), 200

    @app.route('/battle/winner', methods=['GET'])
    def get_winner():
        return jsonify({"winner": battle_manager.winner}), 200

    @app.route('/battle/layout', methods=['GET'])
    def get_layout():
        return jsonify(battle_manager.get_zone_layout()), 200

    @app.route('/battle/reset', methods=['POST'])
    def reset_battle():
        battle_manager.stop_battle()
        battle_manager.arena_ownership.clear()
        battle_manager.players.clear()
        battle_manager.interpreters.clear()
        battle_manager.winner = None
        battle_manager.step_count = 0
        battle_manager.reset_arena()
        return jsonify({"success": True, "message": "Battle reset"}), 200
