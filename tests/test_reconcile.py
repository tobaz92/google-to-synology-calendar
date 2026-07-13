"""Tests de la logique pure de réconciliation (plan_actions + comparaisons)."""

from src.core.constants import GOOGLE_UID_SUFFIX
from src.sync.ical_utils import ical_fingerprint
from src.sync.reconcile import plan_actions


def make_ical(uid, last_modified=None, dtstamp="20260101T000000Z", summary="Test"):
    """Construit un VEVENT iCal minimal, DTSTAMP/LAST-MODIFIED optionnels."""
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//",
        "BEGIN:VEVENT", f"UID:{uid}", f"SUMMARY:{summary}",
        "DTSTART:20260101T100000Z", "DTEND:20260101T110000Z",
    ]
    if dtstamp:
        lines.append(f"DTSTAMP:{dtstamp}")
    if last_modified:
        lines.append(f"LAST-MODIFIED:{last_modified}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def gevent(gid, updated, status=None):
    """Construit un event Google minimal."""
    event = {
        "id": gid, "updated": updated, "summary": "Test",
        "start": {"dateTime": "2026-01-01T10:00:00Z"},
        "end": {"dateTime": "2026-01-01T11:00:00Z"},
    }
    if status:
        event["status"] = status
    return event


def entry(google_id="g1", google_updated="old", caldav_fingerprint="h", href="/c/x.ics"):
    return {"google_id": google_id, "google_updated": google_updated,
            "caldav_fingerprint": caldav_fingerprint, "href": href}


def test_new_google_event_pushes_to_caldav():
    ev = gevent("g1", "2026-07-13T10:00:00Z")
    actions = plan_actions([ev], [], [], {})
    assert len(actions) == 1
    assert actions[0].kind == "push_to_caldav"
    assert actions[0].uid == "g1" + GOOGLE_UID_SUFFIX
    assert actions[0].google_event is ev


def test_new_caldav_event_pushes_to_google():
    ical = make_ical("native")
    actions = plan_actions([], [("native", "/c/n.ics", ical)], [], {})
    assert len(actions) == 1
    assert actions[0].kind == "push_to_google"
    assert actions[0].uid == "native"
    assert actions[0].google_id is None
    assert actions[0].href == "/c/n.ics"


def test_google_echo_yields_no_action():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(google_updated="2026-07-13T10:00:00Z")}
    ev = gevent("g1", "2026-07-13T10:00:00Z")
    assert plan_actions([ev], [], [], table) == []


def test_caldav_echo_yields_record_href_only():
    uid = "native"
    ical = make_ical(uid)
    table = {uid: entry(caldav_fingerprint=ical_fingerprint(ical), href=None)}
    actions = plan_actions([], [(uid, "/c/n.ics", ical)], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "record_href"
    assert actions[0].href == "/c/n.ics"


def test_caldav_echo_survives_server_reformatting():
    """Radicale renvoie LF + DTSTAMP ajouté : l'écho doit quand même matcher."""
    uid = "native"
    written = make_ical(uid, dtstamp=None)
    reformatted = make_ical(uid, dtstamp="20260601T120000Z").replace("\r\n", "\n")
    table = {uid: entry(caldav_fingerprint=ical_fingerprint(written), href="/c/n.ics")}
    assert plan_actions([], [(uid, "/c/n.ics", reformatted)], [], table) == []


def test_conflict_google_newer_pushes_to_caldav():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(google_updated="2026-07-01T00:00:00Z")}
    ev = gevent("g1", "2026-07-13T12:00:00Z")
    ical = make_ical(uid, last_modified="20260710T000000Z")
    actions = plan_actions([ev], [(uid, "/c/x.ics", ical)], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "push_to_caldav"


def test_conflict_caldav_newer_pushes_to_google():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(google_updated="2026-07-01T00:00:00Z")}
    ev = gevent("g1", "2026-07-05T00:00:00Z")
    ical = make_ical(uid, last_modified="20260710T000000Z")
    actions = plan_actions([ev], [(uid, "/c/x.ics", ical)], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "push_to_google"
    assert actions[0].google_id == "g1"


def test_conflict_without_caldav_timestamp_google_wins():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(google_updated="2026-07-01T00:00:00Z")}
    ev = gevent("g1", "2026-07-05T00:00:00Z")
    ical = make_ical(uid, dtstamp=None)
    actions = plan_actions([ev], [(uid, "/c/x.ics", ical)], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "push_to_caldav"


def test_google_deletion_deletes_in_caldav():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry()}
    ev = gevent("g1", "2026-07-13T00:00:00Z", status="cancelled")
    actions = plan_actions([ev], [], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "delete_in_caldav"
    assert actions[0].uid == uid


def test_google_deletion_unknown_uid_ignored():
    ev = gevent("ghost", "2026-07-13T00:00:00Z", status="cancelled")
    assert plan_actions([ev], [], [], {}) == []


def test_caldav_deletion_deletes_in_google():
    uid = "native"
    table = {uid: entry(href="/c/n.ics")}
    actions = plan_actions([], [], ["/c/n.ics"], table)
    assert len(actions) == 1
    assert actions[0].kind == "delete_in_google"
    assert actions[0].google_id == "g1"


def test_google_delete_vs_caldav_modify_modification_wins():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(href="/c/x.ics")}
    ev = gevent("g1", "2026-07-13T00:00:00Z", status="cancelled")
    ical = make_ical(uid)
    actions = plan_actions([ev], [(uid, "/c/x.ics", ical)], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "push_to_google"
    # L'id Google est mort (supprimé côté Google) : recréation via insert
    assert actions[0].google_id is None


def test_caldav_delete_vs_google_modify_modification_wins():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(href="/c/x.ics")}
    ev = gevent("g1", "2026-07-13T00:00:00Z")
    actions = plan_actions([ev], [], ["/c/x.ics"], table)
    assert len(actions) == 1
    assert actions[0].kind == "push_to_caldav"


