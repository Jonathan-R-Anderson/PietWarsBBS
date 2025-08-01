# PietWars V2

This project is organized as a Python package under `src` with three main components:

- `api` – Flask API serving board operations and Piet interpreter execution
- `modules` – utility modules, including networking and a Textual-based loading effect
- `renderer` – contains the Textual UI and a telnet server for BBS access

Shared state for the API is maintained in `src/api/state.py` to avoid scattered
global variables.

## Running the BBS

Run the Docker Compose setup and connect via telnet to interact with the BBS.

```bash
telnet localhost 1337
```

