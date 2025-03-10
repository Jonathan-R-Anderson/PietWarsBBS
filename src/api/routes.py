import sys
import os
from flask import request, jsonify
from piet import PietInterpreter  # Import Piet logic



### 🛠 Validation Functions ###

def validate_modification(board, x, y, new_color):
    """
    Validates whether a modification is legal by running the Piet interpreter.
    
    :param board: The current game board object
    :param x: X coordinate of the modification
    :param y: Y coordinate of the modification
    :param new_color: New color to apply
    :return: Boolean (True if valid, False if invalid)
    """
    temp_board = [row[:] for row in board.board]  # Copy board
    temp_colors = [row[:] for row in board.colors]  # Copy colors

    temp_colors[y][x] = new_color  # Apply change

    piet_interpreter = PietInterpreter(temp_board, temp_colors)
    piet_interpreter.run_step()  # Execute one step

    return piet_interpreter.is_valid()


### 🔄 Modification Functions ###

def modify_board(board, x, y, color):
    """
    Modifies the game board if the change is valid.
    
    :param board: The game board object
    :param x: X coordinate
    :param y: Y coordinate
    :param color: New color
    :return: Dictionary with success status and updated board state
    """
    if validate_modification(board, x, y, color):
        success = board.set_color(x, y, color)
        print(f"Success {success} color: {color}")
        return {
            "success": success,
            "board": board.board,
            "colors": board.colors
        }, 200 if success else 400
    else:
        return {"error": "Invalid Piet instruction"}, 400


### 🎮 API Routes ###

def register_routes(app, board):
    """Registers API routes for the game board."""

    @app.route("/set_color", methods=["POST"])
    def set_color():
        """
        API: Modifies a color on the board if it is valid.
        
        Request JSON: { "x": <int>, "y": <int>, "color": "<ANSI Code>" }
        Response: { "success": <bool>, "board": [...], "colors": [...] }
        """
        data = request.json
        x, y, color = data.get("x"), data.get("y"), data.get("color")

        print(f"data: {data}")

        if x is None or y is None or color is None:
            return jsonify({"error": "Missing x, y, or color"}), 400

        return jsonify(*modify_board(board, x, y, color)), 200

    @app.route("/clear_color", methods=["POST"])
    def clear_color():
        """
        API: Clears a color at a specific position.

        Request JSON: { "x": <int>, "y": <int> }
        Response: { "success": True, "board": [...], "colors": [...] }
        """
        data = request.json
        x, y = data.get("x"), data.get("y")

        if x is None or y is None:
            return jsonify({"error": "Missing x or y"}), 400

        board.clear_color(x, y)
        return jsonify({
            "success": True,
            "board": board.board,
            "colors": board.colors
        }), 200

    @app.route("/get_board", methods=["GET"])
    def get_board():
        """
        API: Retrieves the board state.

        Response: { "board": [...], "colors": [...] }
        """
        return jsonify({
            "board": board.board, 
            "colors": board.colors
        }), 200

    @app.route("/render", methods=["GET"])
    def render_board():
        """
        API: Returns an ANSI-rendered board.

        Response: <pre>...</pre>
        """
        return f"<pre>{board.render()}</pre>", 200
