"""Chemins centralisés du projet."""

import os
from pathlib import Path

_default_data = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(_default_data)))

CONFIG_PATH = DATA_DIR / "config.yaml"
TOKEN_PATH = DATA_DIR / "token.json"
CREDENTIALS_PATH = DATA_DIR / "credentials.json"
STATE_PATH = DATA_DIR / "sync_state.json"
