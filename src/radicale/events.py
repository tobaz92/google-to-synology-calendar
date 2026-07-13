"""Gestion des événements dans Radicale (CalDAV)."""

import logging

from caldav.lib.error import NotFoundError

from .changes import event_href

log = logging.getLogger("google2radicale")


def upsert_event(caldav_calendar, uid: str, ical_data: str) -> tuple[str, str]:
    """Crée ou écrase un événement par UID. Retourne ("created"|"updated", href).

    Un événement existant est écrasé EN PLACE (un seul PUT sur la même URL) :
    jamais de delete+recreate, pour ne pas ouvrir de fenêtre où l'événement
    a disparu sans avoir été recréé. Le href canonique retourné permet de
    mapper les futures suppressions (le REPORT sync-collection ne renvoie
    que des href).
    """
    existing = _find_event_by_uid(caldav_calendar, uid)
    if existing:
        existing.data = ical_data
        existing.save()
        return "updated", event_href(existing)

    created = caldav_calendar.save_event(ical_data)
    return "created", event_href(created)


def delete_event_by_uid(caldav_calendar, uid: str) -> bool:
    """Supprime un événement par UID. Retourne True si supprimé, False si absent."""
    existing = _find_event_by_uid(caldav_calendar, uid)
    if not existing:
        log.debug("  Événement déjà absent : %s", uid)
        return False

    existing.delete()
    log.info("  Supprimé : %s", uid)
    return True


def _find_event_by_uid(caldav_calendar, uid: str):
    """Cherche un événement par UID via la requête REPORT CalDAV.

    Seule l'absence est masquée : une erreur transitoire doit remonter,
    sinon elle serait traitée comme « n'existe pas » (doublon à la clé).
    """
    try:
        return caldav_calendar.event_by_uid(uid)
    except NotFoundError:
        return None
