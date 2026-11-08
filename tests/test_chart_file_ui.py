"""Focused Qt smoke test for explicit local-only file actions."""
from PySide6.QtWidgets import QApplication, QMessageBox
import pytest

import astrochart.ui as ui
from astrochart import __version__
from astrochart.chart_storage import make_record, read_record
from astrochart.domain import BodyPosition, Chart


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setattr(ui, "auto_updates_enabled", lambda: False)
    monkeypatch.setattr(ui, "auto_install_enabled", lambda: False)
    app = QApplication.instance() or QApplication([])
    # An unexpected UI error must fail CI rather than open a blocking modal.
    def unexpected_dialog(*args):
        raise AssertionError("Unexpected QMessageBox.warning: " + str(args[-1]))
    monkeypatch.setattr(ui.QMessageBox, "warning", unexpected_dialog)
    win = ui.MainWindow()
    win.show()
    app.processEvents()
    win._show_chart(Chart([BodyPosition("שמש", 12.0, False)],
                          [], 14.0, 23.0, False, []))
    win._active_record = make_record(win._capture_input(), __version__)
    yield win
    win.close()
    app.processEvents()


def test_local_save_and_structured_exports(tmp_path, window, monkeypatch):
    path = tmp_path / "saved.astrochart.json"
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName",
                        lambda *args: (str(path), ""))
    window._save_chart(False)
    assert read_record(path)["input"] == window._capture_input()
    assert window._current_file == str(path)

    structured = tmp_path / "export.json"
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName",
                        lambda *args: (str(structured), ""))
    window._export_chart("json")
    assert structured.exists()
    import json
    output = json.loads(structured.read_text(encoding="utf-8"))
    assert output["derived_data"]["bodies"][0]["name"] == "שמש"
    assert output["input_record"]["recalculation_required_on_open"]


def test_changed_inputs_block_saving(tmp_path, window, monkeypatch):
    attempted = tmp_path / "should-not-be-written.json"
    messages = []
    monkeypatch.setattr(ui.QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName",
                        lambda *args: (str(attempted), ""))
    window.hour.setTime(window.hour.time().addSecs(60))
    window._save_chart(False)
    assert not attempted.exists()
    assert any("הקלט השתנה" in message or "יש לחשב" in message
               for message in messages)


def test_native_png_pdf_and_text_exports(tmp_path, window, monkeypatch):
    for kind in ("png", "pdf", "txt"):
        destination = tmp_path / ("chart." + kind)
        monkeypatch.setattr(ui.QFileDialog, "getSaveFileName",
                            lambda *args, destination=destination: (str(destination), ""))
        window._export_chart(kind)
        assert destination.exists(), kind
        if kind == "png":
            assert destination.read_bytes().startswith(b"\\x89PNG".decode("unicode_escape").encode("latin1"))
        elif kind == "pdf":
            assert destination.read_bytes().startswith(b"%PDF")
        else:
            assert "שמש" in destination.read_text(encoding="utf-8")


def test_uncertainty_tooltips_selections_and_table_are_qualified(window):
    """Unknown and estimated positions cannot masquerade as exact values."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    from astrochart.wheel import format_body_label

    unknown = Chart([BodyPosition("ירח", 29.7, False, (0, 1))],
                    [], None, None, True, [])
    window._show_chart(unknown)
    label = window.table.item(0, 0).toolTip()
    assert "טלה / שור" in label
    assert "דגימת אמצע יום" in label and "לא מיקום לידה" in label
    window.table.setCurrentCell(0, 0)
    assert "טלה / שור" in window.wheel_legend.text()
    assert "דגימת אמצע יום" in window.wheel_legend.text()

    window.wheel.grab()
    marker = window.wheel._hit_targets["ירח"]
    QTest.mouseMove(window.wheel, QPoint(round(marker.x()), round(marker.y())))
    assert window.wheel.toolTip() == format_body_label(unknown, unknown.bodies[0])

    estimated = Chart([BodyPosition("ירח", 29.7, False, house=3)],
                      [], 15.0, 20.0, False, [], time_certainty="estimated")
    window._show_chart(estimated)
    assert "לפי שעה משוערת" in window.table.item(0, 0).toolTip()
    assert "משוער" in window.table.item(0, 2).text()
    assert "משוער" in window.table.item(0, 3).text()
    window.table.setCurrentCell(0, 0)
    assert "לפי שעה משוערת" in window.wheel_legend.text()
    assert "בית 3" in window.wheel_legend.text()


def test_uncertainty_note_survives_standalone_png(tmp_path, window):
    from PySide6.QtGui import QImageReader, QColor
    from astrochart.chart_export import export_wheel_png
    from astrochart.wheel import wheel_certainty_note

    cases = [
        ("known", Chart([BodyPosition("ירח", 10, False)], [], 15, 20, False, [])),
        ("estimated", Chart([BodyPosition("ירח", 10, False)], [], 15, 20,
                            False, [], time_certainty="estimated")),
        ("unknown", Chart([BodyPosition("ירח", 10, False, (0, 1))],
                          [], None, None, True, [])),
    ]
    window.wheel.resize(400, 400)
    for name, chart in cases:
        window.wheel.set_chart(chart)
        path = tmp_path / (name + ".png")
        export_wheel_png(window.wheel, path, scale=2)
        image = QImageReader(str(path)).read()
        assert not image.isNull() and image.width() == 800 and image.height() == 800
        note = wheel_certainty_note(chart)
        if name == "known":
            assert note == ""
        else:
            if name == "unknown":
                assert "דגימת אמצע יום" in note
            else:
                assert "שעה משוערת" in note and "בתים והיבטים" in note
            # Footer background is painted into the PNG, not only the UI panel.
            assert image.pixelColor(20, 740) != QColor("#ffffff")


def test_pdf_long_warning_wrap_and_render(tmp_path, window):
    """A multi-line caution uses its measured height in the actual PDF."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QFont, QImage, QPainter
    from astrochart.chart_export import _wrapped_pdf_line_height, export_chart_pdf

    warning = "אזהרת אי־ודאות: " + "שעת הלידה אינה מדויקת ולכן נדרש להיזהר בפרשנות. " * 32
    image = QImage(900, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        painter.setFont(QFont("Segoe UI", 9))
        assert _wrapped_pdf_line_height(painter, 360, warning) > 23
    finally:
        painter.end()
    chart = Chart([BodyPosition("ירח", 29, False)], [], None, None, True,
                  [warning])
    window.wheel.set_chart(chart)
    destination = tmp_path / "wrapped-warning.pdf"
    export_chart_pdf(window.wheel, chart, destination)
    assert destination.read_bytes().startswith(b"%PDF")
    try:
        from PySide6.QtPdf import QPdfDocument
    except ImportError:
        return  # The layout check and actual PDF export above are still mandatory.
    doc = QPdfDocument()
    assert doc.load(str(destination)) == QPdfDocument.Error.None_
    assert doc.pageCount() >= 1
    rendered = doc.render(doc.pageCount() - 1, QSize(900, 1250))
    assert not rendered.isNull()
