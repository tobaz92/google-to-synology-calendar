"""Client CalDAV pour Synology Calendar."""

import logging
import os
import re

import caldav

log = logging.getLogger("google2synology")

CALDAV_TIMEOUT = 30  # secondes


def get_caldav_client(config: dict) -> caldav.DAVClient:
    """Crée un client CalDAV connecté au Synology."""
    syn = config["synology"]
    password = os.environ.get("SYNOLOGY_PASSWORD", syn.get("password", ""))

    if not password:
        raise ValueError(
            "Mot de passe Synology manquant. "
            "Définis SYNOLOGY_PASSWORD en variable d'environnement "
            "ou synology.password dans config.yaml."
        )

    verify_ssl = syn.get("verify_ssl", True)
    if not verify_ssl:
        _suppress_ssl_warnings()
        log.warning("Vérification SSL désactivée — risque MITM")
    return caldav.DAVClient(
        url=syn["url"],
        username=syn["username"],
        password=password,
        ssl_verify_cert=verify_ssl,
        timeout=syn.get("timeout", CALDAV_TIMEOUT),
    )


_ssl_warnings_suppressed = False


def _suppress_ssl_warnings():
    """Supprime les warnings SSL urllib3 une seule fois."""
    global _ssl_warnings_suppressed
    if _ssl_warnings_suppressed:
        return
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _ssl_warnings_suppressed = True


def get_or_create_calendar(client: caldav.DAVClient, calendar_name: str):
    """Récupère un calendrier existant ou le crée.
    Si plusieurs calendriers portent le même nom, préfère celui
    créé via l'interface (URL courte) plutôt qu'un fantôme CalDAV (UUID).
    """
    principal = client.principal()

    # Pattern UUID pour détecter les calendriers fantômes créés par CalDAV
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    )

    ui_match = None
    any_match = None
    for cal in principal.calendars():
        if cal.get_display_name() == calendar_name:
            any_match = cal
            if not uuid_pattern.search(str(cal.url)):
                ui_match = cal
                break

    if ui_match:
        return ui_match
    if any_match:
        return any_match

    log.info("Création du calendrier Synology : %s", calendar_name)
    try:
        return principal.make_calendar(name=calendar_name)
    except Exception as e:
        raise RuntimeError(
            f"Impossible de créer le calendrier '{calendar_name}' sur Synology. "
            f"Vérifie les permissions de l'utilisateur CalDAV. Erreur : {e}"
        ) from e
