"""IANA historical time zones. Ambiguous/nonexistent wall times are rejected."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def valid_utc_instants(wall: datetime, zone_name: str) -> list[datetime]:
    if wall.tzinfo is not None:
        raise ValueError("Expected a local date and time without a UTC offset")
    try:
        tz = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("אזור הזמן אינו מוכר במאגר המקומי") from exc
    instants = set()
    for fold in (0, 1):
        candidate = wall.replace(tzinfo=tz, fold=fold)
        utc = candidate.astimezone(timezone.utc)
        if utc.astimezone(tz).replace(tzinfo=None) == wall:
            instants.add(utc)
    return sorted(instants)


def local_to_utc(wall: datetime, zone_name: str) -> datetime:
    options = valid_utc_instants(wall, zone_name)
    if not options:
        raise ValueError("השעה אינה קיימת באזור הזמן עקב מעבר שעון")
    if len(options) > 1:
        raise ValueError("השעה כפולה עקב מעבר שעון; בחר שעה חד-משמעית")
    return options[0]


def full_local_day(day, zone_name: str) -> tuple[datetime, datetime]:
    # Use a half-open UTC interval covering the entire local civil day.
    start = valid_utc_instants(datetime.combine(day, time.min), zone_name)
    end = valid_utc_instants(datetime.combine(day + timedelta(days=1), time.min), zone_name)
    if not start or not end:
        raise ValueError("אין אפשרות לקבוע את גבולות היום באזור הזמן הזה")
    return min(start), max(end)
