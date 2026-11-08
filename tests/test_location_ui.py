"""Qt location picker guards against unrecognized place names."""
import pytest
from PySide6.QtWidgets import QApplication

import astrochart.ui as ui
from astrochart.locations import CITIES


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setattr(ui, "auto_updates_enabled", lambda: False)
    monkeypatch.setattr(ui, "auto_install_enabled", lambda: False)
    monkeypatch.setattr(ui, "load_favorites", lambda: {})
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow()
    window.show()
    app.processEvents()
    yield window
    window.close()
    app.processEvents()


def test_alias_search_uses_known_local_coordinates(window):
    window.city.setCurrentText("Jerusalem")
    assert window.run.isEnabled()
    assert window.lat.value() == pytest.approx(CITIES["ירושלים"][0], abs=1e-4)
    assert window.lon.value() == pytest.approx(CITIES["ירושלים"][1], abs=1e-4)
    assert window.tz.text() == "Asia/Jerusalem"


def test_unknown_city_cannot_reuse_previous_coordinates(window):
    window.city.setCurrentText("Not In Local Database")
    assert not window.run.isEnabled()
    window.city.setCurrentText("הזנה ידנית")
    assert window.run.isEnabled()
    assert not window.advanced.isHidden()


def test_saved_location_uses_local_user_supplied_values(window, monkeypatch):
    inputs = []
    monkeypatch.setattr(ui.QInputDialog, "getText",
                        lambda *args: ("מקום אישי", True))
    def store(name, lat, lon, tz):
        inputs.append((name, lat, lon, tz))
        return {name: [lat, lon, tz]}
    monkeypatch.setattr(ui, "save_favorite", store)
    window.city.setCurrentText("הזנה ידנית")
    window.lat.setValue(31.1111)
    window.lon.setValue(35.2222)
    window.tz.setText("Asia/Jerusalem")
    window.save_favorite_button.click()
    assert inputs == [("מקום אישי", 31.1111, 35.2222, "Asia/Jerusalem")]
    assert window.city.currentText() == "מקום אישי"
    assert window.run.isEnabled()
