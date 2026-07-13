"""Écriture d'événements vers l'API Google Calendar (insert/update/delete)."""

import logging

from googleapiclient.errors import HttpError

from .retry import execute_with_retry

log = logging.getLogger("google2radicale")


def insert_event(service, calendar_id: str, body: dict) -> dict:
    """Insère un événement. Retourne la ressource créée (contient id et updated)."""
    request = service.events().insert(calendarId=calendar_id, body=body)
    return execute_with_retry(request)


def update_event(service, calendar_id: str, google_id: str, body: dict) -> dict:
    """Met à jour un événement existant. Retourne la ressource mise à jour."""
    request = service.events().update(
        calendarId=calendar_id, eventId=google_id, body=body
    )
    return execute_with_retry(request)


def delete_event(service, calendar_id: str, google_id: str) -> None:
    """Supprime un événement. Tolère 404/410 (déjà supprimé côté Google)."""
    request = service.events().delete(calendarId=calendar_id, eventId=google_id)
    try:
        execute_with_retry(request)
    except HttpError as e:
        if e.resp.status in (404, 410):
            log.debug("Événement %s déjà supprimé (%d)", google_id, e.resp.status)
            return
        raise
