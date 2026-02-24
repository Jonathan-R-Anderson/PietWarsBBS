from flask import Flask
from routes import register_routes
from board import GameBoard
from game import BattleManager
from state import state
import os


def create_app():
    """Initialize Flask app and register routes."""
    app = Flask(__name__)
    width = int(os.getenv("BOARD_WIDTH", 40))
    height = int(os.getenv("BOARD_HEIGHT", 20))

    board = GameBoard(width=width, height=height)
    battle_manager = BattleManager(board)
    state.battle_manager = battle_manager

    register_routes(app, board, battle_manager)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
