from flask import Flask
from routes import register_routes
from board import GameBoard  # Ensure this exists

def create_app():
    """Initialize Flask app and register routes."""
    app = Flask(__name__)
    
    board = GameBoard(width=10, height=20)
    
    register_routes(app, board)
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
