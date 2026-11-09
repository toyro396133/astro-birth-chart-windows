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
    # The shared application header owns the brand and update controls; the
    # people page adds a light section heading instead of a second dark header.
    assert len(window.findChildren(ui.QFrame, "appHeader")) == 1
    assert window.update_button.isVisible()
    assert window.auto_update.isVisible()


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

def test_person_form_updates_inline_warning_for_fuzzy_match(window, monkeypatch):
    window._people_store.create_person("דוד כהן")
    observed = {}

    def inspect_dialog(dialog):
        name_edit = dialog.findChild(ui.QLineEdit, "personNameEdit")
        warning = dialog.findChild(ui.QLabel, "personSimilarityWarning")
        save = dialog.findChild(ui.QPushButton, "personFormSaveButton")
        name_edit.setText("שם אחר")
        assert warning.isHidden()
        name_edit.setText("דוד כוהן")
        observed["warning"] = warning.text()
        observed["visible"] = not warning.isHidden()
        observed["save_enabled"] = save.isEnabled()
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui.QDialog, "exec", inspect_dialog)
    assert window._person_form("אדם חדש") is None
    assert observed["visible"]
    assert "שם דומה" in observed["warning"]
    assert "דוד כהן" in observed["warning"]
    assert observed["save_enabled"]


def test_exact_duplicate_warning_does_not_block_creating_a_second_person(
        window, monkeypatch):
    first = window._people_store.create_person("יעל כהן")
    observed = {}

    def accept_duplicate(dialog):
        name_edit = dialog.findChild(ui.QLineEdit, "personNameEdit")
        warning = dialog.findChild(ui.QLabel, "personSimilarityWarning")
        save = dialog.findChild(ui.QPushButton, "personFormSaveButton")
        name_edit.setText("יעל כהן")
        observed["warning"] = warning.text()
        observed["visible"] = not warning.isHidden()
        observed["save_enabled"] = save.isEnabled()
        return ui.QDialog.DialogCode.Accepted

    monkeypatch.setattr(ui.QDialog, "exec", accept_duplicate)
    window._create_person()

    people = window._people_store.list_people()
    assert len(people) == 2
    assert people[0]["id"] != people[1]["id"]
    assert {person["name"] for person in people} == {"יעל כהן"}
    assert observed["visible"] and "שם זהה" in observed["warning"]
    assert first["id"] in {person["id"] for person in people}
    assert observed["save_enabled"]


def test_edit_similarity_check_excludes_current_person_but_finds_other_duplicate(
        window, monkeypatch):
    first = window._people_store.create_person("רות לוי")
    second = window._people_store.create_person("רות לוי")
    window._refresh_people(first["id"])
    observed = {}

    def inspect_edit(dialog):
        name_edit = dialog.findChild(ui.QLineEdit, "personNameEdit")
        warning = dialog.findChild(ui.QLabel, "personSimilarityWarning")
        save = dialog.findChild(ui.QPushButton, "personFormSaveButton")
        assert name_edit.text() == "רות לוי"
        observed["warning"] = warning.text()
        observed["visible"] = not warning.isHidden()
        observed["save_enabled"] = save.isEnabled()
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui.QDialog, "exec", inspect_edit)
    window._edit_person()

    assert observed["visible"]
    assert "רות לוי" in observed["warning"]
    assert second["id"][:8] in observed["warning"]
    assert first["id"][:8] not in observed["warning"]
    assert observed["save_enabled"]
    assert window._people_store.get_person(first["id"])["name"] == "רות לוי"
    assert window._people_store.get_person(second["id"])["name"] == "רות לוי"



def test_map_version_history_dialog_lists_versions_and_marks_current(window, monkeypatch):
    person = window._people_store.create_person("היסטוריית מפה")
    entry = window._people_store.save_map(person["id"], "מפה", sample_record())
    changed = make_record({
        "date_mode": "gregorian", "civil_date": "2024-07-03",
        "clock": "14:00", "gregorian_date": "2024-07-03",
        "hebrew_year": 5784, "hebrew_month": 10, "hebrew_day": 27,
        "phase": "day", "unknown_time": False, "estimated_time": False,
        "city": "תל אביב", "latitude": 32.0853, "longitude": 34.7818,
        "zone": "Asia/Jerusalem",
    }, ui.__version__)
    window._people_store.update_map(person["id"], entry["id"], "מפה", changed)
    window._refresh_people(person["id"])
    window.people_maps.setCurrentCell(0, 0)
    observed = {}

    def inspect_dialog(dialog):
        table = dialog.findChild(ui.QTableWidget, "mapVersionHistoryTable")
        restore = dialog.findChild(ui.QPushButton, "restoreMapVersionButton")
        preview = dialog.findChild(ui.QPushButton, "openMapVersionButton")
        observed["rows"] = table.rowCount()
        observed["labels"] = [table.item(row, 0).text() for row in range(table.rowCount())]
        observed["states"] = [table.item(row, 3).text() for row in range(table.rowCount())]
        observed["restore_enabled"] = restore.isEnabled()
        observed["preview_enabled"] = preview.isEnabled()
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui.QDialog, "exec", inspect_dialog)
    window._show_map_version_history()
    assert observed["rows"] == 2
    assert observed["labels"] == ["גרסה 1", "גרסה 2"]
    assert observed["states"] == ["קודמת", "נוכחית"]
    assert observed["restore_enabled"] is False
    assert observed["preview_enabled"] is True


