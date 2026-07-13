"""Conversion iCalendar (VEVENT) → body d'événement Google Calendar API."""

from datetime import date, datetime, timedelta

STATUS_MAP = {
    "CONFIRMED": "confirmed",
    "TENTATIVE": "tentative",
    "CANCELLED": "cancelled",
}

RECURRENCE_PROPS = ("rrule", "rdate", "exdate", "exrule")


def ical_to_google_event(vevent) -> dict:
    """
    Convertit un composant icalendar.Event en body pour l'API Google.

    Lève ValueError si le VEVENT porte RECURRENCE-ID (exception d'occurrence,
    non gérée en écriture) ou s'il n'a pas de DTSTART.
    """
    if vevent.get("recurrence-id") is not None:
        raise ValueError("exception d'occurrence non gérée (RECURRENCE-ID présent)")
    if vevent.get("dtstart") is None:
        raise ValueError("VEVENT sans DTSTART")

    body = {"summary": str(vevent.get("summary", "(sans titre)"))}
    _add_text_fields(body, vevent)
    _add_status(body, vevent)
    _add_dates(body, vevent)

    recurrence = _recurrence_lines(vevent)
    if recurrence:
        body["recurrence"] = recurrence

    return body


def _add_text_fields(body: dict, vevent) -> None:
    """Ajoute description et location si présentes."""
    if vevent.get("description"):
        body["description"] = str(vevent.get("description"))
    if vevent.get("location"):
        body["location"] = str(vevent.get("location"))


def _add_status(body: dict, vevent) -> None:
    """Mappe le STATUS iCal vers le status Google (ignore les valeurs inconnues)."""
    status = vevent.get("status")
    if status is None:
        return
    mapped = STATUS_MAP.get(str(status).upper())
    if mapped:
        body["status"] = mapped


def _add_dates(body: dict, vevent) -> None:
    """Ajoute start/end au format Google (date-only ou dateTime+timeZone)."""
    start_prop = vevent.get("dtstart")
    end_prop = vevent.get("dtend")
    start = start_prop.dt

    if isinstance(start, datetime):
        body["start"] = _google_datetime(start, start_prop)
        end = _end_value(vevent, start, end_prop, fallback=start)
        body["end"] = _google_datetime(end, end_prop or start_prop)
    elif isinstance(start, date):
        body["start"] = {"date": start.isoformat()}
        end = _end_value(vevent, start, end_prop, fallback=start + timedelta(days=1))
        body["end"] = {"date": end.isoformat()}
    else:
        raise ValueError("DTSTART de type inattendu")


def _end_value(vevent, start, end_prop, fallback):
    """DTEND si présent, sinon DTSTART+DURATION (RFC 5545), sinon fallback."""
    if end_prop is not None:
        return end_prop.dt
    duration = vevent.get("duration")
    if duration is not None:
        return start + duration.dt
    return fallback


def _google_datetime(dt: datetime, prop) -> dict:
    """Construit un objet dateTime Google avec timeZone déduit du VEVENT."""
    return {"dateTime": dt.isoformat(), "timeZone": _tz_name(dt, prop)}


def _tz_name(dt: datetime, prop) -> str:
    """Déduit le TZID : param TZID, sinon clé du tzinfo, sinon UTC."""
    tzid = prop.params.get("TZID")
    if tzid:
        return str(tzid)
    key = getattr(dt.tzinfo, "key", None)
    return key or "UTC"


def _recurrence_lines(vevent) -> list:
    """Sérialise RRULE/RDATE/EXDATE/EXRULE en lignes iCal texte pour Google."""
    lines = []
    for name in RECURRENCE_PROPS:
        value = vevent.get(name)
        if value is None:
            continue
        props = value if isinstance(value, list) else [value]
        for prop in props:
            lines.append(_ical_line(name.upper(), prop))
    return lines


def _ical_line(name: str, prop) -> str:
    """Ligne iCal complète, paramètres compris.

    to_ical() ne rend que la valeur : sans les paramètres (TZID d'un EXDATE,
    VALUE=DATE), Google rejette la récurrence ou décale les exclusions.
    """
    params = getattr(prop, "params", None)
    if params:
        return f"{name};{params.to_ical().decode()}:{prop.to_ical().decode()}"
    return f"{name}:{prop.to_ical().decode()}"
