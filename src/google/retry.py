"""Retry générique avec backoff exponentiel pour les appels Google API."""

import logging
import random
import time

from googleapiclient.errors import HttpError

from ..core.constants import MAX_RETRIES, RETRY_BASE_DELAY

log = logging.getLogger("google2radicale")

RETRYABLE_STATUS = (429, 500, 503)


def execute_with_retry(request):
    """
    Exécute une requête Google API (objet retourné par ...().list/insert/etc.)
    avec retry + backoff exponentiel sur 429/500/503.

    Toute autre HttpError (dont 410, 404) remonte à l'appelant, qui décide
    comment la traiter.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status not in RETRYABLE_STATUS or attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            log.warning(
                "Erreur Google API %d, retry dans %ds (tentative %d/%d)",
                e.resp.status, delay, attempt + 1, MAX_RETRIES,
            )
            time.sleep(delay)

    raise RuntimeError("Nombre max de retries atteint pour l'API Google")
