from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import astrochart.ui as ui
from astrochart.chart_storage import make_record, save_record
from astrochart.domain import BodyPosition, Chart
from astrochart.people_storage import PeopleStore


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "auto_updates_enabled", lambda: False)
    monkeypatch.setattr(ui, "auto_install_enabled", lambda: False)
    monkeypatch.setattr(ui, "PeopleStore", lambda: PeopleStore(tmp_path / "people"))
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        ui.QMessageBox, "warning",
        lambda *args: (_ for _ in ()).throw(AssertionError(str(args[-1]))))
    win = ui.MainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def sample_record():
    return make_record({
        "date_mode": "gregorian",
        "civil_date": "2024-07-01",
        "clock": "12:30",
        "gregorian_date": "2024-07-01",
        "hebrew_year": 5784,
        "hebrew_month": 10,
        "hebrew_day": 25,
        "phase": "day",
        "unknown_time": False,
        "estimated_time": False,
        "city": "ירושלים",
        "latitude": 31.7683,
        "longitude": 35.2137,
        "zone": "Asia/Jerusalem",
    }, ui.__version__)


def set_current_chart(window, record=None):
    record = record or sample_record()
    window._active_chart = Chart(
        [BodyPosition("שמש", 12.0, False)], [], 14.0, 23.0, False, [])
    window._active_record = record


def test_people_page_is_the_initial_entry_and_supports_empty_state(window):
    assert window.page_stack.currentWidget() is window.people_page
    assert window.people_list.count() == 0
    assert "עדיין לא נבחר אדם" in window.person_name_label.text()
    assert not window.new_chart_button.isEnabled()


def test_create_person_and_select_existing_person(window, monkeypatch):
    monkeypatch.setattr(window, "_person_form", lambda *args: ("דוד כהן", "הערה"))
    window._create_person()
    assert window.people_list.count() == 1
    person_id = window.people_list.item(0).data(ui.Qt.ItemDataRole.UserRole)
    assert window._people_store.get_person(person_id)["name"] == "דוד כהן"

    window.people_list.setCurrentRow(0)
    window.new_chart_button.click()
    assert window._active_person_id == person_id
    assert window.page_stack.currentWidget() is window.chart_page
    assert "דוד כהן" in window.person_context_label.text()


def test_duplicate_person_names_remain_separate_selectable_records(window):
    first = window._people_store.create_person("יעל")
    second = window._people_store.create_person("יעל")
    window._refresh_people(first["id"])
    assert window.people_list.count() == 2
    ids = {
        window.people_list.item(row).data(ui.Qt.ItemDataRole.UserRole)
        for row in range(window.people_list.count())
    }
    assert ids == {first["id"], second["id"]}


def test_save_requires_person_selection_and_creates_map_under_that_person(window, monkeypatch):
    person = window._people_store.create_person("רוני")
    window._new_chart_for_person(person["id"])
    set_current_chart(window, make_record(window._capture_input(), ui.__version__))
    monkeypatch.setattr(ui.QInputDialog, "getText",
                        lambda *args: ("מפה ראשונה", True))

    window._save_chart()
    stored = window._people_store.get_person(person["id"])
    assert len(stored["maps"]) == 1
    map_entry = stored["maps"][0]
    assert map_entry["name"] == "מפה ראשונה"
    assert window._active_person_id == person["id"]
    assert window._active_map_id == map_entry["id"]
    assert Path(window._current_file).is_file()


def test_legacy_standalone_file_still_opens_without_implicit_person_assignment(
        window, monkeypatch, tmp_path):
    legacy = tmp_path / "legacy.astrochart.json"
    record = sample_record()
    save_record(legacy, record)
    monkeypatch.setattr(ui.QFileDialog, "getOpenFileName",
                        lambda *args: (str(legacy), ""))
    def calculate():
        window._active_chart = Chart(
            [BodyPosition("שמש", 12.0, False)], [], 14.0, 23.0, False, [])
        window._active_record = record
    monkeypatch.setattr(window, "_calculate", calculate)

    window._open_chart()
    assert window._current_file == str(legacy)
    assert window._active_person_id is None
    assert window.page_stack.currentWidget() is window.chart_page
    assert "יש לבחור אדם לפני שמירה" in window.person_context_label.text()


def test_legacy_chart_save_is_cancelled_when_person_selection_is_cancelled(
        window, monkeypatch):
    person = window._people_store.create_person("אסתר")
    set_current_chart(window)
    window._active_person_id = None
    monkeypatch.setattr(ui.QInputDialog, "getItem", lambda *args: ("", False))
    window._save_chart()
    assert window._people_store.get_person(person["id"])["maps"] == []


def test_legacy_chart_can_be_assigned_to_an_existing_person_before_save(
        window, monkeypatch):
    person = window._people_store.create_person("אברהם")
    set_current_chart(window)
    window._active_person_id = None
    monkeypatch.setattr(
        ui.QInputDialog, "getItem",
        lambda parent, title, label, items, current, editable:
            (next(item for item in items if person["id"][:8] in item), True))
    monkeypatch.setattr(ui.QInputDialog, "getText",
                        lambda *args: ("מפה שיובאה", True))

    window._save_chart()
    stored = window._people_store.get_person(person["id"])
    assert len(stored["maps"]) == 1
    assert stored["maps"][0]["name"] == "מפה שיובאה"
    assert window._active_person_id == person["id"]


def test_opening_a_person_map_restores_its_stable_relationship(window, monkeypatch):
    person = window._people_store.create_person("נעמי")
    entry = window._people_store.save_map(person["id"], "מפת בדיקה", sample_record())
    window._refresh_people(person["id"])
    window.people_maps.setCurrentCell(0, 0)
    def calculate():
        window._active_chart = Chart(
            [BodyPosition("שמש", 12.0, False)], [], 14.0, 23.0, False, [])
        window._active_record = sample_record()
    monkeypatch.setattr(window, "_calculate", calculate)

    window._open_selected_person_map()
    assert window._active_person_id == person["id"]
    assert window._active_map_id == entry["id"]
    assert window.page_stack.currentWidget() is window.chart_page
