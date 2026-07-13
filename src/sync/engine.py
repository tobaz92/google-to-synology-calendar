"""Orchestration I/O d'un cycle de sync pour un mapping Google ↔ Radicale."""

import logging
from dataclasses import dataclass

from googleapiclient.errors import HttpError

from ..google import fetch_events_incremental
from ..radicale import event_href, event_uid, fetch_changes, invalidate_calendar
from .apply import ApplyContext, apply_action
from .ical_utils import parse_vevent
from .reconcile import plan_actions

log = logging.getLogger("google2radicale")

# 4xx déterministes : re-tenter à l'identique échouera pareil. On les compte
# « skipped » pour ne pas geler les tokens (pilule empoisonnée), contrairement
# aux erreurs transitoires (réseau, 5xx, 401/403) qui déclenchent un replay.
PERMANENT_HTTP_STATUS = (400, 404, 409, 410, 412, 422)


@dataclass
class CalendarContext:
    """Calendrier CalDAV résolu + son nom (nécessaire à l'invalidation)."""

    calendar: object
    name: str


def sync_mapping(service, calendar_ctx: CalendarContext, gcal_id: str, mapping_state: dict) -> dict:
    """Synchronise un mapping. Mute ``mapping_state`` (tokens + table). Retourne les stats."""
    google_events, new_g_token = fetch_events_incremental(
        service, gcal_id, mapping_state["google_sync_token"]
    )
    changed, deleted_hrefs, new_c_token = fetch_changes(
        calendar_ctx.calendar, mapping_state["caldav_sync_token"]
    )
    caldav_changes, pre_skipped = _extract_changes(changed)

    actions = plan_actions(google_events, caldav_changes, deleted_hrefs, mapping_state["events"])
    ctx = ApplyContext(service, calendar_ctx.calendar, gcal_id, mapping_state["events"])
    stats = _apply_all(actions, ctx)
    stats["skipped"] += pre_skipped

    _advance_tokens(mapping_state, calendar_ctx, new_g_token, new_c_token, stats["errors"])
    return stats


def _extract_changes(changed_events) -> tuple[list, int]:
    """Transforme les objets caldav en tuples (uid, href, ical_data).

    Les payloads sans UID ou inexploitables par icalendar sont écartés ICI,
    avant le planning : sinon un seul VEVENT malformé ferait échouer tout le
    mapping (parse dans la résolution de conflit) et gèlerait ses tokens.
    """
    tuples, skipped = [], 0
    for obj in changed_events:
        uid = event_uid(obj)
        if uid is None:
            log.warning("Événement CalDAV sans UID, ignoré : %s", event_href(obj))
            skipped += 1
            continue
        try:
            valid = parse_vevent(obj.data) is not None
        except Exception as e:
            log.warning("Payload CalDAV inexploitable (%s), ignoré : %s", e, event_href(obj))
            valid = False
        if not valid:
            skipped += 1
            continue
        tuples.append((uid, event_href(obj), obj.data))
    return tuples, skipped


def _apply_all(actions, ctx: ApplyContext) -> dict:
    """Applique chaque action avec le modèle d'erreurs hérité de la phase 1."""
    stats = {
        "to_caldav": 0, "to_google": 0, "deleted_caldav": 0,
        "deleted_google": 0, "skipped": 0, "errors": 0,
    }
    for action in actions:
        _apply_one(action, ctx, stats)
    return stats


def _apply_one(action, ctx: ApplyContext, stats: dict) -> None:
    """Applique une action et impute le résultat dans les stats."""
    try:
        key = apply_action(action, ctx)
    except ValueError as e:
        stats["skipped"] += 1
        log.warning("Ignoré (%s '%s') : %s", action.kind, action.uid, e)
    except HttpError as e:
        _count_http_error(action, e, stats)
    except Exception as e:
        stats["errors"] += 1
        log.error("Erreur (%s '%s') : %s", action.kind, action.uid, e)
    else:
        if key is not None:
            stats[key] += 1


def _count_http_error(action, e: HttpError, stats: dict) -> None:
    """Sépare les rejets Google permanents (skipped) des transitoires (errors)."""
    if e.resp.status in PERMANENT_HTTP_STATUS:
        stats["skipped"] += 1
        log.error(
            "Rejet permanent Google (%s '%s', HTTP %d) — non re-tenté : %s",
            action.kind, action.uid, e.resp.status, e,
        )
    else:
        stats["errors"] += 1
        log.error("Erreur Google (%s '%s') : %s", action.kind, action.uid, e)


def _advance_tokens(mapping_state, calendar_ctx, new_g_token, new_c_token, errors: int) -> None:
    """Avance les tokens seulement si aucune erreur transitoire ; sinon replay."""
    if errors:
        invalidate_calendar(calendar_ctx.name)
        log.warning(
            "  syncTokens non avancés (%s) — nouvelle tentative au prochain cycle",
            calendar_ctx.name,
        )
        return
    if new_g_token:
        mapping_state["google_sync_token"] = new_g_token
    if new_c_token:
        mapping_state["caldav_sync_token"] = new_c_token
