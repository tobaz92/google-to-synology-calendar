"""Client CalDAV pour Radicale."""

import logging
import os

import caldav

log = logging.getLogger("google2radicale")

CALDAV_TIMEOUT = 30  # secondes

# Cache nom → URL de collection : évite la découverte principal/calendriers
# à chaque cycle et fige le choix quand plusieurs collections sont homonymes
_calendar_url_cache: dict[str, str] = {}


def get_caldav_client(config: dict) -> caldav.DAVClient:
    """Crée un client CalDAV connecté au serveur Radicale."""
    rad = config["radicale"]

    verify_ssl = rad.get("verify_ssl", True)
    if not verify_ssl:
        _suppress_ssl_warnings()
        log.warning("Vérification SSL désactivée — risque MITM")
    return caldav.DAVClient(
        url=rad["url"],
        username=rad["username"],
        password=os.environ.get("RADICALE_PASSWORD") or rad.get("password", ""),
        ssl_verify_cert=verify_ssl,
        timeout=rad.get("timeout", CALDAV_TIMEOUT),
    )


def get_or_create_calendar(client: caldav.DAVClient, calendar_name: str):
    """Retourne le calendrier depuis le cache d'URL, le résout ou le crée sinon."""
    cached_url = _calendar_url_cache.get(calendar_name)
    if cached_url:
        return client.calendar(url=cached_url)

    calendar = _resolve_or_create(client, calendar_name)
    _calendar_url_cache[calendar_name] = str(calendar.url)
    return calendar


def invalidate_calendar(calendar_name: str) -> None:
    """Oublie l'URL cachée — force une re-résolution au prochain cycle."""
    _calendar_url_cache.pop(calendar_name, None)


def _resolve_or_create(client: caldav.DAVClient, calendar_name: str):
    """Résout un calendrier par nom d'affichage, le crée s'il n'existe pas."""
    principal = client.principal()
    matches = [
        cal for cal in principal.calendars()
        if cal.get_display_name() == calendar_name
    ]

    if len(matches) > 1:
        # Tri par URL : choix déterministe entre collections homonymes,
        # stable d'un redémarrage à l'autre
        matches.sort(key=lambda cal: str(cal.url))
        log.warning(
            "%d calendriers nommés '%s' sur Radicale — utilisation de %s. "
            "Supprime les doublons pour lever l'ambiguïté.",
            len(matches), calendar_name, matches[0].url,
        )
    if matches:
        return matches[0]

    log.info("Création du calendrier Radicale : %s", calendar_name)
    try:
        return principal.make_calendar(name=calendar_name)
    except Exception as e:
        raise RuntimeError(
            f"Impossible de créer le calendrier '{calendar_name}' sur Radicale. "
            f"Vérifie les droits de l'utilisateur CalDAV. Erreur : {e}"
        ) from e


_ssl_warnings_suppressed = False


def _suppress_ssl_warnings():
    """Supprime les warnings SSL urllib3 une seule fois."""
    global _ssl_warnings_suppressed
    if _ssl_warnings_suppressed:
        return
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _ssl_warnings_suppressed = True
