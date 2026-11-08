"""Date-mixing tests: leap month, civil-year limits and ambiguity."""
from datetime import date, time

import pytest

from astrochart.mixed_dates import mixed_candidates, hebrew_months_in_gregorian_year


def test_day_and_previous_evening_candidates():
    day = mixed_candidates(2023, 7, 1, "day", time(12))
    assert any(c.hebrew_year == 5784 and c.resolved.civil_day == date(2023, 9, 16)
               for c in day)
    night = mixed_candidates(2023, 7, 1, "evening", time(21))
    assert any(c.hebrew_year == 5784 and c.resolved.civil_day == date(2023, 9, 15)
               for c in night)


def test_leap_month_and_year_boundaries():
    candidates = mixed_candidates(2024, 13, 14, "day", time(12))
    assert [(c.hebrew_year, c.key) for c in candidates] == [(5784, "2024-03-24")]
    assert all(c.resolved.civil_day.year == 2024 for c in candidates)
    assert 13 in [month for month, _ in hebrew_months_in_gregorian_year(2024)]


def test_rejects_bad_input():
    for year in (1849, 2150, True):
        with pytest.raises(ValueError):
            mixed_candidates(year, 7, 1, "day", time(12))
    assert mixed_candidates(2024, 13, 30, "day", time(12)) == []
    with pytest.raises(ValueError):
        mixed_candidates(2024, 7, 1, "invalid", time(12))


def test_ambiguous_mixed_date_is_not_discarded():
    # Across several years a 354-day Hebrew cycle may place the same
    # Hebrew month/day twice in a January-December year.
    found = False
    for year in range(2020, 2061):
        for month in (7, 9, 10, 11, 12, 1):
            if len(mixed_candidates(year, month, 1, "day", time(12))) > 1:
                found = True
                break
        if found:
            break
    assert found
