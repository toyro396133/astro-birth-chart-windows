import json
import multiprocessing
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import astrochart.people_storage as people_storage

from astrochart.chart_storage import make_record
from astrochart.people_storage import PeopleStore


def sample_record(day="2024-07-01", city="ירושלים", clock="12:30"):
    return make_record({
        "date_mode": "gregorian",
        "civil_date": day,
        "clock": clock,
        "gregorian_date": day,
        "hebrew_year": 5784,
        "hebrew_month": 10,
        "hebrew_day": 25,
        "phase": "day",
        "unknown_time": clock is None,
        "estimated_time": False,
        "city": city,
        "latitude": 31.7683,
        "longitude": 35.2137,
        "zone": "Asia/Jerusalem",
    }, "0.6.2")


def test_empty_people_store_and_stable_ids_allow_identical_names(tmp_path):
    store = PeopleStore(tmp_path)
    assert store.list_people() == []

    first = store.create_person("דוד כהן", "אדם ראשון\nפרטים נוספים")
    second = store.create_person("דוד כהן", "אדם אחר")

    assert first["id"] != second["id"]
    assert store.get_person(first["id"])["name"] == "דוד כהן"
    assert len(store.list_people()) == 2

    renamed = store.update_person(first["id"], "דוד לוי", "פרטים מעודכנים\nשורה שנייה")
    assert renamed["id"] == first["id"]
    assert store.get_person(first["id"])["name"] == "דוד לוי"
    assert "שורה שנייה" in store.get_person(first["id"])["notes"]
    assert store.get_person(second["id"])["name"] == "דוד כהן"


