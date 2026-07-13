"""Application des actions de réconciliation — couche I/O.

Chaque handler exécute les appels API nécessaires puis mute la table d'état
(``events_table``) sur succès. Les erreurs remontent : c'est l'orchestrateur
(``engine``) qui les classe en ``skipped`` (permanent) ou ``errors``.
"""

import logging
from dataclasses import dataclass

from googleapiclient.errors import HttpError

from ..core.constants import G2R_UID_PROP
from ..google import delete_event, ical_to_google_event, insert_event, update_event
from ..radicale import delete_event_by_uid, upsert_event
from ..radicale.converter import google_event_to_ical
from .ical_utils import ical_fingerprint, parse_vevent

log = logging.getLogger("google2radicale")


@dataclass
class ApplyContext:
    """Dépendances I/O partagées par les handlers d'un mapping."""

    service: object
    caldav_calendar: object
    gcal_id: str
    events_table: dict


def apply_action(action, ctx: ApplyContext) -> str | None:
    """Applique une action. Retourne la clé de stat impactée, ou None."""
    return _HANDLERS[action.kind](action, ctx)


def _push_to_caldav(action, ctx: ApplyContext) -> str:
    event = action.google_event
    ical = google_event_to_ical(event, uid=action.uid)
    _, href = upsert_event(ctx.caldav_calendar, action.uid, ical)
    ctx.events_table[action.uid] = {
        "google_id": event["id"],
        "google_updated": event["updated"],
        "caldav_fingerprint": ical_fingerprint(ical),
        "href": href,
    }
    return "to_caldav"


def _push_to_google(action, ctx: ApplyContext) -> str:
    vevent = parse_vevent(action.ical_data)
    if vevent is None:
        raise ValueError("aucun VEVENT exploitable dans le payload CalDAV")
    body = ical_to_google_event(vevent)
    # Marqueur de correspondance posé à CHAQUE écriture (update = full
    # replace côté API : sans ça, la première mise à jour l'effacerait)
    body["extendedProperties"] = {"private": {G2R_UID_PROP: action.uid}}
    resource = _write_google(ctx, action.google_id, body)
    ctx.events_table[action.uid] = {
        "google_id": resource["id"],
        "google_updated": resource["updated"],
        "caldav_fingerprint": ical_fingerprint(action.ical_data),
        "href": action.href,
    }
    return "to_google"


def _write_google(ctx: ApplyContext, google_id, body: dict) -> dict:
    """Update si un id Google est connu, sinon insert.

    Un 404/410 sur l'update signifie que l'id est mort côté Google
    (supprimé pendant que l'état le croyait vivant) : on recrée.
    """
    if google_id:
        try:
            return update_event(ctx.service, ctx.gcal_id, google_id, body)
        except HttpError as e:
            if e.resp.status not in (404, 410):
                raise
            log.info("Id Google %s mort, recréation", google_id)
    return insert_event(ctx.service, ctx.gcal_id, body)


def _delete_in_caldav(action, ctx: ApplyContext) -> str:
    delete_event_by_uid(ctx.caldav_calendar, action.uid)
    ctx.events_table.pop(action.uid, None)
    return "deleted_caldav"


def _delete_in_google(action, ctx: ApplyContext) -> str:
    if action.google_id:
        delete_event(ctx.service, ctx.gcal_id, action.google_id)
    ctx.events_table.pop(action.uid, None)
    return "deleted_google"


def _forget(action, ctx: ApplyContext) -> None:
    ctx.events_table.pop(action.uid, None)
    return None


def _record_href(action, ctx: ApplyContext) -> None:
    entry = ctx.events_table.get(action.uid)
    if entry is not None:
        entry["href"] = action.href
    return None


_HANDLERS = {
    "push_to_caldav": _push_to_caldav,
    "push_to_google": _push_to_google,
    "delete_in_caldav": _delete_in_caldav,
    "delete_in_google": _delete_in_google,
    "forget": _forget,
    "record_href": _record_href,
}
