from datetime import date, datetime, timezone
import pytest
from astrochart.timeconv import full_local_day, local_to_utc


def test_jerusalem_dst_vs_winter():
    summer = local_to_utc(datetime(2024, 7, 1, 12), "Asia/Jerusalem")
    winter = local_to_utc(datetime(2024, 1, 1, 12), "Asia/Jerusalem")
    assert summer.hour == 9
    assert winter.hour == 10


def test_nonexistent_time_rejected():
    with pytest.raises(ValueError, match="אינה קיימת"):
        local_to_utc(datetime(2024, 3, 10, 2, 30), "America/New_York")


def test_ambiguous_time_rejected():
    with pytest.raises(ValueError, match="כפולה"):
        local_to_utc(datetime(2024, 11, 3, 1, 30), "America/New_York")


def test_dst_short_day():
    a, b = full_local_day(date(2024, 3, 10), "America/New_York")
    assert (b - a).total_seconds() == 23 * 3600
