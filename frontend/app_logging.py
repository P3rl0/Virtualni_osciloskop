"""Small logging setup shared by the frontend.

The application should be usable without inspecting the terminal, but hardware
and configuration problems still need a persistent diagnostic trail.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG_DIR = Path.cwd() / "logs"
LOG_FILE = LOG_DIR / "oscilloscope.log"


def setup_logging() -> None:
    """Configure root logging once.

    Safe to call multiple times. Existing handlers are left in place so tests or
    host applications can override logging behavior.
    """
    if logging.getLogger().handlers:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
