from datetime import datetime

import pytest
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import astrochart.ui as ui
from astrochart.chart_storage import make_record
from astrochart.domain import BodyPosition, Chart
from astrochart.people_storage import PeopleStore
from astrochart.timeconv import full_local_day, local_to_utc


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
    win._birth_time_timer.stop()
    win.close()
    app.processEvents()


class FastCalculator:
    """Use the production UI/calculation path and real IANA wall-time conversion.

    Only the slow Skyfield ephemeris lookup is replaced with a deterministic
    chart row; DST validation still uses the production local_to_utc function.
    """
    def __init__(self):
        self.calls = []

    def calculate(self, day, clock, zone, latitude, longitude, unknown_time=False):
        self.calls.append((day, clock, zone, latitude, longitude, unknown_time))
        if unknown_time:
            full_local_day(day, zone)
            chart = Chart([BodyPosition("שמש", 12.0, False)], [],
                          None, None, True, [])
            chart.time_certainty = "unknown"
            return chart
        local_to_utc(datetime.combine(day, clock), zone)
        return Chart([BodyPosition("שמש", 12.0, False)], [],
                     14.0, 23.0, False, [])


def _persisted_bytes(store):
    return {
        str(path.relative_to(store.directory)): path.read_bytes()
        for path in store.directory.rglob("*")
        if path.is_file() and path.name != ".people.lock"
    }


def test_slider_and_time_input_sync_bidirectionally_with_rtl_keyboard(window):
    slider = window.birth_time_slider
    assert slider.minimum() == 0
    assert slider.maximum() == 1439
    assert slider.singleStep() == 1
    assert slider.pageStep() == 15
    assert slider.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert slider.accessibleName() == "מחוון שעת לידה"
    assert slider.accessibleDescription()
    assert slider.focusPolicy() == Qt.FocusPolicy.StrongFocus

    window.hour.setTime(QTime(5, 37))
    assert slider.value() == 5 * 60 + 37

    slider.setValue(13 * 60 + 7)
    assert window.hour.time() == QTime(13, 7)
    assert window._birth_time_recalc_pending

    window._birth_time_timer.stop()
    window._birth_time_recalc_pending = False
    before = slider.value()
    slider.setFocus()
    QTest.keyClick(slider, Qt.Key.Key_PageUp)
    assert slider.value() != before
    assert window.hour.time() == QTime(slider.value() // 60,
                                       slider.value() % 60)
    window._birth_time_timer.stop()
    window._birth_time_recalc_pending = False


def test_slider_live_recalculation_uses_existing_pipeline_without_storage_writes(
        window):
    person = window._people_store.create_person("בדיקת מחוון")
    window._new_chart_for_person(person["id"])
    calculator = FastCalculator()
    window.calc = calculator

    assert window._calculate()
    assert window._active_record["input"]["clock"] == window.hour.time().toString("HH:mm")
    assert len(calculator.calls) == 1

    window.birth_time_slider.setValue(12 * 60 + 31)
    QTest.qWait(420)
    QApplication.processEvents()

    assert len(calculator.calls) == 2
    assert calculator.calls[-1][1].hour == 12
    assert calculator.calls[-1][1].minute == 31
    assert window._active_record["input"]["clock"] == "12:31"
    assert window._active_chart.time_certainty == "known"
    assert "עודכנה" in window.birth_time_status.text()
    assert "נשמר" in window.birth_time_status.text()
    assert window._people_store.get_person(person["id"])["maps"] == []


def test_explicit_save_appends_one_version_and_close_without_save_is_byte_preserving(
        window, monkeypatch):
    store = window._people_store
    person = store.create_person("שמירת התאמת שעה")
    window._new_chart_for_person(person["id"])
    window.calc = FastCalculator()
    monkeypatch.setattr(ui.QInputDialog, "getText",
                        lambda *args: ("מפת בדיקה", True))

    assert window._calculate()
    window._save_chart()
    person_id = window._active_person_id
    map_id = window._active_map_id
    assert person_id == person["id"]
    assert map_id
    initial_history = store.list_map_versions(person_id, map_id)
    assert [version["number"] for version in initial_history["versions"]] == [1]

    version_dir = store._version_directory(person_id, map_id)
    original_snapshots = {
        path.name: path.read_bytes()
        for path in version_dir.glob("*.astrochart.json")
    }
    before_drag = _persisted_bytes(store)

    window.birth_time_slider.setValue(12 * 60 + 31)
    assert _persisted_bytes(store) == before_drag
    assert window._active_person_id == person_id
    assert window._active_map_id == map_id

    # Save flushes the pending in-memory recalculation, then commits one version.
    window._save_chart()
    saved_person = store.get_person(person_id)
    assert window._active_person_id == person_id
    assert window._active_map_id == map_id
    assert [item["id"] for item in saved_person["maps"]] == [map_id]
    assert sum(bool(item["is_primary"]) for item in saved_person["maps"]) == 1

    history = store.list_map_versions(person_id, map_id)
    assert [version["number"] for version in history["versions"]] == [1, 2]
    assert history["current_version_id"] == history["versions"][-1]["id"]
    for name, data in original_snapshots.items():
        assert (version_dir / name).read_bytes() == data

    after_save = _persisted_bytes(store)
    window.birth_time_slider.setValue(12 * 60 + 45)
    QTest.qWait(420)
    QApplication.processEvents()
    assert _persisted_bytes(store) == after_save
    assert window._active_person_id == person_id
    assert window._active_map_id == map_id

    window.close()
    QApplication.processEvents()
    assert _persisted_bytes(store) == after_save


