from flask import request, jsonify

def register_routes(app, board):
    """Registers API routes for the game board."""

    @app.route("/set_color", methods=["POST"])
    def set_color():
        data = request.json
        x, y, color = data.get("x"), data.get("y"), data.get("color")

        if x is None or y is None or color is None:
            return jsonify({"error": "Missing x, y, or color"}), 400

        success = board.set_color(x, y, color)
        return jsonify({"success": success, "board": board.board, "colors": board.colors})

    @app.route("/clear_color", methods=["POST"])
    def clear_color():
        data = request.json
        x, y = data.get("x"), data.get("y")

        if x is None or y is None:
            return jsonify({"error": "Missing x or y"}), 400

        board.clear_color(x, y)
        return jsonify({"success": True, "board": board.board, "colors": board.colors})

    @app.route("/get_board", methods=["GET"])
    def get_board():
        """Return the board with both `board` and `colors`."""
        return jsonify({
            "board": board.board, 
            "colors": board.colors
        })

    @app.route("/render", methods=["GET"])
    def render_board():
        """Return a preformatted ANSI-rendered board for direct terminal viewing."""
        return f"<pre>{board.render()}</pre>"