def test_deletion_both_sides_forgets():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(href="/c/x.ics")}
    ev = gevent("g1", "2026-07-13T00:00:00Z", status="cancelled")
    actions = plan_actions([ev], [], ["/c/x.ics"], table)
    assert len(actions) == 1
    assert actions[0].kind == "forget"


def test_initial_adoption_single_action_no_duplicate():
    uid = "g1" + GOOGLE_UID_SUFFIX
    ev = gevent("g1", "2026-07-13T12:00:00Z")
    ical = make_ical(uid, last_modified="20260710T000000Z")
    actions = plan_actions([ev], [(uid, "/c/x.ics", ical)], [], {})
    assert len(actions) == 1
    assert actions[0].kind == "push_to_caldav"


def test_unknown_deleted_href_yields_no_action():
    assert plan_actions([], [], ["/c/ghost.ics"], {}) == []


def test_caldav_echo_with_known_href_yields_nothing():
    uid = "native"
    ical = make_ical(uid)
    table = {uid: entry(caldav_fingerprint=ical_fingerprint(ical), href="/c/n.ics")}
    assert plan_actions([], [(uid, "/c/n.ics", ical)], [], table) == []


def test_orphan_google_suffixed_caldav_event_ignored():
    """Copie d'origine Google sans contrepartie ni entrée : jamais repoussée."""
    uid = "dead-master_20200101T100000Z" + GOOGLE_UID_SUFFIX
    ical = make_ical(uid)
    assert plan_actions([], [(uid, "/c/o.ics", ical)], [], {}) == []


def test_google_uid_resolved_via_g2r_marker():
    """État perdu : le marqueur extendedProperties relie l'event à son uid natif."""
    ev = gevent("gX", "2026-07-13T10:00:00Z")
    ev["extendedProperties"] = {"private": {"g2r_uid": "native"}}
    ical = make_ical("native", last_modified="20260701T000000Z")
    actions = plan_actions([ev], [("native", "/c/n.ics", ical)], [], {})
    assert len(actions) == 1
    assert actions[0].uid == "native"
    assert actions[0].kind == "push_to_caldav"


def test_conflict_equal_timestamps_google_wins():
    uid = "g1" + GOOGLE_UID_SUFFIX
    table = {uid: entry(google_updated="2026-07-01T00:00:00Z")}
    ev = gevent("g1", "2026-07-10T00:00:00Z")
    ical = make_ical(uid, last_modified="20260710T000000Z")
    actions = plan_actions([ev], [(uid, "/c/x.ics", ical)], [], table)
    assert len(actions) == 1
    assert actions[0].kind == "push_to_caldav"