def test_unknown_time_disables_slider_and_never_becomes_exact(window):
    window.calc = FastCalculator()
    window.unknown.setChecked(True)

    assert not window.birth_time_slider.isEnabled()
    assert "לא ידועה" in window.birth_time_value_label.text()
    assert "אינה ידועה" in window.birth_time_status.text()
    assert window._calculate()

    assert window._active_record["input"]["unknown_time"] is True
    assert window._active_record["input"]["clock"] is None
    assert window._active_chart.time_certainty == "unknown"

    window.unknown.setChecked(False)
    assert window.birth_time_slider.isEnabled()


def test_estimated_time_remains_estimated_after_live_slider_adjustment(window):
    window.calc = FastCalculator()
    window.approx_hour.setChecked(True)
    window.birth_time_slider.setValue(14 * 60 + 5)
    window._run_pending_birth_time_calculation()

    assert window._active_record["input"]["estimated_time"] is True
    assert window._active_record["input"]["unknown_time"] is False
    assert window._active_record["input"]["clock"] == "14:05"
    assert window._active_chart.time_certainty == "estimated"
    assert "משוערת" in window.birth_time_value_label.text()
    assert any("משוערת" in warning for warning in window._active_chart.warnings)


@pytest.mark.parametrize(
    ("day", "minutes", "message"),
    [
        (QDate(2024, 3, 10), 2 * 60 + 30, "אינה קיימת"),
        (QDate(2024, 11, 3), 1 * 60 + 30, "כפולה"),
    ],
)
def test_dst_gap_and_fall_back_ambiguity_are_visible_without_shifting_input(
        window, day, minutes, message):
    window.calc = FastCalculator()
    window.tz.setText("America/New_York")
    window.day.setDate(day)
    intended = QTime(minutes // 60, minutes % 60)

    window.birth_time_slider.setValue(minutes)
    window._run_pending_birth_time_calculation()

    assert window.hour.time() == intended
    assert window.day.date() == day
    assert window.tz.text() == "America/New_York"
    assert message in window.birth_time_status.text()
    assert window._active_chart is None
    assert window._active_record is None


def test_date_city_and_timezone_changes_keep_slider_value_and_use_current_context(
        window):
    calculator = FastCalculator()
    window.calc = calculator
    window.birth_time_slider.setValue(12 * 60 + 10)
    assert window._birth_time_recalc_pending

    window.day.setDate(QDate(2024, 11, 4))
    assert not window._birth_time_recalc_pending
    assert not window._birth_time_timer.isActive()
    window.city.setCurrentText("ניו יורק")
    assert window.tz.text() == "America/New_York"
    assert window.birth_time_slider.value() == 12 * 60 + 10
    assert window.hour.time() == QTime(12, 10)

    window.tz.setText("Europe/London")
    window.birth_time_slider.setValue(12 * 60 + 11)
    window._run_pending_birth_time_calculation()

    assert len(calculator.calls) == 1
    day, clock, zone, latitude, longitude, unknown = calculator.calls[0]
    assert day.isoformat() == "2024-11-04"
    assert clock.hour == 12 and clock.minute == 11
    assert zone == "Europe/London"
    assert latitude == pytest.approx(40.7128)
    assert longitude == pytest.approx(-74.0060)
    assert unknown is False


def test_tables_pdf_receives_metadata_when_shared_pdf_exporter_supports_it(
        window, monkeypatch, tmp_path):
    chart = Chart([BodyPosition("שמש", 12.0, False)], [],
                  14.0, 23.0, False, [])
    window._active_chart = chart
    window._active_record = make_record(window._capture_input(), ui.__version__)
    destination = tmp_path / "tables.pdf"
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName",
                        lambda *args: (str(destination), "PDF (*.pdf)"))
    calls = []

    def export_with_metadata(chart_arg, path_arg, *, metadata):
        calls.append((chart_arg, path_arg, metadata))

    monkeypatch.setattr(ui, "export_chart_tables_pdf", export_with_metadata)
    window._export_chart("pdf_tables")

    assert calls == [(chart, destination, window._active_record["input"])]
