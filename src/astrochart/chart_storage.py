"""Versioned local chart records: input is validated and recalculated on open.

No network, telemetry, or deserialization of executable objects. Saved output is
provenance, not a promise of byte-identical ephemeris/time-zone results.
"""
import json
import math
import os
import tempfile
from datetime import date, time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = "astro-birth-chart"
SCHEMA_VERSION = 1
MAX_FILE_SIZE = 262144
METHOD = {"zodiac": "tropical", "houses": "whole-sign",
          "ephemeris": "de440s.bsp", "aspect_profile": "default-v1"}
FIELDS = ("date_mode", "civil_date", "clock", "gregorian_date", "hebrew_year",
          "hebrew_month", "hebrew_day", "phase", "unknown_time", "estimated_time",
          "city", "latitude", "longitude", "zone")


def _nonempty(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError(f"ערך לא תקין: {field}")
    return value


def validate_input(data):
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        raise ValueError("קובץ המפה אינו כולל את כל שדות הקלט")
    if data["date_mode"] not in ("gregorian", "hebrew", "mixed"):
        raise ValueError("סוג תאריך לא נתמך")
    for field in ("civil_date", "gregorian_date"):
        try:
            value = date.fromisoformat(_nonempty(data[field], field))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"תאריך פגום: {field}") from exc
        if not date(1850, 1, 1) <= value <= date(2149, 12, 31):
            raise ValueError("התאריך מחוץ לטווח החישוב")
    for field in ("unknown_time", "estimated_time"):
        if type(data[field]) is not bool:
            raise ValueError("דגל שעה לא תקין")
    if data["unknown_time"] and data["estimated_time"]:
        raise ValueError("לא ניתן להגדיר שעה ידועה-בקירוב ושעה לא ידועה ביחד")
    if data["clock"] is not None:
        try:
            time.fromisoformat(_nonempty(data["clock"], "clock"))
        except ValueError as exc:
            raise ValueError("פורמט שעה פגום") from exc
    elif not data["unknown_time"]:
        raise ValueError("חסרה שעה ידועה")
    for field in ("hebrew_year", "hebrew_month", "hebrew_day"):
        if type(data[field]) is not int:
            raise ValueError("שדה תאריך עברי פגום")
    if not 5500 <= data["hebrew_year"] <= 6100 or not 1 <= data["hebrew_month"] <= 13 or not 1 <= data["hebrew_day"] <= 30:
        raise ValueError("תאריך עברי מחוץ לטווח")
    if data["phase"] not in ("day", "evening", "after_midnight"):
        raise ValueError("חלק היום אינו נתמך")
    if data["date_mode"] in ("hebrew", "mixed") and data["unknown_time"]:
        raise ValueError("תאריך עברי ללא שעה אינו נתמך")
    if data["date_mode"] == "mixed":
        from .mixed_dates import mixed_candidates
        if data["clock"] is None:
            raise ValueError("תאריך מעורב מחייב שעה")
        civil = date.fromisoformat(data["civil_date"])
        gregorian_year = date.fromisoformat(data["gregorian_date"]).year
        clock = time.fromisoformat(data["clock"])
        options = mixed_candidates(gregorian_year, data["hebrew_month"],
                                   data["hebrew_day"], data["phase"], clock)
        if not any(option.hebrew_year == data["hebrew_year"] and
                   option.resolved.civil_day == civil for option in options):
            raise ValueError("התאריך המעורב אינו תואם את התאריך האזרחי")
    for field, bounds in (("latitude", (-90, 90)), ("longitude", (-180, 180))):
        value = data[field]
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError(f"קואורדינטה פגומה: {field}")
        if not (bounds[0] < value < bounds[1]) if field == "latitude" else not (bounds[0] <= value <= bounds[1]):
            raise ValueError(f"קואורדינטה מחוץ לטווח: {field}")
    _nonempty(data["city"], "city")
    zone = _nonempty(data["zone"], "zone")
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("אזור זמן IANA לא מוכר") from exc
    return data


def _tzdata_version():
    try:
        return version("tzdata")
    except PackageNotFoundError:
        return "system"


def make_record(data, app_version):
    validate_input(data)
    record = {
        "format": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "app_version": _nonempty(app_version, "app_version"),
        "tzdata_version": _tzdata_version(),
        "calculation_method": dict(METHOD),
        "input": dict(data),
        "recalculation_required_on_open": True,
    }
    return validate_record(record)


def validate_record(record):
    if not isinstance(record, dict) or set(record) != {
        "format", "schema_version", "app_version", "tzdata_version",
        "calculation_method", "input", "recalculation_required_on_open"}:
        raise ValueError("מבנה קובץ מפה אינו מוכר")
    if record["format"] != SCHEMA or type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("גרסת פורמט מפה אינה נתמכת")
    _nonempty(record["app_version"], "app_version")
    _nonempty(record["tzdata_version"], "tzdata_version")
    if record["calculation_method"] != METHOD:
        raise ValueError("שיטת החישוב השמורה אינה נתמכת בגרסה זו")
    if record["recalculation_required_on_open"] is not True:
        raise ValueError("קובץ חסר הוראה לחישוב מחדש")
    validate_input(record["input"])
    return record


def save_record(path, record):
    validate_record(record)
    target = Path(path)
    payload = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_FILE_SIZE:
        raise ValueError("קובץ המפה גדול מדי")
    # Write alongside destination to preserve atomicity on the same filesystem.
    fd, temporary = tempfile.mkstemp(prefix=".astrochart-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_record(path):
    target = Path(path)
    if target.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("קובץ המפה גדול מדי")
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("קובץ המפה אינו JSON תקין") from exc
    return validate_record(record)


def export_results(chart, record):
    """Machine-readable chart facts, with explicit sampling caveats."""
    from dataclasses import asdict
    validate_record(record)
    return {
        "format": "astro-birth-chart-results",
        "schema_version": 1,
        "input_record": record,
        "derived_data": {
            "hour_is_unknown": bool(chart.approximate),
            "sampled_midpoint_not_birth_position": bool(chart.approximate),
            "bodies": [asdict(body) for body in chart.bodies],
            "aspects": [asdict(aspect) for aspect in chart.aspects],
            "ascendant": chart.ascendant,
            "mc": chart.mc,
            "warnings": list(chart.warnings),
        },
        "caution": "Computed facts only; unknown-hour positions/aspects are samples, not exact birth data.",
    }
