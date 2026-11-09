"""Generate a synthetic PDF design sample for CI artifact review (never user data)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication
from astrochart.chart_tables_pdf import export_chart_tables_pdf
from astrochart.domain import Aspect, BodyPosition, Chart


def main():
    app = QApplication.instance() or QApplication([])
    names = [
        "שמש", "ירח", "מרקורי", "ונוס", "מאדים", "צדק",
        "שבתאי", "אורנוס", "נפטון", "פלוטו",
    ]
    bodies = [
        BodyPosition(name, (13.2 + i * 34.7) % 360, i in (1, 5, 7),
                     house=(i % 12) + 1)
        for i, name in enumerate(names)
    ]
    kinds = ("משולש", "צמידות", "ריבוע", "שישים", "ניגוד")
    aspects = [
        Aspect(names[i % len(names)], names[(i + 3) % len(names)],
               kinds[i % len(kinds)], (i * 17.8 + 44) % 180,
               (i * 0.31) % 5, certainty="known")
        for i in range(18)
    ]
    chart = Chart(bodies, aspects, 13.2, 102.5, False, [])
    target = Path("qa-output/AstroBirthChart-PDF-Design-Preview.pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    export_chart_tables_pdf(chart, target, metadata={
        "civil_date": "2026-04-05", "city": "נתוני הדגמה",
        "clock": "12:00", "unknown_time": False})
    if target.stat().st_size < 2000:
        raise SystemExit("PDF preview is unexpectedly small")
    print(f"PDF_DESIGN_PREVIEW_READY: {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
