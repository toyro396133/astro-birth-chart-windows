from datetime import date, datetime, time, timezone
from pathlib import Path
import pytest

from astrochart.domain import SIGNS, sign_index
from astrochart.engine import Calculator, ephemeris_path


@pytest.fixture(scope="module")
def calculator():
    if not ephemeris_path().exists():
        pytest.skip("DE440s not provisioned yet; CI downloads pinned kernel before tests")
    return Calculator()


def test_skyfield_published_reference_2020(calculator):
    # Skyfield documentation, DE421: 2020-10-13 23:25:55 UTC
    # Sun 201.07794°, Mars 21.07794° (true ecliptic of date).
    # JPL DE440s should agree well within 0.1 degree.
    moment = datetime(2020, 10, 13, 23, 25, 55, tzinfo=timezone.utc)
    assert abs(calculator.position(moment, "sun") - 201.07794) < 0.1
    assert abs(calculator.position(moment, "mars barycenter") - 21.07794) < 0.1


def test_known_hour_has_houses_and_angles(calculator):
    c = calculator.calculate(date(2000, 1, 1), time(12), "Etc/UTC", 0, 0)
    assert len(c.bodies) == 10
    assert 0 <= c.ascendant < 360
    assert 0 <= c.mc < 360
    assert all(1 <= b.house <= 12 for b in c.bodies)


def test_unknown_hour_has_no_angles_or_houses(calculator):
    c = calculator.calculate(date(2000, 1, 1), None, "Asia/Jerusalem",
                             31.7683, 35.2137, unknown_time=True)
    assert c.approximate
    assert c.ascendant is None and c.mc is None
    assert all(b.house is None for b in c.bodies)
    assert c.time_certainty == "unknown"
    assert all(b.degree_certainty == "estimated" for b in c.bodies)
    assert all(a.certainty == "estimated" for a in c.aspects)


def test_unknown_hour_moon_cusp_scenario(calculator):
    # Search over several dates and verify reported alternatives match samples.
    for day in range(1, 29):
        c = calculator.calculate(date(2024, 1, day), None, "Etc/UTC",
                                 0, 0, unknown_time=True)
        moon = next(b for b in c.bodies if b.name == "ירח")
        assert moon.signs_possible
        if len(moon.signs_possible) > 1:
            assert "עשוי להחליף מזל" in "\n".join(c.warnings)
            return
    pytest.fail("Moon never crossed a sign boundary in tested period")
