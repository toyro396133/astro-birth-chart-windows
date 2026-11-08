"""Mixed Gregorian-year / Hebrew-month-and-day input, calculated offline.

A given Hebrew day may occur twice in one Gregorian year. Never silently
guess the intended occurrence; callers must select a returned candidate.
"""
from dataclasses import dataclass
from datetime import date, time

from pyluach import dates

from .hebrew_dates import ResolvedDate, from_gregorian, months_of_year, resolve_hebrew_date


@dataclass(frozen=True)
class MixedCandidate:
    hebrew_year: int
    resolved: ResolvedDate

    @property
    def key(self) -> str:
        return self.resolved.civil_day.isoformat()

    @property
    def label(self) -> str:
        return f"{self.resolved.civil_day:%d.%m.%Y} (שנה עברית {self.hebrew_year})"


def hebrew_months_in_gregorian_year(gregorian_year: int) -> list[tuple[int, str]]:
    """Union of all Hebrew month variants intersecting one civil year."""
    if not 1850 <= gregorian_year <= 2149:
        raise ValueError("השנה הלועזית מחוץ לטווח 1850–2149")
    begin = from_gregorian(date(gregorian_year, 1, 1))[0]
    end = from_gregorian(date(gregorian_year, 12, 31))[0]
    months = {}
    for year in range(begin, end + 1):
        for number, name in months_of_year(year):
            if number in months and months[number] != name:
                months[number] = "אדר / אדר א׳" if number == 12 else name
            else:
                months[number] = name
    return [(number, months[number]) for number in
            (7, 8, 9, 10, 11, 12, 13, 1, 2, 3, 4, 5, 6)
            if number in months]


def mixed_candidates(gregorian_year: int, hebrew_month: int, hebrew_day: int,
                     phase: str, local_time: time) -> list[MixedCandidate]:
    """All valid choices with a civil birth date inside gregorian_year."""
    if type(gregorian_year) is not int or not 1850 <= gregorian_year <= 2149:
        raise ValueError("השנה הלועזית מחוץ לטווח 1850–2149")
    if type(hebrew_month) is not int or type(hebrew_day) is not int:
        raise ValueError("יום או חודש עברי לא תקינים")
    if phase not in ("day", "evening", "after_midnight"):
        raise ValueError("חלק היום אינו מוכר")
    start, stop = date(gregorian_year, 1, 1), date(gregorian_year, 12, 31)
    hebrew_start = from_gregorian(start)[0]
    hebrew_end = from_gregorian(stop)[0]
    found = []
    for year in range(hebrew_start - 1, hebrew_end + 2):
        try:
            result = resolve_hebrew_date(year, hebrew_month, hebrew_day,
                                         phase, local_time)
        except (ValueError, OverflowError):
            continue
        if start <= result.civil_day <= stop:
            found.append(MixedCandidate(year, result))
    return sorted(found, key=lambda candidate: candidate.resolved.civil_day)
