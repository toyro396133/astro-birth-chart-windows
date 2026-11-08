"""Small offline city index with bilingual aliases and user-chosen local favorites.

Coordinates for the seed set remain in locations.CITIES; additional positions are
never fabricated. Favorites retain coordinates explicitly provided by the user.
No geocoding, networking, telemetry, or background updates.
"""
import json
import math
import os
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .locations import CITIES

ALIASES = {
    "Jerusalem": "ירושלים",
    "Tel Aviv": "תל אביב",
    "Tel Aviv-Yafo": "תל אביב",
    "Haifa": "חיפה",
    "Bnei Brak": "בני ברק",
    "Beer Sheva": "באר שבע",
    "Beersheba": "באר שבע",
    "London": "לונדון",
    "New York": "ניו יורק",
    "New York City": "ניו יורק",
    "Paris": "פריז",
    "Moscow": "מוסקבה",
}
MANUAL_LABEL = "הזנה ידנית"
MAX_FAVORITES = 200
MAX_BYTES = 65536


def _normalized(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().split())


def catalog_labels(favorites=None):
    favorites = favorites or {}
    return [MANUAL_LABEL, *CITIES, *ALIASES,
            *(name for name in favorites if name not in CITIES and name not in ALIASES)]


def resolve_location(name, favorites=None):
    favorites = favorites or {}
    normalized = _normalized(name)
    for label, value in favorites.items():
        if _normalized(label) == normalized:
            return tuple(value)
    for label, value in CITIES.items():
        if _normalized(label) == normalized:
            return value
    for alias, canonical in ALIASES.items():
        if _normalized(alias) == normalized:
            return CITIES[canonical]
    return None


def favorite_path():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "AstroBirthChart" / "locations.json"
    return Path.home() / ".config" / "AstroBirthChart" / "locations.json"


def validate_favorite(name, latitude, longitude, zone):
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 70
            or any(c in name for c in "\n\r\t")):
        raise ValueError("יש לתת שם קצר ותקין למיקום")
    if _normalized(name) == _normalized(MANUAL_LABEL) or any(
        _normalized(name) == _normalized(label)
        for label in [*CITIES, *ALIASES]
    ):
        raise ValueError("שם המיקום כבר שמור במאגר הבסיסי")
    for value, left, right in ((latitude, -90, 90), (longitude, -180, 180)):
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("קואורדינטות לא תקינות")
        if not (left < value < right) if left == -90 else not (left <= value <= right):
            raise ValueError("קואורדינטות מחוץ לטווח")
    if not isinstance(zone, str) or not zone or len(zone) > 100:
        raise ValueError("חובה לבחור אזור זמן IANA")
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("אזור זמן IANA אינו תקין") from exc
    return [float(latitude), float(longitude), zone]


def load_favorites(path=None):
    target = Path(path) if path is not None else favorite_path()
    if not target.exists():
        return {}
    try:
        if target.stat().st_size > MAX_BYTES:
            return {}
        payload = json.loads(target.read_text(encoding="utf-8"))
        if (not isinstance(payload, dict) or payload.get("version") != 1
                or not isinstance(payload.get("favorites"), dict)):
            return {}
        favorites = {}
        for name, values in list(payload["favorites"].items())[:MAX_FAVORITES]:
            if not isinstance(values, list) or len(values) != 3:
                continue
            try:
                favorites[name] = validate_favorite(name, *values)
            except (ValueError, TypeError):
                continue
        return favorites
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def save_favorite(name, latitude, longitude, zone, path=None):
    values = validate_favorite(name, latitude, longitude, zone)
    target = Path(path) if path is not None else favorite_path()
    old = load_favorites(target)
    if (len(old) >= MAX_FAVORITES and not any(
            _normalized(key) == _normalized(name) for key in old)):
        raise ValueError("הגעת למכסת המיקומים המועדפים")
    for key in old:
        if _normalized(key) == _normalized(name):
            name = key
            break
    old[name] = values
    payload = json.dumps(
        {"version": 1, "favorites": old},
        ensure_ascii=False, indent=2, allow_nan=False,
    ) + "\n"
    if len(payload.encode("utf-8")) > MAX_BYTES:
        raise ValueError("קובץ המיקומים גדול מדי")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".astro-location-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return old
