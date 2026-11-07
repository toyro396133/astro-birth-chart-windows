"""Hebrew-to-Gregorian birth-date input. Everything is calculated offline.

pyluach's corresponding Gregorian date is the civil *daytime* date.
A Hebrew date starts on the preceding evening. After-midnight night
belongs to the same civil date as the daytime portion.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from pyluach import dates, hebrewcal
from .timeconv import local_to_utc

Phase = Literal["day", "evening", "after_midnight"]

PHASE_LABELS = {
    "day": "יום",
    "evening": "לילה — בערב שלפני חצות",
    "after_midnight": "לילה — אחרי חצות",
}


@dataclass(frozen=True)
class ResolvedDate:
    civil_day: date
    local_time: time
    phase: Phase

    @property
    def label(self) -> str:
        return f"{self.civil_day:%d.%m.%Y} בשעה {self.local_time:%H:%M}"


def months_of_year(year: int) -> list[tuple[int, str]]:
    """Calendar order, Tishrei through Elul, including leap Adar months."""
    return [(m.month, m.month_name(hebrew=True)) for m in hebrewcal.Year(year).itermonths()]


def days_of_month(year: int, month: int) -> int:
    return sum(1 for _ in hebrewcal.Month(year, month).iterdates())


def from_gregorian(day: date) -> tuple[int, int, int]:
    h = dates.HebrewDate.from_pydate(day)
    return h.year, h.month, h.day


def resolve_hebrew_date(year: int, month: int, day: int, phase: Phase,
                        local_time: time) -> ResolvedDate:
    """Resolve the Gregorian civil date; never guess an unentered birth hour."""
    if phase not in PHASE_LABELS:
        raise ValueError("חלק היום אינו מוכר")
    try:
        base = dates.HebrewDate(year, month, day).to_pydate()
    except (ValueError, OverflowError) as exc:
        raise ValueError("התאריך העברי אינו תקין (בדוק יום, חודש ושנה)") from exc
    if phase == "evening":
        if local_time.hour < 12:
            raise ValueError("לילה לפני חצות: יש לבחור שעה בין 12:00 ל־23:59")
        base -= timedelta(days=1)
    elif phase == "after_midnight" and local_time.hour >= 12:
        raise ValueError("לילה אחרי חצות: יש לבחור שעה בין 00:00 ל־11:59")
    if not (date(1850, 1, 1) <= base <= date(2149, 12, 31)):
        raise ValueError("התאריך הלועזי מחוץ לטווח האפמריס (1850–2149)")
    return ResolvedDate(base, local_time, phase)


def sun_altitude(calculator, civil_day: date, local_time: time, zone: str,
                 latitude: float, longitude: float) -> float:
    """Solar apparent altitude at the local input (degrees, no refraction).

    Uses the same bundled JPL ephemeris as the chart, no network service.
    """
    from skyfield.api import wgs84
    utc = local_to_utc(datetime.combine(civil_day, local_time), zone)
    t = calculator.timescale.from_datetime(utc)
    observer = calculator.earth + wgs84.latlon(
        latitude_degrees=latitude, longitude_degrees=longitude)
    alt, _, _ = observer.at(t).observe(calculator.planets["sun"]).apparent().altaz()
    return float(alt.degrees)


def validate_phase_sun(phase: Phase, altitude: float) -> str | None:
    """Prevent obviously wrong Hebrew-day assignment near sunrise/sunset.

    Approximate horizon threshold: solar upper limb ~-0.833 degrees.
    At the boundary, return a caveat instead of falsely fixing the date.
    """
    if phase == "day" and altitude < -2.0:
        raise ValueError("השעה שנבחרה היא בלילה לפי מקום הלידה; בחר לילה או תקן שעה")
    if phase != "day" and altitude > 1.0:
        raise ValueError("השעה שנבחרה היא ביום לפי מקום הלידה; בחר יום או תקן שעה")
    if abs(altitude + 0.833) < 1.5:
        return ("השעה סמוכה לזריחה או לשקיעה: קביעת היום תלויה באופק המקומי "
                "ובדיוק השעה המשוערת.")
    return None
