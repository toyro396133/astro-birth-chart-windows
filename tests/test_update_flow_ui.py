"""Staged updates: metadata checking never downloads; opt-in install is explicit."""
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

import astrochart.ui as ui
from astrochart.updater import (
    Release, auto_install_enabled, auto_updates_enabled, save_auto_install,
    save_auto_updates,
)


def fake_release():
    return Release("9.9.9", "https://example.invalid/release", "a" * 64, 74_000_000)


def test_preferences_are_independent_and_default_safe(tmp_path):
    config = tmp_path / "preferences.json"
    assert not auto_updates_enabled(config)
    assert not auto_install_enabled(config)
    save_auto_updates(True, config)
    assert auto_updates_enabled(config)
    assert not auto_install_enabled(config)
    save_auto_install(True, config)
    assert auto_updates_enabled(config) and auto_install_enabled(config)
    save_auto_updates(False, config)
    assert not auto_updates_enabled(config) and auto_install_enabled(config)
    save_auto_install(False, config)
    assert not auto_install_enabled(config)
    config.write_text("[malformed", encoding="utf-8")
    assert not auto_updates_enabled(config)
    assert not auto_install_enabled(config)


def test_check_thread_never_downloads_or_installs(monkeypatch):
    monkeypatch.setattr(ui, "install_directory", lambda: Path("/fake/AstroBirthChart"))
    monkeypatch.setattr(ui, "is_installed_setup", lambda _: True)
    seen = []
    monkeypatch.setattr(ui, "latest_release", lambda name: seen.append(name) or fake_release())
    def forbidden(*args, **kwargs):
        raise AssertionError("Metadata check must never download or install")
    monkeypatch.setattr(ui, "download_release", forbidden)
    monkeypatch.setattr(ui, "launch_install", forbidden)
    monkeypatch.setattr(ui, "launch_setup_install", forbidden)
    thread = ui.UpdateCheckThread()
    received = []
    thread.result.connect(received.append)
    thread.run()
    assert seen == [ui.SETUP_ASSET]
    assert len(received) == 1
    release, mode = received[0]
    assert release.version == "9.9.9" and mode == "setup"


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setattr(ui, "auto_updates_enabled", lambda: False)
    monkeypatch.setattr(ui, "auto_install_enabled", lambda: False)
    monkeypatch.setattr(ui, "save_auto_install", lambda *_: None)
    monkeypatch.setattr(ui, "save_auto_updates", lambda *_: None)
    app = QApplication.instance() or QApplication([])
    win = ui.MainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def test_checked_version_visible_without_download(window):
    assert window.update_panel.isHidden()
    assert not window.auto_install.isChecked()
    assert window._prepared_update is None
    window._on_update_checked((fake_release(), "setup"))
    assert not window.update_panel.isHidden()
    assert "v9.9.9" in window.latest_update_label.text()
    assert "MB" in window.latest_update_label.text()
    assert "טרם הורד" in window.update_status.text()
    assert window.download_button.isEnabled()
    assert not window.install_button.isEnabled()
    assert window._prepared_update is None


def test_download_confirmation_and_postpone_install(window, monkeypatch, tmp_path):
    release = fake_release()
    window._on_update_checked((release, "setup"))
    sample = tmp_path / "AstroBirthChart-Setup.exe"
    sample.write_bytes(b"test installer placeholder")
    prepared = (release.version, sample, "setup", release.digest)
    requests = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: (
        requests.append("asked") or QMessageBox.StandardButton.No
    ))

    class MockDownload(QObject):
        result = Signal(object)
        error = Signal(str)
        finished = Signal()

        def __init__(self, selected, mode, parent=None):
            super().__init__(parent)
            assert selected == release and mode == "setup"

        def start(self):
            self.result.emit(prepared)
            self.finished.emit()

        def isRunning(self):
            return False

    monkeypatch.setattr(ui, "UpdateDownloadThread", MockDownload)
    window.download_button.click()
    assert requests == ["asked"]
    assert window._prepared_update == prepared
    assert window.install_button.isEnabled()
    assert "מוכנה" in window.update_status.text()
    # Closing removes only an unused package, and no installer ran.
    window.close()
    assert not sample.exists()


def test_explicit_auto_install_skips_confirmation(window, monkeypatch, tmp_path):
    release = fake_release()
    window._on_update_checked((release, "setup"))
    sample = tmp_path / "AstroBirthChart-Setup.exe"
    sample.write_bytes(b"placeholder")
    prepared = (release.version, sample, "setup", release.digest)
    installed = []
    monkeypatch.setattr(window, "_install_prepared",
                        lambda: installed.append(window._prepared_update))
    def unwanted_prompt(*args):
        raise AssertionError("An explicit install-after-download choice should not reprompt")
    monkeypatch.setattr(QMessageBox, "question", unwanted_prompt)

    class MockDownload(QObject):
        result = Signal(object)
        error = Signal(str)
        finished = Signal()

        def __init__(self, selected, mode, parent=None):
            super().__init__(parent)

        def start(self):
            self.result.emit(prepared)
            self.finished.emit()

        def isRunning(self):
            return False

    monkeypatch.setattr(ui, "UpdateDownloadThread", MockDownload)
    window.auto_install.setChecked(True)
    window.download_button.click()
    assert installed == [prepared]
    window._clear_prepared_update()
    assert not sample.exists()


