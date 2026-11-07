"""App entry point. --self-test allows offline validation of frozen Windows executable."""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def self_test():
    from datetime import date, time
    from astrochart.engine import Calculator
    result = Calculator().calculate(
        date(2000, 1, 1), time(12, 0), "Etc/UTC", 0, 0)
    assert len(result.bodies) == 10
    assert result.ascendant is not None
    assert len(result.aspects) > 0
    from astrochart.hebrew_dates import resolve_hebrew_date
    resolved = resolve_hebrew_date(5784, 7, 1, "evening", time(21))
    assert resolved.civil_day == date(2023, 9, 15)
    print("HEBREW_DATE_OK")
    print("OFFLINE_ENGINE_OK")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication
    from astrochart.ui import MainWindow
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    window = MainWindow()
    window.show()
    if "--smoke-gui" in sys.argv:
        QTimer.singleShot(1200, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
