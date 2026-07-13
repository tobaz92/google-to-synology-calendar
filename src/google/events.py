"""Récupération des événements Google Calendar."""

import logging
import random
import time

from googleapiclient.errors import HttpError

from ..core.constants import MAX_RETRIES, RETRY_BASE_DELAY

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
        result = _execute_with_retry(service, params)

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
        # Sync initiale : on peut utiliser singleEvents
        params["singleEvents"] = True
        params["timeMin"] = "2020-01-01T00:00:00Z"

    return params


def _execute_with_retry(service, params: dict):
    """
    Exécute l'appel API avec retry + backoff exponentiel.

    Retourne None si le syncToken est invalide (410 Gone).
    """
    for attempt in range(MAX_RETRIES):
        try:
            return service.events().list(**params).execute()
        except HttpError as e:
            if e.resp.status == 410:
                return None
            if e.resp.status in (429, 500, 503) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                log.warning(
                    "Erreur Google API %d, retry dans %ds (tentative %d/%d)",
                    e.resp.status, delay, attempt + 1, MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            raise

    raise RuntimeError("Nombre max de retries atteint pour l'API Google")
