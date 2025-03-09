from flask import Blueprint, request, jsonify
from driver import PietInterpreter  # Import interpreter

interpreter_bp = Blueprint("interpreter", __name__)  # Create a Flask Blueprint

# Global Interpreter Instance
piet_interpreter = None

@interpreter_bp.route("/start_piet", methods=["POST"])
def start_piet():
    """Initialize the Piet interpreter with the current game board."""
    global piet_interpreter

    data = request.json
    board = data.get("board")
    colors = data.get("colors")

    if not board or not colors:
        return jsonify({"error": "Missing board or colors"}), 400

    piet_interpreter = PietInterpreter(board, colors)
    return jsonify({"success": True, "message": "Piet interpreter initialized"}), 200


@interpreter_bp.route("/step_piet", methods=["POST"])
def step_piet():
    """Execute a single step in the Piet interpreter."""
    global piet_interpreter

    if piet_interpreter is None:
        return jsonify({"error": "Interpreter not initialized"}), 400

    if not piet_interpreter.running:
        return jsonify({"error": "Program already completed"}), 400

    piet_interpreter.run_step()
    return jsonify({
        "success": True,
        "position": piet_interpreter.position,
        "stack": piet_interpreter.stack,
        "running": piet_interpreter.running
    })


@interpreter_bp.route("/run_piet", methods=["POST"])
def run_piet():
    """Run the Piet interpreter until completion."""
    global piet_interpreter

    if piet_interpreter is None:
        return jsonify({"error": "Interpreter not initialized"}), 400

    piet_interpreter.run()
    return jsonify({
        "success": True,
        "message": "Program executed completely",
        "final_stack": piet_interpreter.stack
    })


@interpreter_bp.route("/get_stack", methods=["GET"])
def get_stack():
    """Return the current stack of the interpreter."""
    global piet_interpreter

    if piet_interpreter is None:
        return jsonify({"error": "Interpreter not initialized"}), 400

    return jsonify({"stack": piet_interpreter.stack})


