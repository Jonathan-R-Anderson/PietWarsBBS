# PietWars V2

This project is organized as a Python package under `src` with three main components:

- `api` – Flask API serving board operations and Piet interpreter execution
- `modules` – utility modules, including networking and loading effects
- `renderer` – Textual UI for interacting with the board

Shared state for the API is maintained in `src/api/state.py` to avoid scattered
global variables.
