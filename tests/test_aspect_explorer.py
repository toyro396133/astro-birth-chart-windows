"""Fact-only aspect filtering and single-pair wheel highlighting."""
from PySide6.QtWidgets import QApplication
from astrochart.aspect_explorer import (
    AspectExplorerDialog, certainty_label, filter_aspects,
)
from astrochart.domain import Aspect, BodyPosition, Chart
from astrochart.wheel import Wheel


def sample_chart(*, unknown=False):
    bodies = [BodyPosition("שמש", 5, False),
              BodyPosition("ירח", 35, False),
              BodyPosition("ונוס", 65, False)]
    aspects = [
        Aspect("שמש", "ירח", "ריבוע", 90, 1.0, kind_id="square"),
        Aspect("שמש", "ונוס", "שישים", 60, 0.5, kind_id="sextile"),
        Aspect("ירח", "ונוס", "משולש", 120, 2.0, kind_id="trine"),
    ]
    return Chart(bodies, aspects, None, None, unknown, [])


def test_aspect_filters_sort_by_orb_not_translation():
    chart = sample_chart()
    assert [a.kind_id for a in filter_aspects(chart)] == [
        "sextile", "square", "trine"]
    assert [a.kind_id for a in filter_aspects(chart, body="שמש")] == [
        "sextile", "square"]
    assert [a.kind_id for a in filter_aspects(chart, kind_id="square")] == ["square"]
    assert filter_aspects(chart, body="לא קיים") == []


def test_unknown_hour_aspects_are_labeled_as_samples():
    chart = sample_chart(unknown=True)
    assert certainty_label(chart, chart.aspects[0]) == "דגימת שעה בלבד"


def test_ui_selection_highlights_exact_one_aspect():
    app = QApplication.instance() or QApplication([])
    chart = sample_chart()
    wheel = Wheel()
    wheel.set_chart(chart)
    dialog = AspectExplorerDialog(chart)
    dialog.aspectSelected.connect(wheel.set_selected_aspect_pair)
    dialog.show()
    app.processEvents()
    try:
        assert dialog.table.rowCount() == 3
        assert dialog.body_filter.count() == 4
        dialog.body_filter.setCurrentIndex(
            dialog.body_filter.findData("שמש"))
        assert dialog.table.rowCount() == 2
        dialog.kind_filter.setCurrentIndex(
            dialog.kind_filter.findData("sextile"))
        assert dialog.table.rowCount() == 1
        assert dialog._visible_aspects[0].kind_id == "sextile"
        # QWidget tests must set a current cell; selectRow alone does not
        # always move keyboard focus or emit a current-index change.
        dialog.table.setCurrentCell(0, 0)
        app.processEvents()
        assert dialog.table.currentRow() == 0
        assert wheel.selected_aspect_pair == frozenset(("שמש", "ונוס"))
        wheel.set_selected_body("ירח")
        assert wheel.selected_body == "ירח"
        assert wheel.selected_aspect_pair is None
    finally:
        dialog.close()
        wheel.close()
