"""Actual Windows GUI interaction and rendered screenshots; uses test data only."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtCore import QDate, QTime, Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame

from astrochart.ui import MainWindow


def snapshot(window, name):
    path = ROOT / "qa-output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    QTest.qWait(300)
    pix = window.grab()
    assert pix.width() >= 1000 and pix.height() >= 700
    assert pix.save(str(path), "PNG"), f"Unable to save screenshot {path}"
    print("SCREENSHOT", str(path), pix.width(), pix.height())


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

    window.phase.setCurrentIndex(window.phase.findData("after_midnight"))
    assert window.hour.text() == "01:00", window.hour.text()
    assert "16.09.2023" in window.conversion_label.text()
    window.run.click()
    QTest.qWait(150)
    assert window.wheel.chart is not None
    assert "16.09.2023" in window.warnings.text()
    snapshot(window, "hebrew-after-midnight.png")
    # Wider display snapshot additionally checks the elastic dashboard split.
    window.resize(1360, 860)
    QTest.qWait(180)
    assert window.wheel.width() >= 430
    snapshot(window, "ui-wide.png")

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
