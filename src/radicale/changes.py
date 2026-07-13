"""Détection des changements côté Radicale via sync-collection (RFC 6578).

La lib `caldav` expose `Calendar.get_objects_by_sync_token`, qui fait un
REPORT sync-collection. Points clés du comportement observé dans la lib
(collection.py, méthode `SynchronizableCalendarObjectCollection.sync`) :

- Le REPORT ne rapatrie PAS le CalendarData (`no_calendardata=True`). Les
  objets renvoyés sont donc « vides » : il faut appeler `obj.load()` pour
  obtenir leur `.data`.
- Les suppressions apparaissent comme des objets dans la même liste : leur
  `load()` échoue en `NotFoundError` (le serveur renvoie un statut 404 pour
  la ressource dans le multistatus). On distingue donc créé/modifié vs
  supprimé en tentant le `load()`.
- Si le serveur ne supporte pas les sync-tokens, ou si le token est jugé
  invalide/expiré, la lib retombe silencieusement sur une récupération
  complète et renvoie un token « fake-… ». On traite ce cas comme une
  resync initiale (cf. le 410 côté Google).
"""

import logging

from caldav.lib.error import NotFoundError

log = logging.getLogger("google2radicale")

_FALLBACK_TOKEN_PREFIX = "fake-"


def fetch_changes(caldav_calendar, sync_token: str | None) -> tuple[list, list[str], str]:
    """Retourne (changed_events, deleted_hrefs, new_sync_token).

    - `changed_events` : objets caldav chargés (`.data` peuplé) créés ou
      modifiés depuis `sync_token`. Chacun expose `.data`, `.url`, et son
      UID via `event_uid` / son href via `event_href`.
    - `deleted_hrefs` : href canoniques des ressources supprimées.
    - `new_sync_token` : token à persister pour le prochain cycle.

    `sync_token=None` déclenche une sync initiale : tout le calendrier est
    renvoyé comme « changed », `deleted_hrefs` vide.
    """
    if sync_token is None:
        return _initial_sync(caldav_calendar)

    collection = caldav_calendar.get_objects_by_sync_token(
        sync_token=sync_token, load_objects=False
    )
    new_token = collection.sync_token

    if _is_fallback_token(new_token):
        log.warning(
            "Sync token Radicale rejeté ou non supporté — resync complète du calendrier"
        )
        return _initial_sync(caldav_calendar)

    changed, deleted = _classify(collection)
    return changed, deleted, new_token


def event_uid(event) -> str | None:
    """Extrait l'UID du VEVENT d'un objet caldav, sans déclencher de load."""
    return event.id


def event_href(event) -> str:
    """Href canonique d'une ressource caldav (sans credentials, normalisé).

    Sert de clé stable pour associer un événement Radicale à son pendant
    Google. Doit être identique pour un « changed » et sa suppression
    ultérieure, d'où la canonicalisation.
    """
    return str(event.url.canonical())


def _initial_sync(caldav_calendar) -> tuple[list, list[str], str]:
    """Charge tout le calendrier ; aucun objet n'est une suppression."""
    collection = caldav_calendar.get_objects_by_sync_token(
        sync_token=None, load_objects=True
    )
    return list(collection.objects), [], collection.sync_token


def _classify(collection) -> tuple[list, list[str]]:
    """Sépare créés/modifiés (load OK) des supprimés (load NotFoundError).

    Reproduit la logique de `SynchronizableCalendarObjectCollection.sync` :
    seule l'absence est masquée, toute autre erreur de load remonte.
    """
    changed = []
    deleted = []
    for obj in collection.objects:
        try:
            obj.load()
        except NotFoundError:
            deleted.append(event_href(obj))
        else:
            changed.append(obj)
    return changed, deleted


def _is_fallback_token(token) -> bool:
    """Vrai si la lib a basculé en mode dégradé (token « fake-… »)."""
    return isinstance(token, str) and token.startswith(_FALLBACK_TOKEN_PREFIX)
