"""Offline Hebrew date conversion, leap years and solar day/night checks."""
from datetime import date, time
import pytest

from astrochart.hebrew_dates import (
    from_gregorian, months_of_year, days_of_month, resolve_hebrew_date,
    validate_phase_sun,
)


def test_hebrew_new_year_to_day_and_previous_evening():
    # First daytime of 1 Tishrei 5784 = 16 September 2023.
    midday = resolve_hebrew_date(5784, 7, 1, "day", time(12))
    evening = resolve_hebrew_date(5784, 7, 1, "evening", time(21))
    early = resolve_hebrew_date(5784, 7, 1, "after_midnight", time(1))
    assert midday.civil_day == date(2023, 9, 16)
    assert evening.civil_day == date(2023, 9, 15)
    assert early.civil_day == date(2023, 9, 16)
    assert midday.local_time == time(12)


def test_roundtrip_fixed_reference():
    assert from_gregorian(date(2023, 9, 16)) == (5784, 7, 1)
    assert from_gregorian(date(2024, 3, 24)) == (5784, 13, 14)


def test_leap_year_months_and_days():
    months = months_of_year(5784)
    assert len(months) == 13
    assert any(n == 13 for n, _ in months)
    assert len(months_of_year(5783)) == 12
    assert days_of_month(5784, 13) == 29
    assert days_of_month(5784, 7) == 30


@pytest.mark.parametrize("month,day", [(7, 31), (13, 30), (0, 1)])
def test_invalid_hebrew_date_rejected(month, day):
    with pytest.raises(ValueError):
        resolve_hebrew_date(5784, month, day, "day", time(12))


def test_leap_month_not_in_regular_year():
    with pytest.raises(ValueError):
        resolve_hebrew_date(5783, 13, 10, "day", time(12))


def test_unknown_phase_rejected():
    with pytest.raises(ValueError):
        resolve_hebrew_date(5784, 7, 1, "twilight", time(12))


def test_night_clock_cannot_contradict_selected_half():
    with pytest.raises(ValueError):
        resolve_hebrew_date(5784, 7, 1, "evening", time(1))
    with pytest.raises(ValueError):
        resolve_hebrew_date(5784, 7, 1, "after_midnight", time(21))


def test_check_solar_day_night():
    with pytest.raises(ValueError):
        validate_phase_sun("evening", 25)
    with pytest.raises(ValueError):
        validate_phase_sun("day", -25)
    assert validate_phase_sun("day", 30) is None
    assert validate_phase_sun("evening", -20) is None
    assert validate_phase_sun("after_midnight", -20) is None
    assert validate_phase_sun("evening", -0.8) is not None
