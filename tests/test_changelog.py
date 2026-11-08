"""Release journal is complete and reproducible."""
from astrochart.changelog import render_history, render_release_notes


def test_per_package_notes():
    notes = render_release_notes("0.6.0")
    assert "עדכונים והפצה" in notes
    assert "קלט תאריכים" in notes
    assert "ייצוא" in notes
    assert "PDF" in notes
    assert render_history().index("v0.6.0") < render_history().index("v0.5.1")
