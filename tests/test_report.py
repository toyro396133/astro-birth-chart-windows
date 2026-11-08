"""Plain-text chart copy is deterministic and contains no generated predictions."""
import pytest
from astrochart.domain import Aspect, BodyPosition, Chart
from astrochart.report import format_chart_report


def test_factual_report_with_known_time():
    chart = Chart(
        bodies=[
            BodyPosition("שמש", 31.5, False, house=3),
            BodyPosition("ירח", 120.25, True, house=6),
        ],
        aspects=[Aspect("שמש", "ירח", "ריבוע", 88.75, 1.25)],
        ascendant=312.5,
        mc=217.25,
        approximate=False,
        warnings=["בדיקת דיוק לדוגמה"],
    )
    report = format_chart_report(chart)
    assert "שמש: שור, 1.500°, בית: 3" in report
    assert "ירח: אריה, 0.250°, בית: 6, תנועה: נסיגה" in report
    assert "שמש – ירח: ריבוע" in report
    assert "אופק: 312.500°" in report
    assert "רום השמיים (MC): 217.250°" in report
    assert "בדיקת דיוק לדוגמה" in report


def test_approximate_report_never_claims_house_or_certain_sign():
    chart = Chart(
        bodies=[
            BodyPosition("ירח", 29.98, False, signs_possible=(0, 1),
                         motion_uncertain=True, house=None),
        ],
        aspects=[],
        ascendant=None,
        mc=None,
        approximate=True,
        warnings=["שעת הלידה אינה ידועה"],
    )
    report = format_chart_report(chart)
    assert "לא ידועה — תוצאות בקירוב" in report
    assert "ירח: טלה / שור" in report
    assert "בית: לא מחושב" in report
    assert "תנועה: לא ודאי" in report
    assert "מעלה לדוגמה" in report
    assert "אופק:" not in report
    assert "רום השמיים" not in report


def test_report_is_not_available_before_calculation():
    with pytest.raises(ValueError):
        format_chart_report(None)