def test_multiple_maps_belong_to_one_person_and_primary_is_unique(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("שרה")
    first = store.save_map(person["id"], "מפת לידה", sample_record())
    second = store.save_map(
        person["id"], "שעת לידה חלופית",
        sample_record("2024-07-02", "חיפה", "13:15"))

    saved_person = store.get_person(person["id"])
    assert [item["id"] for item in saved_person["maps"]] == [
        first["id"], second["id"]]
    assert sum(item["is_primary"] for item in saved_person["maps"]) == 1
    assert next(item for item in saved_person["maps"]
                if item["id"] == first["id"])["is_primary"]
    assert store.read_map(person["id"], first["id"])["input"]["city"] == "ירושלים"
    assert store.read_map(person["id"], second["id"])["input"]["city"] == "חיפה"

    selected = store.set_primary_map(person["id"], second["id"])
    assert selected["is_primary"]
    saved_person = store.get_person(person["id"])
    assert [item["is_primary"] for item in saved_person["maps"]] == [False, True]


def test_map_updates_keep_id_and_primary_flag(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("לאה")
    chart = store.save_map(person["id"], "מפה ראשית", sample_record())
    updated = store.update_map(
        person["id"], chart["id"], "מפה מעודכנת",
        sample_record("2024-07-03", "תל אביב", "14:00"))
    assert updated["id"] == chart["id"]
    assert updated["name"] == "מפה מעודכנת"
    assert updated["is_primary"]
    assert store.read_map(person["id"], chart["id"])["input"]["city"] == "תל אביב"


def test_map_cannot_be_saved_or_read_without_a_valid_person_link(tmp_path):
    store = PeopleStore(tmp_path)
    with pytest.raises(KeyError, match="לבחור אדם"):
        store.save_map("0" * 32, "מפה", sample_record())
    person = store.create_person("רחל")
    with pytest.raises(KeyError, match="משויכת"):
        store.read_map(person["id"], "1" * 32)
    with pytest.raises(ValueError, match="מזהה"):
        store.map_path("../outside", "1" * 32)


def test_corrupt_people_index_is_not_silently_reset_or_overwritten(tmp_path):
    store = PeopleStore(tmp_path)
    store.directory.mkdir(parents=True, exist_ok=True)
    store.index_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="הקובץ המקורי נשמר"):
        store.list_people()
    assert store.index_path.read_text(encoding="utf-8") == "{broken"


def test_people_index_contains_metadata_not_chart_results(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("מיכל")
    chart = store.save_map(person["id"], "מפה", sample_record())
    document = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert document["format"] == "astro-birth-chart-people"
    assert "derived_data" not in document
    assert document["people"][0]["maps"][0]["id"] == chart["id"]
    assert store.map_path(person["id"], chart["id"]).is_file()

def _concurrent_create_person(directory, name, barrier, queue):
    try:
        barrier.wait(timeout=20)
        person = PeopleStore(directory).create_person(name)
        queue.put(("ok", person["id"]))
    except BaseException as exc:
        queue.put(("error", repr(exc)))
        raise


def _concurrent_save_map(directory, person_id, day, city, barrier, queue):
    try:
        barrier.wait(timeout=20)
        entry = PeopleStore(directory).save_map(
            person_id, f"מפה {city}", sample_record(day, city, "12:30"))
        queue.put(("ok", entry["id"]))
    except BaseException as exc:
        queue.put(("error", repr(exc)))
        raise


def _run_two_processes(target, args):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    processes = [
        context.Process(target=target, args=(*args[0], barrier, queue)),
        context.Process(target=target, args=(*args[1], barrier, queue)),
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(45)
    try:
        assert all(not process.is_alive() for process in processes), "worker process timed out"
        assert [process.exitcode for process in processes] == [0, 0]
        results = [queue.get(timeout=5) for _ in processes]
        assert all(result[0] == "ok" for result in results), results
        return [result[1] for result in results]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        queue.close()
        queue.join_thread()


def test_save_map_rolls_back_payload_when_index_commit_fails(tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("אדם לשמירה")
    original_write = store._write

    def fail_index(_document):
        raise OSError("simulated index disk failure")

    monkeypatch.setattr(store, "_write", fail_index)
    with pytest.raises(OSError, match="simulated index"):
        store.save_map(person["id"], "מפה שלא נשמרה", sample_record())

    monkeypatch.setattr(store, "_write", original_write)
    assert store.get_person(person["id"])["maps"] == []
    assert not list(store.maps_path.rglob("*.astrochart.json"))
    assert not store.journal_path.exists()
    assert not list(store.directory.glob(".people-*.tmp"))
    assert not list(store.directory.glob(".people-journal-*.tmp"))


def test_update_map_restores_old_payload_and_metadata_when_index_commit_fails(
        tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("אדם לעדכון")
    original = store.save_map(person["id"], "מפה מקורית", sample_record())
    original_record = store.read_map(person["id"], original["id"])
    original_metadata = store.get_person(person["id"])["maps"][0]
    original_write = store._write

    monkeypatch.setattr(
        store, "_write",
        lambda _document: (_ for _ in ()).throw(OSError("simulated index replace failure")))
    with pytest.raises(OSError, match="simulated index replace"):
        store.update_map(
            person["id"], original["id"], "שם חדש",
            sample_record("2024-07-03", "תל אביב", "14:00"))

    monkeypatch.setattr(store, "_write", original_write)
    assert store.read_map(person["id"], original["id"]) == original_record
    restored = store.get_person(person["id"])["maps"][0]
    assert restored == original_metadata
    assert not store.journal_path.exists()
    assert not list(store.maps_path.rglob(".astrochart-*.tmp"))


def test_save_map_rolls_back_after_real_index_replace_failure(tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("בדיקת replace")
    real_replace = os.replace

    def fail_people_index(source, destination):
        if Path(destination) == store.index_path:
            raise OSError("simulated os.replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(people_storage.os, "replace", fail_people_index)
    with pytest.raises(OSError, match="simulated os.replace"):
        store.save_map(person["id"], "מפה", sample_record())

    monkeypatch.undo()
    assert store.get_person(person["id"])["maps"] == []
    assert not list(store.maps_path.rglob("*.astrochart.json"))
    assert not store.journal_path.exists()
    assert not list(store.directory.glob(".people-*.tmp"))
    assert not list(store.directory.glob(".people-journal-*.tmp"))


def test_durable_journal_recovers_after_interrupted_save(tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("התאוששות")
    monkeypatch.setattr(
        store, "_write",
        lambda _document: (_ for _ in ()).throw(OSError("simulated crash point")))
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)

    with pytest.raises(OSError, match="simulated crash point"):
        store.save_map(person["id"], "מפה בהתאוששות", sample_record())

    assert store.journal_path.is_file()
    assert list(store.maps_path.rglob("*.astrochart.json"))
    monkeypatch.undo()

    assert store.get_person(person["id"])["maps"] == []
    assert not list(store.maps_path.rglob("*.astrochart.json"))
    assert not store.journal_path.exists()
    assert not list(store.directory.glob(".people-*.tmp"))
    assert not list(store.directory.glob(".people-journal-*.tmp"))


def test_missing_people_index_with_saved_maps_enters_recovery_state(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("אינדקס חסר")
    entry = store.save_map(person["id"], "מפה שמורה", sample_record())
    payload = store.map_path(person["id"], entry["id"])
    original_bytes = payload.read_bytes()
    store.index_path.unlink()

    with pytest.raises(ValueError, match="קובץ האנשים חסר"):
        store.list_people()

    assert payload.read_bytes() == original_bytes
    assert payload.is_file()
    assert not store.index_path.exists()


def test_store_rejects_posix_symlinked_maps_directory(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX symlink test; Windows junction coverage is separate")
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("קישור")
    outside = tmp_path / "outside"
    outside.mkdir()
    store.maps_path.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="קישור סמלי"):
        store.save_map(person["id"], "לא לכתוב בחוץ", sample_record())
    assert not list(outside.iterdir())


def test_store_rejects_symlinked_index_file(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX symlink test; Windows reparse coverage is separate")
    store = PeopleStore(tmp_path / "people")
    store.create_person("אינדקס")
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    store.index_path.unlink()
    store.index_path.symlink_to(outside)

    with pytest.raises(ValueError, match="קישור סמלי"):
        store.list_people()
    assert outside.read_text(encoding="utf-8") == "{}"


def test_store_rejects_symlinked_store_root(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX symlink test; Windows reparse coverage is separate")
    real = tmp_path / "real-people"
    real.mkdir()
    linked = tmp_path / "linked-people"
    linked.symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match="קישור סמלי"):
        PeopleStore(linked).list_people()


def test_store_rejects_windows_junction_to_external_maps(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction test")
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("junction")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = store.maps_path
    result = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)],
        capture_output=True, text=True, check=False)
    if result.returncode != 0:
        pytest.skip(f"Windows junction creation unavailable: {result.stderr or result.stdout}")
    try:
        with pytest.raises(ValueError, match="נקודת הפניה|קישור סמלי"):
            store.save_map(person["id"], "לא לכתוב דרך junction", sample_record())
        assert not list(outside.iterdir())
    finally:
        if link.exists():
            os.rmdir(link)


def test_concurrent_process_person_creations_are_not_lost(tmp_path):
    directory = str(tmp_path / "people")
    store = PeopleStore(directory)
    ids = _run_two_processes(
        _concurrent_create_person,
        ((directory, "אדם מקביל א"), (directory, "אדם מקביל ב")),
    )
    people = store.list_people()
    assert len(people) == 2
    assert {person["id"] for person in people} == set(ids)
    assert {person["name"] for person in people} == {"אדם מקביל א", "אדם מקביל ב"}


def test_concurrent_process_map_saves_preserve_both_and_one_primary(tmp_path):
    directory = str(tmp_path / "people")
    store = PeopleStore(directory)
    person = store.create_person("מפות מקבילות")
    ids = _run_two_processes(
        _concurrent_save_map,
        (
            (directory, person["id"], "2024-07-01", "ירושלים"),
            (directory, person["id"], "2024-07-02", "חיפה"),
        ),
    )
    saved = store.get_person(person["id"])
    assert len(saved["maps"]) == 2
    assert {entry["id"] for entry in saved["maps"]} == set(ids)
    assert sum(entry["is_primary"] for entry in saved["maps"]) == 1
    assert all(store.read_map(person["id"], map_id) for map_id in ids)

