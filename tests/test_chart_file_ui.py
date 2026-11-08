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
