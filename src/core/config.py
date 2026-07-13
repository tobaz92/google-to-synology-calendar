"""Chargement et validation de la configuration YAML."""

import logging

import yaml

from .paths import CONFIG_PATH

log = logging.getLogger("google2radicale")

REQUIRED_KEYS = ("radicale", "calendars")
REQUIRED_RADICALE_KEYS = ("url", "username")


def load_config() -> dict:
    """Charge, valide et retourne la configuration depuis config.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"{CONFIG_PATH} introuvable. "
            "Copie config.yaml.example → data/config.yaml et remplis-le."
        )

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    _validate(cfg)
    return cfg


def _validate(cfg) -> None:
    """Valide la structure minimale de la configuration."""
    if not isinstance(cfg, dict):
        raise ValueError("config.yaml invalide (doit être un dictionnaire YAML)")

    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ValueError(f"Clé obligatoire manquante dans config.yaml : '{key}'")

    for key in REQUIRED_RADICALE_KEYS:
        if key not in cfg["radicale"]:
            raise ValueError(f"Clé radicale.{key} manquante dans config.yaml")

    if not isinstance(cfg["calendars"], list) or not cfg["calendars"]:
        raise ValueError("config.yaml : 'calendars' doit être une liste non vide")

    url = cfg["radicale"]["url"]
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"radicale.url invalide (doit commencer par https://): {url}")
    if url.startswith("http://"):
        log.warning(
            "radicale.url utilise HTTP — les credentials transitent en clair. "
            "OK en local sur le NAS, à éviter à travers le réseau."
        )

    poll = cfg.get("poll_interval", 300)
    if not isinstance(poll, (int, float)) or poll < 30:
        raise ValueError("poll_interval doit être >= 30 secondes")
