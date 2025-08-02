import logging
from pathlib import Path
from typing import Optional

LOG_PATH = Path(__file__).resolve().parent.parent / "pietwars.log"


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """Configure root logging once and return a named logger.

    Logs are written both to STDOUT and to a file in the repository root
    so the host can access them easily.
    """
    if not logging.getLogger().handlers:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(LOG_PATH),
                logging.StreamHandler(),
            ],
        )
    return logging.getLogger(name)
