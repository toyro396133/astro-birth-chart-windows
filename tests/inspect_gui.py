"""Actual Windows GUI interaction and rendered screenshots; uses test data only."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

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
    report = {
        "known": known,
        "unknown": {
            "table_rows": window.table.rowCount(), "ascendant": unknown.ascendant,
            "warnings": window.warnings.text(), "houses_present": False
        },
        "gui_pass": True
    }
    output = ROOT / "qa-output" / "gui-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("GUI_QA_PASSED", output)
    window.close()
    app.quit()


if __name__ == "__main__":
    main()
