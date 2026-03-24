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


def google_event_to_ical(event: dict) -> str:
    """Convertit un événement Google Calendar en string iCalendar."""
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")

    vevent = _build_vevent(event)
    cal.add_component(vevent)

    return cal.to_ical().decode("utf-8")


def _build_vevent(event: dict) -> Event:
    """Construit un composant VEVENT à partir d'un événement Google."""
    vevent = Event()

    vevent.add("uid", event["id"] + GOOGLE_UID_SUFFIX)
    vevent.add("summary", event.get("summary", "(sans titre)"))

    if event.get("description"):
        vevent.add("description", event["description"])
    if event.get("location"):
        vevent.add("location", event["location"])

    _add_dates(vevent, event)
    _add_timestamps(vevent, event)
    _add_status(vevent, event)

    return vevent


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
        # pour que Synology interprète correctement le TZID
        tz = ZoneInfo(tz_name)
        dt = dt.astimezone(tz)
    elif dt.utcoffset() is not None:
        # Pas de timezone nommé → convertit en UTC pour éviter les TZID génériques
        dt = dt.astimezone(ZoneInfo("UTC"))
    return dt
