"""Configuration du logging."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from .paths import DATA_DIR

_initialized = False


def setup_logging(level: str = "INFO") -> None:
    """Configure le logging une seule fois (stdout + fichier data/app.log)."""
    global _initialized
    if _initialized:
        return

    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if level.upper() not in valid_levels:
        level = "INFO"
    log_level = getattr(logging, level.upper())
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    # Sortie console (stdout)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Fichier rotatif dans data/ (lisible via File Station)
    try:
        log_file = DATA_DIR / "app.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=2 * 1024 * 1024, backupCount=2,
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as e:
        print(f"Impossible de créer le fichier de log : {e}", file=sys.stderr)

    _initialized = True


def get_logger(name: str = "google2radicale") -> logging.Logger:
    """Retourne le logger principal."""
    return logging.getLogger(name)
