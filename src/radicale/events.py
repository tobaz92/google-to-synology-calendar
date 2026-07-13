"""Gestion des événements dans Radicale (CalDAV)."""

import logging

from caldav.lib.error import NotFoundError

from ..core.constants import GOOGLE_UID_SUFFIX
from .converter import google_event_to_ical

log = logging.getLogger("google2radicale")


def sync_event_to_caldav(caldav_calendar, event: dict) -> str:
    """
    Synchronise un événement Google vers CalDAV.
    Retourne "created", "updated" ou "deleted".
    """
    uid = event["id"] + GOOGLE_UID_SUFFIX

    if event.get("status") == "cancelled":
        _delete_event(caldav_calendar, uid)
        return "deleted"

    ical_data = google_event_to_ical(event)
    existing = _find_event_by_uid(caldav_calendar, uid)

    if existing:
        # Écrasement en place (PUT sur la même URL) : pas de fenêtre où
        # l'événement est supprimé sans avoir été recréé
        existing.data = ical_data
        existing.save()
        return "updated"

    caldav_calendar.save_event(ical_data)
    return "created"


def _delete_event(caldav_calendar, uid: str) -> None:
    """Supprime un événement du calendrier CalDAV par UID."""
    existing = _find_event_by_uid(caldav_calendar, uid)
    if existing:
        existing.delete()
        log.info("  Supprimé : %s", uid)
    else:
        log.debug("  Événement déjà absent : %s", uid)


def _find_event_by_uid(caldav_calendar, uid: str):
    """Cherche un événement par UID via la requête REPORT CalDAV.

    Seule l'absence est masquée : une erreur transitoire doit remonter,
    sinon elle serait traitée comme « n'existe pas » (doublon à la clé).
    """
    try:
        return caldav_calendar.event_by_uid(uid)
    except NotFoundError:
        return None
