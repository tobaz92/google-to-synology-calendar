"""Chargement et validation de la configuration YAML."""

import logging
import os

import yaml

from .paths import CONFIG_PATH

log = logging.getLogger("google2radicale")

REQUIRED_KEYS = ("radicale", "calendars")
REQUIRED_RADICALE_KEYS = ("url", "username")
REQUIRED_MAPPING_KEYS = ("google_calendar_id", "radicale_calendar")


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

    _validate_radicale(cfg["radicale"])
    _validate_calendars(cfg["calendars"])

    poll = cfg.get("poll_interval", 300)
    if not isinstance(poll, (int, float)) or poll < 30:
        raise ValueError("poll_interval doit être >= 30 secondes")


def _validate_radicale(radicale: dict) -> None:
    """Valide la section radicale, mot de passe compris (fail-fast au boot)."""
    for key in REQUIRED_RADICALE_KEYS:
        if key not in radicale:
            raise ValueError(f"Clé radicale.{key} manquante dans config.yaml")

    url = radicale["url"]
    if not url.startswith(("https://", "http://")):
        raise ValueError(
            f"radicale.url invalide (doit commencer par http:// ou https://) : {url}"
        )
    if url.startswith("http://"):
        log.warning(
            "radicale.url utilise HTTP — les credentials transitent en clair. "
            "OK en local sur le NAS, à éviter à travers le réseau."
        )

    if not (os.environ.get("RADICALE_PASSWORD") or radicale.get("password")):
        raise ValueError(
            "Mot de passe Radicale manquant : définis radicale.password dans "
            "config.yaml ou RADICALE_PASSWORD en variable d'environnement"
        )


def _validate_calendars(calendars) -> None:
    """Valide chaque mapping google_calendar_id → radicale_calendar.

    Les doublons sont rejetés : deux mappings partageant un même calendrier
    (d'un côté ou de l'autre) partageraient syncTokens et table d'état, et
    se contamineraient mutuellement. Le fan-out n'est pas supporté.
    """
    if not isinstance(calendars, list) or not calendars:
        raise ValueError("config.yaml : 'calendars' doit être une liste non vide")

    seen = {key: set() for key in REQUIRED_MAPPING_KEYS}
    for i, mapping in enumerate(calendars):
        if not isinstance(mapping, dict):
            raise ValueError(f"config.yaml : calendars[{i}] doit être un dictionnaire")
        for key in REQUIRED_MAPPING_KEYS:
            if key not in mapping:
                raise ValueError(
                    f"config.yaml : clé '{key}' manquante dans calendars[{i}]"
                )
            if mapping[key] in seen[key]:
                raise ValueError(
                    f"config.yaml : {key} dupliqué dans calendars : {mapping[key]}"
                )
            seen[key].add(mapping[key])