def test_recheck_discards_old_prepared_update(window, tmp_path):
    release = fake_release()
    window._on_update_checked((release, "setup"))
    sample = tmp_path / "AstroBirthChart-Setup.exe"
    sample.write_bytes(b"placeholder")
    window._prepared_update = (release.version, sample, "setup", release.digest)
    window.install_button.setEnabled(True)
    # Start check using a non-running fake thread that doesn't talk to GitHub.
    class CheckThread(QObject):
        result = Signal(object)
        error = Signal(str)
        finished = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)

        def start(self):
            self.result.emit(None)
            self.finished.emit()

        def isRunning(self):
            return False

    from unittest.mock import patch
    with patch.object(ui, "UpdateCheckThread", CheckThread):
        window.update_button.click()
    assert window._prepared_update is None
    assert window.update_panel.isHidden()
    assert not sample.exists()
    assert "אין עדכון" in window.update_status.text()

def test_stale_results_are_removed_after_input_edit(window):
    from astrochart.domain import BodyPosition, Chart
    chart = Chart([BodyPosition("שמש", 12, False)], [], 20, 100, False, [])
    window._show_chart(chart)
    assert window.wheel.chart is chart
    assert window.interpret_button.isEnabled()
    assert window.table.rowCount() == 1
    assert window.table.editTriggers() == ui.QAbstractItemView.EditTrigger.NoEditTriggers
    window.hour.setTime(window.hour.time().addSecs(60))
    assert window.wheel.chart is None
    assert window.table.rowCount() == 0
    assert not window.interpret_button.isEnabled()
    assert "נדרש חישוב מחדש" in window.chart_caption.text()


def test_failed_recalculation_cannot_retain_previous_chart(window, monkeypatch):
    from astrochart.domain import BodyPosition, Chart
    chart = Chart([BodyPosition("שמש", 12, False)], [], 20, 100, False, [])
    window._show_chart(chart)
    class BrokenCalculator:
        def calculate(self, *args, **kwargs):
            raise ValueError("בדיקת תקלה")
    window.calc = BrokenCalculator()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    window._calculate()
    assert window.wheel.chart is None
    assert not window.interpret_button.isEnabled()


def test_copy_selected_row_as_text(window):
    from astrochart.domain import BodyPosition, Chart
    chart = Chart([BodyPosition("שמש", 12, False)], [], None, None, True, [])
    window._show_chart(chart)
    window.table.selectRow(0)
    window._copy_selected_table_rows()
    copied = QApplication.clipboard().text()
    assert "שמש" in copied and "טלה" in copied


def test_update_notes_are_visible_before_downloading(window):
    release = Release("9.9.9", "https://example.invalid/release",
                      "a" * 64, 74_000_000, "גרסה v9.9.9\n- תוספת: יומן שינויים")
    window._on_update_checked((release, "portable"))
    assert window.update_details.isVisible()
    assert window.update_details.isReadOnly()
    assert "יומן שינויים" in window.update_details.toPlainText()
    assert window._prepared_update is None


def test_mixed_calendar_ui_can_choose_ambiguous_date_and_restore(window):
    from datetime import date
    from astrochart.chart_storage import make_record

    window.date_mode.setCurrentIndex(window.date_mode.findData("mixed"))
    window.mixed_year.setValue(2025)
    window.hebrew_month.setCurrentIndex(window.hebrew_month.findData(10))
    window.hebrew_day.setValue(1)
    window.phase.setCurrentIndex(window.phase.findData("day"))
    window.hour.setTime(ui.QTime(12, 0))
    assert window.mixed_choice.count() == 3
    assert window.mixed_choice.currentData() is None
    assert "לבחור התאמה" in window.conversion_label.text()

    window.mixed_choice.setCurrentIndex(2)
    resolved = window._resolved_input()
    assert resolved.civil_day == date(2025, 12, 21)
    values = window._capture_input()
    record = make_record(values, "0.6.0")
    assert record["input"]["date_mode"] == "mixed"
    assert record["input"]["hebrew_year"] == 5786

    window._restore_input(values)
    assert window._capture_input() == values


def test_tables_pdf_menu_exports_positions_and_aspects_not_wheel(window, monkeypatch, tmp_path):
    from astrochart.domain import BodyPosition, Chart, Aspect
    from astrochart.chart_storage import make_record
    chart = Chart([BodyPosition("שמש", 12, False)],
                  [Aspect("שמש", "ירח", "ריבוע", 90, 1)], 20, 100, False, [])
    window._active_chart = chart
    window._active_record = make_record(window._capture_input(), "0.6.2")
    target = tmp_path / "tables.pdf"
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName",
                        lambda *_: (str(target), "PDF (*.pdf)"))
    calls = []
    monkeypatch.setattr(ui, "export_chart_tables_pdf",
                        lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(ui, "export_chart_pdf",
                        lambda *args, **kw: pytest.fail("wheel/report exporter should not run"))
    window._export_chart("pdf_tables")
    assert calls == [((chart, target), {"metadata": window._active_record["input"]})]
    assert any("טבלת מזלות והיבטים" in action.text()
               for action in window.file_menu.actions())
