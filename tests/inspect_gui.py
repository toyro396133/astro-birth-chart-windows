"""Actual Windows GUI interaction and rendered screenshots; uses test data only."""
import json
import sys
from datetime import date
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtCore import QDate, QTime, Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QWidget

from astrochart.ui import MainWindow
from astrochart.interpretation_dialog import RuleInterpretationDialog
from astrochart.interpretation import interpret_chart
from astrochart.synthesis import synthesize
from astrochart.narrative import compose_narrative, format_narrative


def snapshot(window, name):
    path = ROOT / "qa-output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    QTest.qWait(300)
    pix = window.grab()
    assert pix.width() >= 1000 and pix.height() >= 700
    assert pix.save(str(path), "PNG"), f"Unable to save screenshot {path}"
    print("SCREENSHOT", str(path), pix.width(), pix.height())



def save_n1_example(name, content):
    """Actual R1->N1 output from a QA chart/fixture, not hand-written copy."""
    path = ROOT / "qa-output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    # GitHub Windows runners may use a legacy console encoding.\n    print("N1_OUTPUT", name, content.encode("unicode_escape").decode("ascii"))


def main():
    app = QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    window = MainWindow()
    window.day.setDate(QDate(2024, 7, 1))
    window.hour.setTime(QTime(12, 30))
    window.city.setCurrentText("ירושלים")
    window.resize(1024, 790)
    window.show()
    QTest.qWait(200)
    # Visual redesign is built from real native Qt widgets, not a mockup.
    header = window.findChild(QFrame, "appHeader")
    assert header is not None
    assert "מפת לידה אסטרונומית" in header.findChild(
        __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel, "appTitle").text()
    assert window.styleSheet() and "panelCard" in window.styleSheet()
    assert window.advanced.isHidden(), "Advanced coordinates should start collapsed"
    window.advanced_toggle.click()
    assert not window.advanced.isHidden(), "Advanced controls must open on click"
    assert window.lat.isEnabled() and window.lon.isEnabled() and window.tz.isEnabled()
    window.advanced_toggle.click()
    assert window.advanced.isHidden(), "Advanced controls must close on click"
    window.city.setCurrentText("הזנה ידנית")
    assert not window.advanced.isHidden(), "Manual location must expose coordinate inputs"
    window.city.setCurrentText("ירושלים")
    window.advanced_toggle.click()
    assert window.advanced.isHidden()
    assert window.day.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert window.hour.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert window.day.text() == "01.07.2024", window.day.text()
    assert window.hour.text() == "12:30", window.hour.text()

    # Click the actual calculate button (not a direct call to the core).
    window.run.click()
    QTest.qWait(150)
    chart = window.wheel.chart
    assert chart is not None, "Calculate button failed to populate wheel"
    assert window.table.rowCount() == 10
    assert chart.ascendant is not None and chart.mc is not None
    assert all(b.house is not None for b in chart.bodies)
    assert all(window.table.item(i, j) is not None
               for i in range(10) for j in range(5))
    assert window.aspects.toPlainText(), "No aspects displayed"
    assert window.interpret_button.isEnabled()
    dialog = RuleInterpretationDialog(chart, window)
    assert dialog.report["signals"]
    assert "גרסת כללים" in dialog.summary.toPlainText()
    assert "sun-" in dialog.details.toPlainText()
    assert '"rule_pack_version"' in dialog.payload.toPlainText()
    dialog.copy_json_button.click()
    copied = json.loads(QApplication.clipboard().text())
    assert copied["generation_constraints"]["quote_rule_ids_for_claims"]
    # Integration gate: R1 is present alongside the interactive W1-W6 UI.
    assert "synthesis" in copied, "R1 synthesis was lost during UI integration"
    assert copied["synthesis"]["engine_version"]
    assert "narrative" in copied, "N1 narrative was lost from the structured payload"
    assert copied["narrative"]["source_engine_version"] == copied["synthesis"]["engine_version"]
    assert dialog.synthesis_report["source_rule_pack"] == dialog.report["pack_version"]
    assert dialog.synthesis_view.isReadOnly()
    assert dialog.narrative_view.isReadOnly()
    assert "קריאה רציפה" in dialog.tabs.tabText(0)
    assert "סינתזה" in dialog.tabs.tabText(1)
    assert "לא אבחון" not in dialog.narrative_readable or "אבחון" in dialog.narrative_readable
    dialog.copy_narrative_button.click()
    assert QApplication.clipboard().text() == dialog.narrative_readable
    dialog.copy_synthesis_button.click()
    assert QApplication.clipboard().text() == dialog.synthesis_readable
    dialog.resize(1024, 790)
    dialog.show()
    snapshot(dialog, "narrative-known.png")
    save_n1_example("n1-known.txt", dialog.narrative_readable)
    # Actual QTextEdit scroll/selection/copy stress under a repeated real
    # report (layout fixture, not a separate semantic example).
    original_n1_text = dialog.narrative_view.toPlainText()
    dialog.narrative_view.setPlainText((original_n1_text + "\n\n") * 6)
    app.processEvents()
    bar = dialog.narrative_view.verticalScrollBar()
    assert bar.maximum() > 0, "Long narrative failed to create vertical scroll"
    bar.setValue(bar.maximum())
    app.processEvents()
    assert bar.value() == bar.maximum()
    snapshot(dialog, "narrative-long-scroll.png")
    dialog.narrative_view.selectAll()
    assert dialog.narrative_view.textCursor().hasSelection()
    dialog.copy_narrative_button.click()
    assert QApplication.clipboard().text() == dialog.narrative_readable
    dialog.narrative_view.setPlainText(original_n1_text)
    assert dialog.narrative_view.isReadOnly()
    dialog.close()
    # Real interactive chart: table -> wheel, then wheel -> table.
    assert window.copy_button.isEnabled()
    assert window.wheel.selected_body is None
    window.table.setCurrentCell(0, 0)
    assert window.wheel.selected_body == "שמש"
    QTest.qWait(120)
    marker = window.wheel._hit_targets.get("ירח")
    assert marker is not None
    QTest.mouseClick(window.wheel, Qt.MouseButton.LeftButton,
                     pos=QPoint(round(marker.x()), round(marker.y())))
    assert window.wheel.selected_body == "ירח"
    assert window.table.item(window.table.currentRow(), 0).text() == "ירח"
    window.copy_button.click()
    report_text = QApplication.clipboard().text()
    assert "שמש" in report_text and "ירח" in report_text
    assert "היבטים:" in report_text
    last = window.table.visualRect(window.table.model().index(9, 0))
    assert last.isValid() and last.bottom() < window.table.viewport().height(), (
        "Ten table rows do not fit at 1024x790",
        last.bottom(), window.table.viewport().height()
    )
    # The final row must not visually collide with the following section
    # heading. On CI, the real desktop is only 749px high.
    last_screen_y = window.table.viewport().mapTo(
        window, QPoint(0, last.bottom())).y()
    next_section_y = window.aspects_title.mapTo(window, QPoint(0, 0)).y()
    assert last_screen_y + 3 < next_section_y, (
        "Chart table visually collides with the aspects section",
        last_screen_y, next_section_y)
    assert "אופק:" in window.warnings.text()
    known = {
        "date": "2024-07-01", "time": "12:30", "city": "ירושלים",
        "latitude": window.lat.value(), "longitude": window.lon.value(),
        "tz": window.tz.text(), "ascendant": float(chart.ascendant), "mc": float(chart.mc),
        "bodies": [{
            "name": b.name, "longitude": float(b.longitude), "house": int(b.house),
            "retrograde": bool(b.retrograde)} for b in chart.bodies],
        "aspects": len(chart.aspects),
        "table_rows": window.table.rowCount()
    }
    snapshot(window, "known-time.png")

    window.unknown.setChecked(True)
    assert not window.hour.isEnabled(), "Hour field still editable"
    window.run.click()
    QTest.qWait(150)
    unknown = window.wheel.chart
    assert unknown is not None and unknown.approximate
    assert unknown.ascendant is None and unknown.mc is None
    assert all(b.house is None for b in unknown.bodies)
    assert all(window.table.item(i, 3).text() == "—" for i in range(10))
    assert "שעת הלידה אינה ידועה" in window.warnings.text()
    unknown_dialog = RuleInterpretationDialog(unknown, window)
    assert unknown_dialog.report["time_uncertain"]
    assert unknown_dialog.structured_payload["chart_facts"]["aspects"] == []
    assert unknown_dialog.synthesis_report["time_mode"] == "unknown"
    assert "synthesis" in unknown_dialog.structured_payload
    assert "narrative" in unknown_dialog.structured_payload
    assert "שעת הלידה אינה ידועה" in unknown_dialog.narrative_readable
    assert all(node["provisional_time"]
               for node in unknown_dialog.synthesis_report["nodes"])
    unknown_dialog.resize(1024, 790)
    unknown_dialog.show()
    snapshot(unknown_dialog, "narrative-unknown.png")
    save_n1_example("n1-unknown.txt", unknown_dialog.narrative_readable)
    unknown_dialog.close()
    snapshot(window, "unknown-time.png")
    unknown_summary = {
        "table_rows": window.table.rowCount(), "ascendant": unknown.ascendant,
        "warnings": window.warnings.text(), "houses_present": False
    }
    # Hebrew date mode: verify an actual button click, not only conversion helper.
    window.unknown.setChecked(False)
    window.date_mode.setCurrentIndex(window.date_mode.findData("hebrew"))
    window.hebrew_year.setValue(5784)
    window.hebrew_month.setCurrentIndex(window.hebrew_month.findData(7))
    window.hebrew_day.setValue(1)
    window.phase.setCurrentIndex(window.phase.findData("evening"))
    assert window.hour.text() == "21:00", window.hour.text()
    assert "15.09.2023" in window.conversion_label.text()
    assert window.approx_hour.isChecked()
    window.run.click()
    QTest.qWait(150)
    assert window.hebrew_year.text() == "5784", window.hebrew_year.text()
    assert window.hebrew_day.text() == "1", window.hebrew_day.text()
    assert window.hebrew_year.width() >= 100 and window.hebrew_day.width() >= 70
    assert window.table.rowCount() == 10
    last_row = window.table.visualRect(window.table.model().index(9, 0))
    assert last_row.isValid() and last_row.bottom() < window.table.viewport().height(), (
        "Hebrew mode must display all ten rows",
        last_row.bottom(), window.table.viewport().height()
    )
    assert window.wheel.chart is not None
    assert window.wheel.chart.ascendant is not None
    assert "המרת תאריך עברי" in window.warnings.text()
    assert "שעת הלידה משוערת" in window.warnings.text()
    assert all(b.house is not None for b in window.wheel.chart.bodies)
    snapshot(window, "hebrew-evening.png")
    estimated_dialog = RuleInterpretationDialog(window.wheel.chart, window)
    assert estimated_dialog.narrative_report["time_mode"] == "estimated"
    assert "שעת הלידה משוערת" in estimated_dialog.narrative_readable
    estimated_dialog.resize(1024, 790)
    estimated_dialog.show()
    snapshot(estimated_dialog, "narrative-estimated.png")
    save_n1_example("n1-estimated.txt", estimated_dialog.narrative_readable)
    estimated_dialog.close()

    window.phase.setCurrentIndex(window.phase.findData("after_midnight"))
    assert window.hour.text() == "01:00", window.hour.text()
    assert "16.09.2023" in window.conversion_label.text()
    window.run.click()
    QTest.qWait(150)
    assert window.wheel.chart is not None
    assert "16.09.2023" in window.warnings.text()
    snapshot(window, "hebrew-after-midnight.png")
    # Windows-hosted desktop is only 1024px wide. Put the real main window
    # inside an offscreen host and let Qt fully *show and lay out* the child at
    # 1360x860. Neither host nor child is mapped to the physical desktop.
    # Hiding a top-level window and resizing it is insufficient: its splitter
    # keeps stale geometry, producing deceptively wide empty screenshots.
    window.hide()
    host = QWidget()
    host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    host.resize(1360, 860)
    window.setParent(host, Qt.WindowType.Widget)
    window.setGeometry(0, 0, 1360, 860)
    host.show()
    window.show()
    app.processEvents()
    QTest.qWait(180)
    assert window.width() >= 1360 and window.height() >= 860, (
        "Wide widget layout was clamped", window.size())
    assert window.wheel.width() >= 430, (
        "Offscreen wide layout did not propagate to the wheel", window.wheel.size())
    snapshot(window, "ui-wide.png")
    from PySide6.QtGui import QImageReader
    wide_path = ROOT / "qa-output" / "ui-wide.png"
    decoded = QImageReader(str(wide_path)).size()
    assert decoded.width() >= 1360 and decoded.height() >= 860, (
        "The actual screenshot is not wide", decoded)


    # Opposing test-only evidence on a real chart, processed by unmodified R1.
    conflict_input = deepcopy(interpret_chart(chart))
    opposing = deepcopy(next(hit for hit in conflict_input["signals"]
                             if hit["rule_id"] == "sun-sign-1"))
    opposing.update(rule_id="qa-opposing-sun", polarity=-1)
    conflict_input["signals"].append(opposing)
    conflict_r1 = synthesize(chart, conflict_input)
    conflict_n1 = compose_narrative(conflict_r1)
    assert any(p["kind"] == "tension" and p["evidence_by_polarity"]
               for section in conflict_n1["sections"] for p in section["paragraphs"])
    save_n1_example("n1-contradictory-fixture.txt", format_narrative(conflict_n1))

    report = {
        "hebrew": {
            "day_input": "01 תשרי 5784",
            "evening_converted": "2023-09-15 21:00",
            "after_midnight_converted": "2023-09-16 01:00",
            "gui_pass": True,
        },
        "known": known,
        "unknown": unknown_summary,
        "gui_pass": True
    }
    output = ROOT / "qa-output" / "gui-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("GUI_QA_PASSED", output)
    window.close()
    app.quit()


if __name__ == "__main__":
    main()
