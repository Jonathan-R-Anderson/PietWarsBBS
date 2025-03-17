import sys
import os
from flask import request, jsonify
from piet import PietInterpreter  # Import Piet logic
from PIL import Image
import requests
import numpy as np
import threading
import time

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


interpreter = None
interpreter_lock = threading.Lock()
execution_thread = None
execution_lock = threading.Lock()
stop_execution_flag = threading.Event()
interpreter_output = ""
output_lock = threading.Lock()

# Dictionary to store terminal sizes per client IP
terminal_sizes = {}
previous_terminal_size = (None, None)
def closest_color(rgb):
    """Find the closest known color by computing Euclidean distance in RGB space."""
    r, g, b = rgb  # Extract RGB values
    closest_name = None
    min_distance = float("inf")

    for (cr, cg, cb), color_name in COLOR_MAPPING.items():
        distance = np.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)  # Euclidean distance

        if distance < min_distance:
            min_distance = distance
            closest_name = color_name

    return closest_name


def validate_modification(board, x, y, new_color):
    """
    Validates whether a modification is legal by running the Piet interpreter.
    
    :param board: The current game board object
    :param x: X coordinate of the modification
    :param y: Y coordinate of the modification
    :param new_color: New color to apply
    :return: Boolean (True if valid, False if invalid)
    """

    #temp_board = [row[:] for row in board.board]  # Copy board

    #temp_board[y][x] = new_color  # Apply change

    #piet_interpreter = PietInterpreter(temp_board)
    #piet_interpreter.run_step()  # Execute one step

    #return piet_interpreter.is_valid(x, y)

    return True

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
        return {
            "success": success,
            "board": board.board,
        }, 200 if success else 400
    else:
        return {"error": f"Invalid Piet instruction"}, 400


### 🎮 API Routes ###

