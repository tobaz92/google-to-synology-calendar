"""Client CalDAV pour Radicale."""

import logging
import os

import caldav

log = logging.getLogger("google2radicale")

CALDAV_TIMEOUT = 30  # secondes


def get_caldav_client(config: dict) -> caldav.DAVClient:
    """Crée un client CalDAV connecté au serveur Radicale."""
    rad = config["radicale"]
    password = os.environ.get("RADICALE_PASSWORD", rad.get("password", ""))

    if not password:
        raise ValueError(
            "Mot de passe Radicale manquant. "
            "Définis RADICALE_PASSWORD en variable d'environnement "
            "ou radicale.password dans config.yaml."
        )

    verify_ssl = rad.get("verify_ssl", True)
    if not verify_ssl:
        _suppress_ssl_warnings()
        log.warning("Vérification SSL désactivée — risque MITM")
    return caldav.DAVClient(
        url=rad["url"],
        username=rad["username"],
        password=password,
        ssl_verify_cert=verify_ssl,
        timeout=rad.get("timeout", CALDAV_TIMEOUT),
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
    """Récupère un calendrier Radicale par nom d'affichage, le crée sinon."""
    principal = client.principal()

    for cal in principal.calendars():
        if cal.get_display_name() == calendar_name:
            return cal

    log.info("Création du calendrier Radicale : %s", calendar_name)
    try:
        return principal.make_calendar(name=calendar_name)
    except Exception as e:
        raise RuntimeError(
            f"Impossible de créer le calendrier '{calendar_name}' sur Radicale. "
            f"Vérifie les droits de l'utilisateur CalDAV. Erreur : {e}"
        ) from e