def test_map_version_restore_confirmation_cancel_keeps_current_version(window, monkeypatch):
    person = window._people_store.create_person("ביטול שחזור")
    entry = window._people_store.save_map(person["id"], "מפה", sample_record())
    window._people_store.update_map(
        person["id"], entry["id"], "מפה",
        make_record({
            "date_mode": "gregorian", "civil_date": "2024-07-03",
            "clock": "14:00", "gregorian_date": "2024-07-03",
            "hebrew_year": 5784, "hebrew_month": 10, "hebrew_day": 27,
            "phase": "day", "unknown_time": False, "estimated_time": False,
            "city": "תל אביב", "latitude": 32.0853, "longitude": 34.7818,
            "zone": "Asia/Jerusalem",
        }, ui.__version__))
    current = window._people_store.read_map(person["id"], entry["id"])
    monkeypatch.setattr(ui.QMessageBox, "question",
                        lambda *args: ui.QMessageBox.StandardButton.No)

    def cancel_restore(dialog):
        dialog.findChild(ui.QTableWidget, "mapVersionHistoryTable").selectRow(0)
        dialog.findChild(ui.QPushButton, "restoreMapVersionButton").click()
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui.QDialog, "exec", cancel_restore)
    window._refresh_people(person["id"])
    window.people_maps.setCurrentCell(0, 0)
    window._show_map_version_history()
    assert window._people_store.read_map(person["id"], entry["id"]) == current
    history = window._people_store.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == 2 and history["versions"][-1]["is_current"]


def test_map_version_restore_creates_new_version_and_preserves_map_link(window, monkeypatch):
    person = window._people_store.create_person("שחזור בממשק")
    entry = window._people_store.save_map(person["id"], "מפה", sample_record())
    first = window._people_store.list_map_versions(person["id"], entry["id"])["versions"][0]
    changed = make_record({
        "date_mode": "gregorian", "civil_date": "2024-07-03",
        "clock": "14:00", "gregorian_date": "2024-07-03",
        "hebrew_year": 5784, "hebrew_month": 10, "hebrew_day": 27,
        "phase": "day", "unknown_time": False, "estimated_time": False,
        "city": "תל אביב", "latitude": 32.0853, "longitude": 34.7818,
        "zone": "Asia/Jerusalem",
    }, ui.__version__)
    window._people_store.update_map(person["id"], entry["id"], "מפה", changed)
    monkeypatch.setattr(ui.QMessageBox, "question",
                        lambda *args: ui.QMessageBox.StandardButton.Yes)

    def restore_first(dialog):
        table = dialog.findChild(ui.QTableWidget, "mapVersionHistoryTable")
        table.setCurrentCell(0, 0)
        dialog.findChild(ui.QPushButton, "restoreMapVersionButton").click()
        history_table = dialog.findChild(ui.QTableWidget, "mapVersionHistoryTable")
        assert history_table.rowCount() == 3
        assert history_table.item(2, 3).text() == "נוכחית"
        return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui.QDialog, "exec", restore_first)
    window._refresh_people(person["id"])
    window.people_maps.setCurrentCell(0, 0)
    window._show_map_version_history()
    history = window._people_store.list_map_versions(person["id"], entry["id"])
    assert [item["number"] for item in history["versions"]] == [1, 2, 3]
    assert history["versions"][-1]["restored_from"] == first["id"]
    assert window._people_store.read_map(person["id"], entry["id"]) == sample_record()
    saved_person = window._people_store.get_person(person["id"])
    assert saved_person["id"] == person["id"]
    assert saved_person["maps"][0]["id"] == entry["id"]


def test_opening_historical_version_previews_without_changing_current_payload(window, monkeypatch):
    person = window._people_store.create_person("תצוגת גרסה")
    entry = window._people_store.save_map(person["id"], "מפה", sample_record())
    first = window._people_store.list_map_versions(person["id"], entry["id"])["versions"][0]
    changed = make_record({
        "date_mode": "gregorian", "civil_date": "2024-07-03",
        "clock": "14:00", "gregorian_date": "2024-07-03",
        "hebrew_year": 5784, "hebrew_month": 10, "hebrew_day": 27,
        "phase": "day", "unknown_time": False, "estimated_time": False,
        "city": "תל אביב", "latitude": 32.0853, "longitude": 34.7818,
        "zone": "Asia/Jerusalem",
    }, ui.__version__)
    window._people_store.update_map(person["id"], entry["id"], "מפה", changed)
    original_current = window._people_store.read_map(person["id"], entry["id"])

    def calculate_preview():
        window._active_record = sample_record()
        window._active_chart = object()

    monkeypatch.setattr(window, "_calculate", calculate_preview)

    def open_first_version(dialog):
        table = dialog.findChild(ui.QTableWidget, "mapVersionHistoryTable")
        table.setCurrentCell(0, 0)
        dialog.findChild(ui.QPushButton, "openMapVersionButton").click()
        return ui.QDialog.DialogCode.Accepted

    monkeypatch.setattr(ui.QDialog, "exec", open_first_version)
    window._refresh_people(person["id"])
    window.people_maps.setCurrentCell(0, 0)
    window._show_map_version_history()

    assert window._active_person_id == person["id"]
    assert window._active_map_id == entry["id"]
    assert window.page_stack.currentWidget() is window.chart_page
    assert "גרסה 1" in window.chart_caption.text()
    assert window._people_store.read_map(person["id"], entry["id"]) == original_current
    history = window._people_store.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == 2
    assert history["versions"][-1]["is_current"]
    assert history["versions"][0]["id"] == first["id"]
