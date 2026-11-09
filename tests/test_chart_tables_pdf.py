"""Printable, Hebrew, wheel-free positions-and-aspects PDF regression."""
from PySide6.QtWidgets import QApplication

from astrochart.chart_tables_pdf import chart_table_sections, export_chart_tables_pdf
from astrochart.domain import Aspect, BodyPosition, Chart


def example_chart():
    bodies = [
        BodyPosition("שמש", 13.125, False, house=1),
        BodyPosition("ירח", 102.25, True, house=4),
    ]
    aspects = [Aspect("שמש", "ירח", "ריבוע", 89.125, 0.875)]
    return Chart(bodies, aspects, 13.125, 102.25, False, [])


def test_positions_and_aspects_match_the_ui_columns():
    sections = chart_table_sections(example_chart())
    assert [section[0] for section in sections] == [
        "מיקומי הגופים במזלות", "היבטים בין הגופים"]
    position_headings, position_rows = sections[0][1:3]
    aspect_headings, aspect_rows = sections[1][1:3]
    assert position_headings == ["גוף", "מזל", "מעלה במזל", "בית", "תנועה"]
    assert position_rows == [
        ["שמש", "טלה", "13.125°", "1", "ישירה"],
        ["ירח", "סרטן", "12.250°", "4", "נסיגה"],
    ]
    assert aspect_headings == [
        "גוף ראשון", "גוף שני", "היבט", "מרחק", "סטייה", "דיוק"]
    assert aspect_rows == [
        ["שמש", "ירח", "ריבוע", "89.12°", "0.88°", "מחושב"]]


def test_unknown_hour_is_not_misrepresented_as_exact():
    chart = Chart(
        [BodyPosition("ירח", 359.9, False, signs_possible=(11, 0),
                      motion_uncertain=True)],
        [Aspect("שמש", "ירח", "משולש", 120, 1)],
        None, None, True, [])
    positions, aspects = chart_table_sections(chart)
    assert positions[2][0][1] == "דגים / טלה"
    assert "(דגימה)" in positions[2][0][2]
    assert positions[2][0][3] == "—"
    assert positions[2][0][4] == "לא ודאי"
    assert aspects[2][0][-1] == "דגימה בלבד"


def test_estimated_hour_marks_degrees_houses_and_aspects():
    chart = example_chart()
    chart.time_certainty = "estimated"
    chart.bodies[0].degree_certainty = "estimated"
    chart.aspects[0].certainty = "estimated"
    positions, aspects = chart_table_sections(chart)
    assert "(משוער)" in positions[2][0][2]
    assert "(משוער)" in positions[2][0][3]
    assert aspects[2][0][-1] == "משוער"


def test_wheel_free_pdf_renders_directly_from_tables(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import astrochart.chart_export as chart_export
    import astrochart.report as report

    def forbidden(*args, **kwargs):
        raise AssertionError("The table PDF must not use a wheel or text report")
    monkeypatch.setattr(chart_export, "export_chart_pdf", forbidden)
    monkeypatch.setattr(report, "format_chart_report", forbidden)
    output = tmp_path / "signs-and-aspects.pdf"
    export_chart_tables_pdf(example_chart(), output)
    document = output.read_bytes()
    assert document.startswith(b"%PDF-")
    assert len(document) > 1000


def test_many_aspects_generate_multiple_pages(tmp_path):
    QApplication.instance() or QApplication([])
    chart = example_chart()
    chart.aspects = [
        Aspect("שמש", "ירח", "ריבוע", 89.12, float(i) / 100)
        for i in range(60)
    ]
    output = tmp_path / "multipage.pdf"
    export_chart_tables_pdf(chart, output)
    data = output.read_bytes()
    assert data.startswith(b"%PDF-")
    # A4 print layout should paginate instead of clipping after one page.
    assert data.count(b"/Type /Page\n") >= 2 or data.count(b"/Type /Page ") >= 2



def test_header_uses_real_metadata_and_handles_unknown_input():
    from astrochart.chart_tables_pdf import _header_details, _status_note
    entries = _header_details({
        "civil_date": "2026-05-07", "city": "ירושלים",
        "clock": "15:45", "estimated_time": True})
    assert entries == [("תאריך", "07.05.2026"), ("מקום", "ירושלים"),
                       ("שעה", "15:45 (משוערת)")]
    assert _header_details(None) == []
    assert _header_details({"civil_date": "bad", "city": ""}) == []
    unknown = example_chart()
    unknown.time_certainty = "unknown"
    assert "אינה ידועה" in _status_note(unknown)[1]


def test_polished_pdf_accepts_real_metadata_without_creating_a_report(tmp_path):
    QApplication.instance() or QApplication([])
    chart = example_chart()
    output = tmp_path / "designed.pdf"
    export_chart_tables_pdf(chart, output, metadata={
        "civil_date": "2026-05-07", "clock": "09:15",
        "city": "ירושלים", "unknown_time": False})
    data = output.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 2000


def test_large_multiline_rows_and_uncertain_status_paginate_without_truncation(tmp_path):
    QApplication.instance() or QApplication([])
    chart = example_chart()
    chart.time_certainty = "estimated"
    chart.aspects = [Aspect(
        "גוף ראשון עם תיאור ארוך", "גוף שני עם תיאור ארוך",
        "ריבוע", 90, 1.2, certainty="estimated")
        for _ in range(80)]
    path = tmp_path / "many-aspects.pdf"
    export_chart_tables_pdf(chart, path, metadata={
        "civil_date": "2026-05-07", "city": "ירושלים",
        "clock": "09:15", "estimated_time": True})
    raw = path.read_bytes()
    assert raw.startswith(b"%PDF-")
    assert raw.count(b"/Type /Page\n") >= 2 or raw.count(b"/Type /Page ") >= 2
