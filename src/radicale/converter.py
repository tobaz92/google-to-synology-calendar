"""Conversion des événements Google Calendar → iCalendar."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from ..core.constants import GOOGLE_UID_SUFFIX, PRODID

STATUS_MAP = {
    "confirmed": "CONFIRMED",
    "tentative": "TENTATIVE",
    "cancelled": "CANCELLED",
}


def google_event_to_ical(event: dict, uid: str | None = None) -> str:
    """Convertit un événement Google Calendar en string iCalendar.

    ``uid`` force l'UID du VEVENT : indispensable quand la cible est un
    événement d'origine Radicale (UID natif ≠ id Google + suffixe), sinon
    l'écrasement en place changerait l'identité de la ressource.
    """
    if event.get("recurringEventId"):
        raise ValueError("exception d'occurrence non gérée")

    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")

    vevent = _build_vevent(event, uid or event["id"] + GOOGLE_UID_SUFFIX)
    cal.add_component(vevent)

    return cal.to_ical().decode("utf-8")


def _build_vevent(event: dict, uid: str) -> Event:
    """Construit un composant VEVENT à partir d'un événement Google."""
    vevent = Event()

    vevent.add("uid", uid)
    vevent.add("summary", event.get("summary", "(sans titre)"))

    if event.get("description"):
        vevent.add("description", event["description"])
    if event.get("location"):
        vevent.add("location", event["location"])

    _add_dates(vevent, event)
    _add_timestamps(vevent, event)
    _add_status(vevent, event)
    _add_recurrence(vevent, event)

    return vevent


def _add_recurrence(vevent: Event, event: dict) -> None:
    """Recopie les lignes de récurrence Google (RRULE/RDATE/EXDATE/EXRULE)."""
    lines = event.get("recurrence")
    if not lines:
        return

    raw = "BEGIN:VEVENT\r\n" + "\r\n".join(lines) + "\r\nEND:VEVENT"
    parsed = Event.from_ical(raw)
    for name in ("rrule", "rdate", "exdate", "exrule"):
        value = parsed.get(name)
        if value is None:
            continue
        props = value if isinstance(value, list) else [value]
        for prop in props:
            vevent.add(name, prop)


def _add_dates(vevent: Event, event: dict) -> None:
    """Ajoute les dates de début/fin. Lève ValueError si absentes."""
    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start:
        tz_name = start.get("timeZone") or end.get("timeZone")
        vevent.add("dtstart", _parse_datetime(start["dateTime"], tz_name))
        vevent.add("dtend", _parse_datetime(end["dateTime"], tz_name))
    elif "date" in start:
        vevent.add("dtstart", date.fromisoformat(start["date"]))
        vevent.add("dtend", date.fromisoformat(end["date"]))
    else:
        raise ValueError(
            f"Événement '{event.get('summary', event.get('id'))}' "
            "sans date de début (ni dateTime ni date)"
        )


def _add_timestamps(vevent: Event, event: dict) -> None:
    """Ajoute les timestamps de création/modification."""
    if event.get("created"):
        vevent.add("created", _parse_datetime(event["created"]))
    if event.get("updated"):
        vevent.add("last-modified", _parse_datetime(event["updated"]))


def _add_status(vevent: Event, event: dict) -> None:
    """Ajoute le statut de l'événement."""
    status = event.get("status", "confirmed")
    vevent.add("status", STATUS_MAP.get(status, "CONFIRMED"))


def _parse_datetime(dt_str: str, tz_name: str | None = None) -> datetime:
    """Parse une date/heure ISO 8601 de Google avec timezone nommée."""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    if tz_name:
        # Convertit vers un timezone nommé (ex: Europe/Paris)
        # pour que les clients CalDAV interprètent correctement le TZID
        tz = ZoneInfo(tz_name)
        dt = dt.astimezone(tz)
    elif dt.utcoffset() is not None:
        # Pas de timezone nommé → convertit en UTC pour éviter les TZID génériques
        dt = dt.astimezone(ZoneInfo("UTC"))
    return dt