def register_routes(app, board):
    """Registers API routes for the game board."""

    @app.route("/set_color", methods=["POST"])
    def set_color():
        """
        API: Modifies a color on the board if it is valid.
        
        Request JSON: { "x": <int>, "y": <int>, "color": "<color_name>" }
        Response: { "success": <bool>, "board": [...], "colors": [...] }
        """
        data = request.json
        x, y, color = data.get("x"), data.get("y"), data.get("color")

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
        }), 200

    @app.route("/get_board", methods=["GET"])
    def get_board():
        """
        API: Retrieves the board state.

        Response: { "board": [...], "colors": [...] }
        """
        return jsonify({
            "board": board.board, 
        }), 200
    
    @app.route("/get_dimensions", methods=["GET"])
    def get_dimensions():
        """
        API: Retrieves the board dimensions.

        Response: WxH
        """
        return jsonify({
            "rows": board.height,
            "cols": board.width 
        }), 200
    

    @app.route("/render", methods=["GET"])
    def render_board():
        """
        API: Returns an ANSI-rendered board.

        Response: <pre>...</pre>
        """
        return f"<pre>{board.render()}</pre>", 200

    @app.route("/set_terminal_size", methods=["POST"])
    def set_terminal_size():
        """Receive and store the terminal dimensions from the client."""
        data = request.json
        rows = data.get("rows")
        cols = data.get("cols")

        if rows is None or cols is None:
            return jsonify({"error": "Missing terminal size parameters"}), 400

        if not isinstance(rows, int) or not isinstance(cols, int) or rows <= 0 or cols <= 0:
            return jsonify({"error": "Invalid terminal size values"}), 400

        # Store the terminal size for the client's IP address
        client_ip = request.remote_addr
        terminal_sizes[client_ip] = {"rows": rows, "cols": cols}

        return jsonify({"message": "Terminal size updated", "rows": rows, "cols": cols}), 200


    @app.route("/get_terminal_size", methods=["GET"])
    def get_terminal_size():
        """Return the stored terminal size for the requesting client."""
        client_ip = request.remote_addr
        terminal_size = terminal_sizes.get(client_ip, {"rows": 100, "cols": 200})  # Default if not set

        return jsonify(terminal_size)



    @app.route("/upload_image", methods=["POST"])
    def upload_image():
        """Receives a PNG file, scales it to terminal size, and updates the board."""
        global previous_terminal_size
        DIMENSIONS_API_URL = "http://api:5000/set_dimensions"

        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        # ✅ Fetch terminal size and ensure it's in JSON format
        terminal_size_response = requests.get("http://api:5000/get_terminal_size")

        if terminal_size_response.status_code != 200:
            return jsonify({"error": "Unable to fetch terminal size"}), 500

        terminal_size = terminal_size_response.json()  # ✅ Extract JSON

        rows, cols = terminal_size.get("rows", 0), terminal_size.get("cols", 0)  # Ensure valid defaults

        # ✅ Prevent invalid dimensions (width and height must be > 0)
        if rows <= 0 or cols <= 0:
            return jsonify({"error": "Invalid terminal size received"}), 400

        # ✅ Reset board if terminal size has changed
        if previous_terminal_size == (None, None) or previous_terminal_size != (rows, cols):
            requests.post(DIMENSIONS_API_URL, json={"rows": rows, "cols": cols})  # Reset board size
            previous_terminal_size = (rows, cols)

        # ✅ Load and scale image
        image = Image.open(request.files["image"]).convert("RGB")  # Ensure it's in RGB format
        image = image.resize((max(1, cols), max(1, rows)))  # ✅ Prevent zero-sized images

        width, height = image.size

        for y in range(height):
            for x in range(width):
                pixel = image.getpixel((x, y))  # Get RGB value as a tuple
                color_name = closest_color(pixel)  # 🔥 Find closest match

                if color_name:
                    requests.post(
                        "http://127.0.0.1:5000/set_color",
                        json={"x": x, "y": y, "color": color_name},
                        headers={"Content-Type": "application/json"},
                    )

        board.board_loaded = True
        return jsonify({"message": "Image processed successfully"}), 200



    @app.route('/start_execution', methods=['GET'])
    def start_execution():
        global interpreter, execution_thread
        #data = request.json
        #program = data.get('program')
        #if not program:
        #    return jsonify({"error": "No program provided"}), 400

        if execution_thread and execution_thread.is_alive():
            return jsonify({"message": "Execution is already running"}), 400

        stop_execution_flag.clear()

        def execute_program():
            while not interpreter.has_terminated() and not stop_execution_flag.is_set():
                with execution_lock:
                    interpreter.step()
                time.sleep(0.1)  # Adjust sleep duration as needed

        execution_thread = threading.Thread(target=execute_program, daemon=True)
        execution_thread.start()

        return jsonify({"message": "Execution started"}), 200

    @app.route('/stop_execution', methods=['GET'])
    def stop_execution():
        if execution_thread and execution_thread.is_alive():
            stop_execution_flag.set()
            execution_thread.join()
            return jsonify({"message": "Execution stopped"}), 200
        else:
            return jsonify({"message": "No execution is currently running"}), 400

    @app.route('/current_codel', methods=['GET'])
    def current_codel():
        global interpreter
        if interpreter is None:
            return jsonify({"error": "Interpreter not initialized"}), 400

        with execution_lock:
            codel_position = interpreter.get_current_codel_position()
            return jsonify({"current_codel": codel_position}), 200
        
    @app.route('/load_piet', methods=['GET'])
    def load_piet():
        global interpreter
        if (board.board_loaded):
            with interpreter_lock:
                interpreter = PietInterpreter(board.board)
                return jsonify({"message": "Interpreter initialized"}), 200
        else:
            return jsonify({'error': "Board is not loaded"})

    @app.route('/get_output', methods=['GET'])
    def get_output():
        def fetch_output():
            nonlocal output_data
            with output_lock:
                if interpreter_output:
                    output_data = interpreter_output

        output_data = None
        output_thread = threading.Thread(target=fetch_output)
        output_thread.start()
        output_thread.join(timeout=3)  # Wait for up to 3 seconds

        if output_data is not None:
            return jsonify({"output": output_data}), 200
        else:
            return jsonify({"error": "No output available"}), 204  # No Content
        
    @app.route('/board_status', methods=['GET'])
    def board_status():
        if (board.board_loaded == True):
            return jsonify({"loaded":True}), 200
        else:
            return jsonify({"loaded":False}), 400