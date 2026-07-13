"""Moteur de réconciliation — logique PURE, sans I/O.

Décide, pour un cycle, la liste d'actions à appliquer de part et d'autre
(Google ↔ Radicale) à partir des changements observés des deux côtés et de
la table d'état. Aucune dépendance aux API caldav/google : entièrement
testable avec des dicts et des chaînes iCal.
"""

import logging
from dataclasses import dataclass

from ..core.constants import G2R_UID_PROP, GOOGLE_UID_SUFFIX
from .ical_utils import caldav_timestamp, ical_fingerprint, parse_rfc3339

log = logging.getLogger("google2radicale")


@dataclass
class Action:
    """Action unitaire à appliquer par le moteur d'orchestration."""

    kind: str
    uid: str
    google_event: dict | None = None
    ical_data: str | None = None
    google_id: str | None = None
    href: str | None = None


@dataclass
class _Cycle:
    """Vue classée d'un cycle : ce qui a changé de chaque côté."""

    g_active: dict
    g_cancelled: dict
    c_active: dict
    c_deleted: set
    table: dict


def plan_actions(google_events, caldav_changes, deleted_hrefs, events_table) -> list:
    """Calcule les actions du cycle. Voir docstring module pour les règles.

    - ``caldav_changes`` : list de tuples ``(uid, href, ical_data)``.
    - ``events_table`` : table d'état en lecture seule ici.
    """
    index = {e["google_id"]: uid for uid, e in events_table.items() if e.get("google_id")}
    g_active, g_cancelled = _split_google(google_events, index, events_table)
    c_active, echo_actions = _split_caldav(caldav_changes, events_table)
    c_deleted = _resolve_deleted(deleted_hrefs, events_table)

    cycle = _Cycle(g_active, g_cancelled, c_active, c_deleted, events_table)
    actions = list(echo_actions)
    for uid in set(g_active) | set(g_cancelled) | set(c_active) | c_deleted:
        action = _decide(uid, cycle)
        if action is not None:
            actions.append(action)
    return actions


def _split_google(google_events, index, table) -> tuple:
    """Classe les events Google en actifs / annulés, en filtrant nos échos."""
    active, cancelled = {}, {}
    for event in google_events:
        uid = _google_uid(event, index)
        if event.get("status") == "cancelled":
            cancelled[uid] = event
        elif _is_google_echo(uid, event, table):
            continue
        else:
            active[uid] = event
    return active, cancelled


def _google_uid(event: dict, index: dict) -> str:
    """Uid CalDAV d'un event Google : table, sinon marqueur g2r_uid, sinon suffixe.

    Le marqueur (posé à chaque écriture vers Google) permet de retrouver la
    correspondance après perte de l'état local, sans dupliquer l'événement.
    """
    marker = event.get("extendedProperties", {}).get("private", {}).get(G2R_UID_PROP)
    return index.get(event["id"]) or marker or (event["id"] + GOOGLE_UID_SUFFIX)


def _is_google_echo(uid, event, table) -> bool:
    """Vrai si l'event Google est le retour de notre propre écriture."""
    entry = table.get(uid)
    return entry is not None and event.get("updated") == entry.get("google_updated")


def _split_caldav(caldav_changes, table) -> tuple:
    """Classe les changements CalDAV, en isolant nos échos (→ record_href)."""
    active, echoes = {}, []
    for uid, href, ical_data in caldav_changes:
        entry = table.get(uid)
        if entry is not None and ical_fingerprint(ical_data) == entry.get("caldav_fingerprint"):
            if entry.get("href") != href:
                echoes.append(Action("record_href", uid, href=href))
            continue
        active[uid] = (href, ical_data)
    return active, echoes


def _resolve_deleted(deleted_hrefs, table) -> set:
    """Retrouve les uid des ressources CalDAV supprimées via leur href."""
    href_to_uid = {e["href"]: uid for uid, e in table.items() if e.get("href")}
    resolved = set()
    for href in deleted_hrefs:
        uid = href_to_uid.get(href)
        if uid is None:
            log.debug("href supprimé inconnu, ignoré : %s", href)
            continue
        resolved.add(uid)
    return resolved


def _decide(uid, cycle: _Cycle) -> Action | None:
    """Applique la matrice de décision pour un uid donné."""
    g = "mod" if uid in cycle.g_active else "del" if uid in cycle.g_cancelled else None
    c = "mod" if uid in cycle.c_active else "del" if uid in cycle.c_deleted else None

    if g == "mod" and c == "mod":
        return _resolve_conflict(uid, cycle)
    if g == "mod":
        return _push_caldav(uid, cycle)  # c == "del" ou None : la modif gagne
    if g == "del" and c == "mod":
        return _push_google(uid, cycle, recreate=True)
    if g == "del" and c == "del":
        return Action("forget", uid)
    if g == "del":
        return Action("delete_in_caldav", uid) if uid in cycle.table else None
    if c == "mod":
        return _adopt_or_push_google(uid, cycle)
    if c == "del":
        return _delete_google(uid, cycle)
    return None


def _adopt_or_push_google(uid, cycle: _Cycle) -> Action | None:
    """Changement CalDAV seul : push vers Google, sauf orphelin d'origine Google.

    Un uid suffixé absent de la table sans contrepartie Google est une copie
    laissée par une sync antérieure (état perdu, instance éclatée de la
    phase 1) : le pousser créerait un doublon dans Google. On l'ignore.
    """
    if uid not in cycle.table and uid.endswith(GOOGLE_UID_SUFFIX):
        log.warning("Copie orpheline d'origine Google ignorée : %s", uid)
        return None
    return _push_google(uid, cycle)


def _resolve_conflict(uid, cycle: _Cycle) -> Action:
    """Modif des deux côtés : le timestamp le plus récent gagne."""
    event = cycle.g_active[uid]
    _, ical_data = cycle.c_active[uid]
    if _google_wins(event, ical_data):
        return _push_caldav(uid, cycle)
    return _push_google(uid, cycle)


def _push_caldav(uid, cycle: _Cycle) -> Action:
    return Action("push_to_caldav", uid, google_event=cycle.g_active[uid])


def _push_google(uid, cycle: _Cycle, recreate: bool = False) -> Action:
    entry = cycle.table.get(uid)
    href, ical_data = cycle.c_active[uid]
    google_id = None if recreate else (entry.get("google_id") if entry else None)
    return Action("push_to_google", uid, ical_data=ical_data, google_id=google_id, href=href)


def _delete_google(uid, cycle: _Cycle) -> Action:
    entry = cycle.table[uid]  # c == "del" implique une entrée résolue via href
    return Action("delete_in_google", uid, google_id=entry.get("google_id"))


def _google_wins(event: dict, ical_data: str) -> bool:
    """Compare updated (Google) et LAST-MODIFIED (CalDAV). Égalité → Google."""
    caldav_ts = caldav_timestamp(ical_data)
    if caldav_ts is None:
        return True
    return parse_rfc3339(event["updated"]) >= caldav_ts
