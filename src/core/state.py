"""Gestion de l'état de synchronisation (syncTokens Google)."""

import json
import logging
import os

from .paths import STATE_PATH

log = logging.getLogger("google2radicale")


def load_state() -> dict:
    """Charge l'état de sync depuis le fichier JSON."""
    if not STATE_PATH.exists():
        return {}

    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("sync_state.json corrompu (%s), reset de l'état", e)
        return {}


def save_state(state: dict) -> None:
    """Sauvegarde l'état de sync de manière atomique (write + rename)."""
    tmp_path = STATE_PATH.with_suffix(".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
    tmp_path.rename(STATE_PATH)
