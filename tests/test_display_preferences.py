"""Local-only typography and layout preferences."""
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import astrochart.ui as ui
from astrochart.display_preferences import (
    DisplayPreferences, read_preferences, save_preferences,
)
from astrochart.domain import BodyPosition, Chart


def ini(tmp_path):
    return QSettings(str(tmp_path / "display.ini"), QSettings.Format.IniFormat)


def test_display_preferences_roundtrip_and_invalid_fallback(tmp_path):
    settings = ini(tmp_path)
    assert read_preferences(settings) == DisplayPreferences()
    updated = DisplayPreferences(110, 30, 18)
    save_preferences(settings, updated)
    assert read_preferences(ini(tmp_path)) == updated
    settings.setValue("display/font_percent", "9999")
    settings.setValue("display/table_row_height", "not_a_number")
    assert read_preferences(settings) == DisplayPreferences(100, 21, 18)
    with pytest.raises(ValueError):
        save_preferences(settings, DisplayPreferences(250, 99, 0))


def test_gui_apply_preferences_preserves_chart(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "QSettings", lambda *args: ini(tmp_path))
    monkeypatch.setattr(ui, "auto_updates_enabled", lambda: False)
    monkeypatch.setattr(ui, "auto_install_enabled", lambda: False)
    monkeypatch.setattr(ui, "load_favorites", lambda: {})
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow()
    window.show()
    app.processEvents()
    try:
        chart = Chart([BodyPosition("שמש", 12, False)], [], None, None, True, [])
        window._show_chart(chart)
        updated = DisplayPreferences(110, 30, 18)
        save_preferences(window._display_settings, updated)
        window._apply_display_preferences(updated)
        assert window._active_chart is chart
        assert window.wheel.chart is chart
        assert window.table.verticalHeader().defaultSectionSize() == 30
        assert window.wheel._symbol_point_size == 18
        assert "font-size: 25px;" in window.styleSheet()
        assert read_preferences(ini(tmp_path)) == updated
    finally:
        window.close()
