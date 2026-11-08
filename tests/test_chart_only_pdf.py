"""The chart-only PDF is produced locally without consulting the report."""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter

from astrochart.chart_export import export_chart_pdf


class DummyWheel:
    chart = object()

    def width(self):
        return 420

    def height(self):
        return 420

    def render(self, painter, position):
        assert isinstance(painter, QPainter)
        painter.drawEllipse(15, 15, 390, 390)


def test_chart_only_pdf_skips_report_completely(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import astrochart.report as report

    def forbidden(*args, **kwargs):
        raise AssertionError("Chart-only PDF must not format any report or interpretation")

    monkeypatch.setattr(report, "format_chart_report", forbidden)
    path = tmp_path / "wheel-only.pdf"
    export_chart_pdf(DummyWheel(), object(), path, include_report=False)
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 500
