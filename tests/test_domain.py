import pytest
from astrochart.domain import (
    BodyPosition, calculate_aspects, degree_in_sign, house_of,
    short_separation, sign_index,
)


def test_sign_boundaries_and_wraparound():
    assert sign_index(0) == 0
    assert sign_index(29.9999) == 0
    assert sign_index(30) == 1
    assert sign_index(-0.1) == 11
    assert degree_in_sign(390) == 0


def test_whole_sign_houses():
    assert house_of(300, 291) == 2
    assert house_of(0, 291) == 4
    assert house_of(240, 291) == 12


def test_separation_and_aspect_orb():
    assert short_separation(359, 1) == 2
    a = BodyPosition("a", 10, False)
    b = BodyPosition("b", 102, False)
    aspects = calculate_aspects([a, b])
    assert len(aspects) == 1
    assert aspects[0].kind == "ריבוע"
    assert aspects[0].separation == 92
    assert aspects[0].orb == 2

def test_aspect_has_stable_identifier_not_translated_label():
    bodies = [BodyPosition("a", 20, False), BodyPosition("b", 80, False)]
    aspects = calculate_aspects(bodies)
    assert len(aspects) == 1
    assert aspects[0].kind == "שישים"
    assert aspects[0].kind_id == "sextile"
    assert aspects[0].certainty == "known"


def test_legacy_approximate_chart_is_unknown_time():
    from astrochart.domain import Chart
    chart = Chart([], [], None, None, True, [])
    assert chart.time_certainty == "unknown"
