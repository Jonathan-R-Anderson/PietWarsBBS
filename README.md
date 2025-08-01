# PietWars V2

This project is organized as a Python package under `src` with three main components:

- `api` – Flask API serving board operations and Piet interpreter execution
- `modules` – utility modules, including networking and a Textual-based loading effect
- `renderer` – Textual UI for interacting with the board and the BBS menu

Shared state for the API is maintained in `src/api/state.py` to avoid scattered
global variables.

## Running the BBS

Run the Textual BBS interface to access boards and launch the PietWars game:

```bash
python -m src.renderer.bbs_app
```
