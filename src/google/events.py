"""Récupération des événements Google Calendar."""

import logging

from googleapiclient.errors import HttpError

from .retry import execute_with_retry

log = logging.getLogger("google2radicale")


def fetch_events_incremental(service, calendar_id: str, sync_token: str = None):
    """
    Récupère les événements modifiés depuis le dernier syncToken.

    Retourne (events, new_sync_token).
    Si le syncToken est invalide (410), effectue un resync complet.
    """
    all_events = []
    page_token = None

    while True:
        params = _build_list_params(calendar_id, sync_token, page_token)
        result = _execute_list(service, params)

        if result is None:
            # syncToken invalide, resync complet
            log.warning("syncToken invalide pour %s, resync complet", calendar_id)
            return fetch_events_incremental(service, calendar_id, sync_token=None)

        all_events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")

        if not page_token:
            new_sync_token = result.get("nextSyncToken")
            return all_events, new_sync_token


def _build_list_params(calendar_id: str, sync_token: str, page_token: str) -> dict:
    """Construit les paramètres pour l'appel events().list()."""
    params = {
        "calendarId": calendar_id,
        "maxResults": 250,
    }

    if page_token:
        params["pageToken"] = page_token
    elif sync_token:
        # singleEvents est INCOMPATIBLE avec syncToken (API Google)
        params["syncToken"] = sync_token
    else:
        # Pas de singleEvents : on veut les événements maîtres avec RRULE,
        # pas les occurrences éclatées, pour rester cohérent avec le mode
        # syncToken (bidirectionnel).
        params["timeMin"] = "2020-01-01T00:00:00Z"

    return params


def _execute_list(service, params: dict):
    """
    Exécute events().list() avec retry.

    Retourne None si le syncToken est invalide (410 Gone) — spécifique au list.
    """
    try:
        return execute_with_retry(service.events().list(**params))
    except HttpError as e:
        if e.resp.status == 410:
            return None
        raise
