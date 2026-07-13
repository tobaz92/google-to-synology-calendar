"""Utilitaires iCalendar partagés par le moteur de sync (parse, empreinte)."""

import hashlib
import json
from datetime import datetime, timezone

from icalendar import Calendar

TEXT_PROPS = ("summary", "description", "location", "status")
RECURRENCE_PROPS = ("rrule", "rdate", "exdate", "exrule")


def parse_vevent(ical_data: str):
    """Retourne le premier VEVENT sans RECURRENCE-ID, ou None."""
    cal = Calendar.from_ical(ical_data)
    for comp in cal.walk("VEVENT"):
        if comp.get("recurrence-id") is None:
            return comp
    return None


def ical_fingerprint(ical_data: str) -> str | None:
    """Empreinte sémantique des propriétés synchronisées d'un VEVENT.

    Un hash brut du payload ne survit pas au serveur : Radicale renvoie le
    contenu normalisé (LF, DTSTAMP ajouté, ordre des propriétés). On hashe
    donc uniquement les champs que la sync transporte : deux payloads
    équivalents pour la sync ont la même empreinte, quel que soit le
    formatage. None si aucun VEVENT exploitable.
    """
    vevent = parse_vevent(ical_data)
    if vevent is None:
        return None

    fields = {name: str(vevent.get(name) or "") for name in TEXT_PROPS}
    for name in ("dtstart", "dtend"):
        prop = vevent.get(name)
        fields[name] = prop.dt.isoformat() if prop is not None else ""
    for name in RECURRENCE_PROPS:
        fields[name] = _recurrence_key(vevent.get(name))

    payload = json.dumps(fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _recurrence_key(value) -> str:
    """Forme canonique triée d'une propriété de récurrence (ou '')."""
    if value is None:
        return ""
    props = value if isinstance(value, list) else [value]
    return "|".join(sorted(p.to_ical().decode() for p in props))


def caldav_timestamp(ical_data: str):
    """LAST-MODIFIED du VEVENT, à défaut DTSTAMP, sinon None. Aware UTC."""
    vevent = parse_vevent(ical_data)
    if vevent is None:
        return None
    for key in ("last-modified", "dtstamp"):
        prop = vevent.get(key)
        if prop is not None:
            return to_utc(prop.dt)
    return None


def to_utc(dt: datetime) -> datetime:
    """Force un datetime en aware UTC (naïf supposé UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_rfc3339(value: str) -> datetime:
    """Parse un timestamp RFC3339 Google en aware UTC."""
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
