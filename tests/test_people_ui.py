from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import astrochart.ui as ui
import astrochart.people_storage as people_storage
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
    record = record or make_record(window._capture_input(), ui.__version__)
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


def test_new_chart_for_person_resets_previous_chart_inputs(window):
    person = window._people_store.create_person("בדיקת איפוס")
    window._new_chart_for_person(person["id"])
    window.day.setDate(ui.QDate(1990, 4, 5))
    window.hour.setTime(ui.QTime(18, 45))
    window.city.setCurrentText("תל אביב")
    window.unknown.setChecked(True)
    window.approx_hour.setChecked(True)
    window._new_chart_for_person(person["id"])

    assert window.day.date() == ui.QDate.currentDate()
    assert window.hour.text() == "12:00"
    assert window.city.currentText() == "ירושלים"
    assert window.phase.currentData() == "day"
    assert window.date_mode.currentData() == "gregorian"
    assert not window.unknown.isChecked()
    assert not window.approx_hour.isChecked()
    assert window._active_record is None


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
    labels = [window.people_list.item(row).text()
              for row in range(window.people_list.count())]
    assert len(set(labels)) == 2
    assert all("מזהה" in label for label in labels)


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


def test_legacy_chart_can_be_assigned_to_a_new_person_before_save(
        window, monkeypatch):
    existing = window._people_store.create_person("אדם קיים")
    set_current_chart(window)
    window._active_person_id = None
    monkeypatch.setattr(
        ui.QInputDialog, "getItem",
        lambda parent, title, label, items, current, editable: (items[-1], True))
    monkeypatch.setattr(window, "_person_form", lambda *args: ("אדם חדש", ""))
    monkeypatch.setattr(ui.QInputDialog, "getText",
                        lambda *args: ("מפה ראשונה", True))

    window._save_chart()
    people = window._people_store.list_people()
    created = next(person for person in people if person["name"] == "אדם חדש")
    assert created["id"] != existing["id"]
    assert len(created["maps"]) == 1
    assert created["maps"][0]["name"] == "מפה ראשונה"


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

def test_person_chooser_uses_full_ids_when_short_prefixes_collide(window, monkeypatch):
    generated_ids = iter([
        "12345678aaaaaaaaaaaaaaaaaaaaaaaa",
        "12345678bbbbbbbbbbbbbbbbbbbbbbbb",
    ])
    monkeypatch.setattr(
        people_storage.uuid, "uuid4",
        lambda: SimpleNamespace(hex=next(generated_ids)))
    monkeypatch.setattr(
        people_storage, "_now",
        lambda: "2026-11-09T00:00:00+00:00")
    first = window._people_store.create_person("שם זהה")
    second = window._people_store.create_person("שם זהה")
    seen_labels = []

    def choose_second(_parent, _title, _prompt, labels, _current, _editable):
        seen_labels.extend(labels)
        return labels[1], True

    monkeypatch.setattr(ui.QInputDialog, "getItem", choose_second)
    selected_id = window._choose_person_for_save()

    assert first["id"][:8] == second["id"][:8]
    assert selected_id == second["id"]
    assert len(set(seen_labels[:-1])) == 2
    assert second["id"] in seen_labels[1]


def test_missing_people_index_displays_recovery_state_instead_of_empty_state(
        window, monkeypatch):
    person = window._people_store.create_person("אדם עם מפה")
    entry = window._people_store.save_map(person["id"], "מפה שמורה", sample_record())
    payload = window._people_store.map_path(person["id"], entry["id"])
    original = payload.read_bytes()
    window._people_store.index_path.unlink()
    warnings = []
    monkeypatch.setattr(
        ui.QMessageBox, "warning",
        lambda *args: warnings.append(args[-1]))

    window._refresh_people()

    assert window.people_list.count() == 1
    assert "נדרש שחזור נתונים" in window.people_list.item(0).text()
    assert not window.people_list.isEnabled()
    assert not window.new_person_button.isEnabled()
    assert not window.new_chart_button.isEnabled()
    assert "נדרשת התאוששות" in window.people_count_label.text()
    assert warnings and "קובץ האנשים חסר" in warnings[0]
    assert payload.read_bytes() == original

