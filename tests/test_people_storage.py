import copy
import errno
import json
import multiprocessing
import os
import subprocess
import uuid
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


def _add_large_people_index(store, *, count=340, notes_length=3600):
    """Build a valid index large enough to exercise schema-specific journal limits."""
    document = store._read_unlocked()
    now = people_storage._now()
    notes = "א" * notes_length
    for index in range(count):
        document["people"].append({
            "id": uuid.uuid4().hex,
            "name": f"אדם לבדיקת גודל {index}",
            "notes": notes,
            "created_at": now,
            "updated_at": now,
            "maps": [],
        })
    store._write(document)
    assert store.index_path.stat().st_size < people_storage.MAX_INDEX_BYTES
    return document


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




def _concurrent_update_map(directory, person_id, map_id, day, city, barrier, queue):
    try:
        barrier.wait(timeout=20)
        updated = PeopleStore(directory).update_map(
            person_id, map_id, f"מפה {city}", sample_record(day, city, "12:30"))
        queue.put(("ok", updated["id"]))
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

    if os.name == "nt":
        real_replace = store._move_file_ex_w

        def fail_people_index(source, destination, flags):
            if Path(destination) == store.index_path:
                raise OSError("simulated MoveFileExW failure")
            return real_replace(source, destination, flags)

        monkeypatch.setattr(store, "_move_file_ex_w", fail_people_index)
        failure_message = "simulated MoveFileExW"
    else:
        real_replace = os.replace

        def fail_people_index(source, destination):
            if Path(destination) == store.index_path:
                raise OSError("simulated os.replace failure")
            return real_replace(source, destination)

        monkeypatch.setattr(people_storage.os, "replace", fail_people_index)
        failure_message = "simulated os.replace"

    with pytest.raises(OSError, match=failure_message):
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

def test_store_rejects_symlinked_person_directory(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX symlink test; Windows junction coverage is separate")
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("תיק אדם")
    outside = tmp_path / "outside-person"
    outside.mkdir()
    store.maps_path.mkdir()
    (store.maps_path / person["id"]).symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="קישור סמלי"):
        store.save_map(person["id"], "לא לכתוב מחוץ למאגר", sample_record())
    assert not list(outside.iterdir())


def test_store_rejects_symlinked_map_payload_on_read(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX symlink test; Windows reparse coverage is separate")
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("קובץ מפה")
    entry = store.save_map(person["id"], "מפה", sample_record())
    target = store.map_path(person["id"], entry["id"])
    original = target.read_bytes()
    outside = tmp_path / "outside-map.json"
    outside.write_bytes(original)
    target.unlink()
    target.symlink_to(outside)

    with pytest.raises(ValueError, match="קישור סמלי"):
        store.read_map(person["id"], entry["id"])
    assert outside.read_bytes() == original



@pytest.mark.skipif(os.name == "nt", reason="POSIX directory fsync behavior")
def test_posix_directory_fsync_propagates_eio(tmp_path, monkeypatch):
    def fail_fsync(_descriptor):
        raise OSError(errno.EIO, "simulated directory fsync EIO")

    monkeypatch.setattr(people_storage.os, "fsync", fail_fsync)
    with pytest.raises(OSError) as error:
        PeopleStore._fsync_directory(tmp_path)
    assert error.value.errno == errno.EIO


def test_windows_replace_uses_movefileex_write_through_flags(tmp_path, monkeypatch):
    store = PeopleStore(tmp_path / "people")
    source = tmp_path / "staged.tmp"
    destination = tmp_path / "target.json"
    source.write_text("staged", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        store, "_move_file_ex_w",
        lambda src, dst, flags: calls.append((str(src), str(dst), flags)))
    store._replace_file(source, destination, platform="nt")

    assert calls == [(
        str(source), str(destination),
        PeopleStore.MOVEFILE_REPLACE_EXISTING | PeopleStore.MOVEFILE_WRITE_THROUGH,
    )]

    def fail_move(_src, _dst, _flags):
        raise OSError(5, "simulated MoveFileExW failure")

    monkeypatch.setattr(store, "_move_file_ex_w", fail_move)
    with pytest.raises(OSError, match="MoveFileExW"):
        store._replace_file(source, destination, platform="nt")


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory fsync failure injection; Windows MoveFileExW is tested separately")
@pytest.mark.parametrize("phase", ["journal", "payload", "index"])
def test_save_map_directory_fsync_eio_never_reports_success(tmp_path, monkeypatch, phase):
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("בדיקת EIO בשמירה")
    map_directory = store.maps_path / person["id"]
    store._ensure_directory(map_directory)
    real_fsync = store._fsync_directory
    root_calls = 0

    def injected(path):
        nonlocal root_calls
        path = Path(path)
        if path == store.directory:
            root_calls += 1
            if phase == "journal" and root_calls == 1:
                raise OSError(errno.EIO, "directory fsync EIO after journal replace")
            if phase == "index" and root_calls == 2:
                raise OSError(errno.EIO, "directory fsync EIO after index replace")
        if phase == "payload" and path == map_directory:
            raise OSError(errno.EIO, "directory fsync EIO after payload replace")
        return real_fsync(path)

    monkeypatch.setattr(store, "_fsync_directory", injected)
    with pytest.raises(OSError, match="directory fsync EIO"):
        store.save_map(person["id"], "מפה", sample_record())

    monkeypatch.undo()
    recovered = PeopleStore(tmp_path / "people")
    saved_person = recovered.get_person(person["id"])
    if phase == "index":
        assert len(saved_person["maps"]) == 1
        entry = saved_person["maps"][0]
        assert recovered.read_map(person["id"], entry["id"]) == sample_record()
    else:
        assert saved_person["maps"] == []
        assert not list(recovered.maps_path.rglob("*.astrochart.json"))
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.glob(".people-*.tmp"))
    assert not list(recovered.directory.glob(".people-journal-*.tmp"))
    assert not list(recovered.maps_path.rglob(".astrochart-*.tmp"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory fsync failure injection; Windows MoveFileExW is tested separately")
@pytest.mark.parametrize("phase", ["journal", "payload", "index"])
def test_update_map_directory_fsync_eio_keeps_payload_and_metadata_consistent(
        tmp_path, monkeypatch, phase):
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("בדיקת EIO בעדכון")
    original = store.save_map(person["id"], "מפה מקורית", sample_record())
    original_record = store.read_map(person["id"], original["id"])
    original_metadata = store.get_person(person["id"])["maps"][0]
    map_directory = store.maps_path / person["id"]
    real_fsync = store._fsync_directory
    root_calls = 0

    def injected(path):
        nonlocal root_calls
        path = Path(path)
        if path == store.directory:
            root_calls += 1
            if phase == "journal" and root_calls == 1:
                raise OSError(errno.EIO, "directory fsync EIO after journal replace")
            if phase == "index" and root_calls == 2:
                raise OSError(errno.EIO, "directory fsync EIO after index replace")
        if phase == "payload" and path == map_directory:
            raise OSError(errno.EIO, "directory fsync EIO after payload replace")
        return real_fsync(path)

    monkeypatch.setattr(store, "_fsync_directory", injected)
    with pytest.raises(OSError, match="directory fsync EIO"):
        store.update_map(
            person["id"], original["id"], "שם חדש",
            sample_record("2024-07-03", "תל אביב", "14:00"))

    monkeypatch.undo()
    recovered = PeopleStore(tmp_path / "people")
    current_record = recovered.read_map(person["id"], original["id"])
    current_metadata = recovered.get_person(person["id"])["maps"][0]
    if phase == "index":
        assert current_record == sample_record("2024-07-03", "תל אביב", "14:00")
        assert current_metadata["name"] == "שם חדש"
    else:
        assert current_record == original_record
        assert current_metadata == original_metadata
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.glob(".people-*.tmp"))
    assert not list(recovered.directory.glob(".people-journal-*.tmp"))
    assert not list(recovered.maps_path.rglob(".astrochart-*.tmp"))


def test_interrupted_update_recovers_old_payload_and_metadata_in_new_store(
        tmp_path, monkeypatch):
    store = PeopleStore(tmp_path / "people")
    person = store.create_person("עדכון שנקטע")
    original = store.save_map(person["id"], "מפה מקורית", sample_record())
    old_record = store.read_map(person["id"], original["id"])
    old_metadata = store.get_person(person["id"])["maps"][0]

    monkeypatch.setattr(
        store, "_write",
        lambda _document: (_ for _ in ()).throw(OSError("simulated interrupted index commit")))
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)

    with pytest.raises(OSError, match="interrupted index commit"):
        store.update_map(
            person["id"], original["id"], "מפה חדשה",
            sample_record("2024-07-03", "תל אביב", "14:00"))

    assert store.journal_path.is_file()
    assert store.read_map(person["id"], original["id"])["input"]["city"] == "תל אביב"
    monkeypatch.undo()

    recovered = PeopleStore(tmp_path / "people")
    assert recovered.read_map(person["id"], original["id"]) == old_record
    assert recovered.get_person(person["id"])["maps"][0] == old_metadata
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.glob(".people-*.tmp"))
    assert not list(recovered.directory.glob(".people-journal-*.tmp"))
    assert not list(recovered.maps_path.rglob(".astrochart-*.tmp"))


def test_first_map_save_creates_immutable_initial_version(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("גרסה ראשונה")
    entry = store.save_map(person["id"], "מפה", sample_record())
    history = store.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == 1
    first = history["versions"][0]
    assert first["number"] == 1 and first["is_current"]
    assert first["restored_from"] is None
    assert history["current_version_id"] == first["id"]
    snapshot = store._version_snapshot_path(person["id"], entry["id"], first["id"])
    assert snapshot.is_file()
    assert store.read_map_version(person["id"], entry["id"], first["id"]) == sample_record()
    assert store.get_person(person["id"])["maps"][0]["id"] == entry["id"]


def test_update_appends_immutable_version_and_identical_save_does_not_add_noise(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("גרסאות עדכון")
    entry = store.save_map(person["id"], "מפה", sample_record())
    first = store.list_map_versions(person["id"], entry["id"])["versions"][0]
    first_path = store._version_snapshot_path(person["id"], entry["id"], first["id"])
    first_bytes = first_path.read_bytes()
    changed = sample_record("2024-07-03", "תל אביב", "14:00")
    store.update_map(person["id"], entry["id"], "מפה", changed)
    history = store.list_map_versions(person["id"], entry["id"])
    assert [item["number"] for item in history["versions"]] == [1, 2]
    assert history["versions"][-1]["is_current"]
    assert first_path.read_bytes() == first_bytes
    assert store.read_map_version(person["id"], entry["id"], first["id"]) == sample_record()
    store.update_map(person["id"], entry["id"], "מפה", changed)
    assert len(store.list_map_versions(person["id"], entry["id"])["versions"]) == 2
    assert store.read_map(person["id"], entry["id"]) == changed


def test_restore_old_version_appends_new_version_without_mutating_history(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("שחזור")
    entry = store.save_map(person["id"], "מפה", sample_record())
    first = store.list_map_versions(person["id"], entry["id"])["versions"][0]
    first_path = store._version_snapshot_path(person["id"], entry["id"], first["id"])
    first_bytes = first_path.read_bytes()
    changed = sample_record("2024-07-03", "תל אביב", "14:00")
    store.update_map(person["id"], entry["id"], "מפה", changed)
    second = store.list_map_versions(person["id"], entry["id"])["versions"][1]
    second_path = store._version_snapshot_path(person["id"], entry["id"], second["id"])
    second_bytes = second_path.read_bytes()
    restored = store.restore_map_version(person["id"], entry["id"], first["id"])
    history = store.list_map_versions(person["id"], entry["id"])
    assert restored["id"] == entry["id"]
    assert [item["number"] for item in history["versions"]] == [1, 2, 3]
    third = history["versions"][-1]
    assert third["is_current"] and third["restored_from"] == first["id"]
    assert store.read_map(person["id"], entry["id"]) == sample_record()
    assert store.read_map_version(person["id"], entry["id"], first["id"]) == sample_record()
    assert first_path.read_bytes() == first_bytes and second_path.read_bytes() == second_bytes
    saved_person = store.get_person(person["id"])
    assert saved_person["id"] == person["id"]
    assert [item["id"] for item in saved_person["maps"]] == [entry["id"]]
    assert sum(item["is_primary"] for item in saved_person["maps"]) == 1



def test_restoring_current_version_is_a_byte_preserving_noop(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("שחזור הגרסה הנוכחית")
    entry = store.save_map(person["id"], "מפה", sample_record())
    history = store.list_map_versions(person["id"], entry["id"])
    current_id = history["current_version_id"]
    payload_before = store.map_path(person["id"], entry["id"]).read_bytes()
    manifest_before = store._version_manifest_path(person["id"], entry["id"]).read_bytes()
    index_before = store.index_path.read_bytes()
    snapshot_before = store._version_snapshot_path(person["id"], entry["id"], current_id).read_bytes()

    restored = store.restore_map_version(person["id"], entry["id"], current_id)

    assert restored["id"] == entry["id"]
    assert store.map_path(person["id"], entry["id"]).read_bytes() == payload_before
    assert store._version_manifest_path(person["id"], entry["id"]).read_bytes() == manifest_before
    assert store.index_path.read_bytes() == index_before
    assert store._version_snapshot_path(person["id"], entry["id"], current_id).read_bytes() == snapshot_before

def test_legacy_map_is_lazily_migrated_as_version_one_without_payload_change(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("מפה ישנה")
    entry = store.save_map(person["id"], "מפה ותיקה", sample_record())
    original_payload = store.map_path(person["id"], entry["id"]).read_bytes()
    store._version_manifest_path(person["id"], entry["id"]).unlink()
    version_directory = store._version_directory(person["id"], entry["id"])
    if version_directory.exists():
        for snapshot in version_directory.iterdir():
            snapshot.unlink()
        version_directory.rmdir()
    assert store.read_map(person["id"], entry["id"]) == sample_record()
    history = store.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == 1 and history["versions"][0]["number"] == 1
    assert store.map_path(person["id"], entry["id"]).read_bytes() == original_payload
    assert store.get_person(person["id"])["maps"][0]["id"] == entry["id"]


def test_corrupt_or_missing_version_metadata_fails_closed_without_overwrite(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("היסטוריה פגומה")
    entry = store.save_map(person["id"], "מפה", sample_record())
    payload_path = store.map_path(person["id"], entry["id"])
    original_payload = payload_path.read_bytes()
    manifest_path = store._version_manifest_path(person["id"], entry["id"])
    original_manifest = manifest_path.read_bytes()
    version_directory = store._version_directory(person["id"], entry["id"])
    original_snapshots = {
        path: path.read_bytes() for path in version_directory.glob("*.astrochart.json")
    }

    manifest_path.write_bytes(b"{broken")
    with pytest.raises(ValueError, match="היסטוריית הגרסאות"):
        store.list_map_versions(person["id"], entry["id"])
    assert manifest_path.read_bytes() == b"{broken"
    assert payload_path.read_bytes() == original_payload
    assert {path: path.read_bytes() for path in original_snapshots} == original_snapshots

    manifest_path.write_bytes(original_manifest)
    first = store.list_map_versions(person["id"], entry["id"])["versions"][0]
    store.update_map(
        person["id"], entry["id"], "מפה מעודכנת",
        sample_record("2024-07-02", "חיפה", "13:15"))
    history = store.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == 2
    missing_snapshot = store._version_snapshot_path(
        person["id"], entry["id"], first["id"])
    missing_snapshot.unlink()

    payload_before = payload_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    remaining_snapshots = {
        path: path.read_bytes() for path in version_directory.glob("*.astrochart.json")
    }
    with pytest.raises(ValueError, match="חסרים"):
        store.list_map_versions(person["id"], entry["id"])

    assert payload_path.read_bytes() == payload_before
    assert manifest_path.read_bytes() == manifest_before
    assert {path: path.read_bytes() for path in remaining_snapshots} == remaining_snapshots
    assert not missing_snapshot.exists()


@pytest.mark.parametrize("operation", ["save", "update", "restore"])
@pytest.mark.parametrize("phase", ["snapshot", "payload", "manifest", "index"])
def test_version_transaction_failure_recovers_consistently(tmp_path, monkeypatch, operation, phase):
    store = PeopleStore(tmp_path)
    person = store.create_person(f"כשל {operation} {phase}")
    entry = None
    selected_version_id = None
    original_record = sample_record()
    original_metadata = None
    original_manifest_bytes = None
    original_snapshot_bytes = {}
    if operation != "save":
        entry = store.save_map(person["id"], "מפה מקורית", original_record)
        first_history = store.list_map_versions(person["id"], entry["id"])
        if operation == "restore":
            selected_version_id = first_history["versions"][0]["id"]
            original_record = sample_record("2024-07-03", "תל אביב", "14:00")
            store.update_map(person["id"], entry["id"], "מפה מקורית", original_record)
            store.list_map_versions(person["id"], entry["id"])
        original_metadata = store.get_person(person["id"])["maps"][0]
        manifest_path = store._version_manifest_path(person["id"], entry["id"])
        original_manifest_bytes = manifest_path.read_bytes()
        version_directory = store._version_directory(person["id"], entry["id"])
        original_snapshot_bytes = {
            path.name: path.read_bytes()
            for path in version_directory.glob("*.astrochart.json")
        }
    new_record = (
        sample_record() if operation == "restore"
        else sample_record("2024-07-03", "תל אביב", "14:00")
    )
    real_snapshot = store._write_version_snapshot
    real_save = store._save_record
    real_manifest = store._write_version_manifest
    real_write = store._write
    person_directory = store.maps_path / person["id"]
    injected = {"done": False}

    def fail_after_snapshot(*args, **kwargs):
        result = real_snapshot(*args, **kwargs)
        if phase == "snapshot" and not injected["done"]:
            injected["done"] = True
            raise OSError("injected after snapshot")
        return result

    def fail_after_payload(path, record):
        result = real_save(path, record)
        is_live_payload = (
            path.parent == person_directory and path.name.endswith(".astrochart.json")
        )
        if phase == "payload" and is_live_payload and not injected["done"]:
            injected["done"] = True
            raise OSError("injected after payload")
        return result

    def fail_after_manifest(pid, mid, manifest):
        result = real_manifest(pid, mid, manifest)
        if phase == "manifest" and not injected["done"]:
            injected["done"] = True
            raise OSError("injected after manifest")
        return result

    def fail_after_index(document):
        result = real_write(document)
        if phase == "index" and not injected["done"]:
            injected["done"] = True
            raise OSError("injected after index")
        return result

    if phase == "snapshot":
        monkeypatch.setattr(store, "_write_version_snapshot", fail_after_snapshot)
    elif phase == "payload":
        monkeypatch.setattr(store, "_save_record", fail_after_payload)
    elif phase == "manifest":
        monkeypatch.setattr(store, "_write_version_manifest", fail_after_manifest)
    else:
        monkeypatch.setattr(store, "_write", fail_after_index)
    # Model a process interruption: the failing process cannot run its
    # best-effort recovery; a fresh PeopleStore must reconcile the journal.
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)

    with pytest.raises(OSError, match="injected after"):
        if operation == "save":
            store.save_map(person["id"], "מפה חדשה", new_record)
        elif operation == "update":
            store.update_map(person["id"], entry["id"], "מפה מעודכנת", new_record)
        else:
            store.restore_map_version(person["id"], entry["id"], selected_version_id)
    assert store.journal_path.is_file()

    monkeypatch.undo()
    recovered = PeopleStore(tmp_path)
    stored_person = recovered.get_person(person["id"])
    if phase == "index":
        assert stored_person is not None
        assert len(stored_person["maps"]) == 1
        map_id = stored_person["maps"][0]["id"] if operation == "save" else entry["id"]
        assert recovered.read_map(person["id"], map_id) == new_record
        history = recovered.list_map_versions(person["id"], map_id)
        expected_versions = {"save": 1, "update": 2, "restore": 3}[operation]
        assert len(history["versions"]) == expected_versions
        assert history["versions"][-1]["is_current"]
        assert stored_person["id"] == person["id"]
        assert stored_person["maps"][0]["id"] == map_id
        if operation == "restore":
            assert history["versions"][-1]["restored_from"] == selected_version_id
            restored_metadata = stored_person["maps"][0]
            assert restored_metadata["civil_date"] == new_record["input"]["civil_date"]
            assert restored_metadata["city"] == new_record["input"]["city"]
            assert restored_metadata["clock"] == new_record["input"]["clock"]
            assert restored_metadata["unknown_time"] == new_record["input"]["unknown_time"]
            assert restored_metadata["is_primary"] == original_metadata["is_primary"]
        assert sum(item["is_primary"] for item in stored_person["maps"]) == 1
    elif operation == "save":
        assert stored_person["maps"] == []
        assert not list(recovered.maps_path.rglob("*.astrochart.json"))
        assert not list(recovered.maps_path.rglob("*.versions.json"))
        assert not list(recovered.maps_path.rglob("*.versions"))
    else:
        assert recovered.read_map(person["id"], entry["id"]) == original_record
        assert stored_person["id"] == person["id"]
        assert stored_person["maps"][0] == original_metadata
        assert recovered._version_manifest_path(person["id"], entry["id"]).read_bytes() == original_manifest_bytes
        history = recovered.list_map_versions(person["id"], entry["id"])
        expected_versions = 1 if operation == "update" else 2
        assert len(history["versions"]) == expected_versions
        assert history["current_version_id"] == json.loads(original_manifest_bytes)["current_version_id"]
    if operation != "save":
        version_directory = recovered._version_directory(person["id"], entry["id"])
        for filename, content in original_snapshot_bytes.items():
            assert (version_directory / filename).read_bytes() == content
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.rglob(".people-*.tmp"))
    assert not list(recovered.directory.rglob(".people-journal-*.tmp"))
    assert not list(recovered.maps_path.rglob(".astrochart-*.tmp"))


def test_large_schema2_journal_recovers_after_interruption_in_fresh_store(tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("יומן גרסאות גדול")
    entry = store.save_map(person["id"], "מפה", sample_record())
    store.list_map_versions(person["id"], entry["id"])
    original_record = store.read_map(person["id"], entry["id"])
    original_manifest = store._version_manifest_path(person["id"], entry["id"]).read_bytes()
    _add_large_people_index(store)
    real_atomic = store._atomic_write_text
    observed = {}

    def interrupt_after_large_journal(path, payload, prefix):
        if path == store.journal_path:
            size = len(payload.encode("utf-8"))
            observed["size"] = size
            assert people_storage.MAX_JOURNAL_SCHEMA_1_BYTES < size
            assert size <= people_storage.MAX_JOURNAL_SCHEMA_2_BYTES
            result = real_atomic(path, payload, prefix)
            raise OSError("interrupted after large schema-2 journal")
        return real_atomic(path, payload, prefix)

    monkeypatch.setattr(store, "_atomic_write_text", interrupt_after_large_journal)
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)
    with pytest.raises(OSError, match="large schema-2 journal"):
        store.update_map(
            person["id"], entry["id"], "גרסה חדשה",
            sample_record("2024-07-03", "תל אביב", "14:00"))
    assert observed["size"] > people_storage.MAX_JOURNAL_SCHEMA_1_BYTES
    assert store.journal_path.is_file()
    monkeypatch.undo()

    recovered = PeopleStore(tmp_path)
    assert recovered.read_map(person["id"], entry["id"]) == original_record
    assert recovered._version_manifest_path(person["id"], entry["id"]).read_bytes() == original_manifest
    history = recovered.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == 1 and history["versions"][0]["is_current"]
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.rglob(".people-*.tmp"))
    assert not list(recovered.directory.rglob(".people-journal-*.tmp"))
    assert not list(recovered.maps_path.rglob(".astrochart-*.tmp"))


@pytest.mark.parametrize("bad_schema_version", [
    pytest.param(2.0, id="float-two"),
    pytest.param(True, id="boolean"),
    pytest.param("2", id="string"),
    pytest.param(None, id="null"),
    pytest.param(3, id="unsupported-integer"),
])
def test_schema2_journal_rejects_non_integer_or_unsupported_version_without_mutation(
        tmp_path, monkeypatch, bad_schema_version):
    store = PeopleStore(tmp_path)
    person = store.create_person("יומן גרסאות עם schema פגום")
    entry = store.save_map(person["id"], "מפה", sample_record())
    store.list_map_versions(person["id"], entry["id"])

    real_atomic = store._atomic_write_text

    def interrupt_after_durable_journal(path, payload, prefix):
        result = real_atomic(path, payload, prefix)
        if path == store.journal_path:
            raise OSError("simulated interruption after valid schema-2 journal")
        return result

    monkeypatch.setattr(store, "_atomic_write_text", interrupt_after_durable_journal)
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)
    with pytest.raises(OSError, match="valid schema-2 journal"):
        store.update_map(
            person["id"], entry["id"], "מפה חדשה",
            sample_record("2024-07-03", "חיפה", "14:00"))
    monkeypatch.undo()

    valid_journal = json.loads(store.journal_path.read_text(encoding="utf-8"))
    assert type(valid_journal["schema_version"]) is int
    assert valid_journal["schema_version"] == store.JOURNAL_SCHEMA
    valid_journal["schema_version"] = bad_schema_version
    store.journal_path.write_text(
        json.dumps(valid_journal, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    payload_path = store.map_path(person["id"], entry["id"])
    manifest_path = store._version_manifest_path(person["id"], entry["id"])
    version_directory = store._version_directory(person["id"], entry["id"])
    preserved_paths = [
        store.journal_path, store.index_path, payload_path, manifest_path,
        *version_directory.glob("*.astrochart.json"),
    ]
    preserved_bytes = {path: path.read_bytes() for path in preserved_paths}
    malformed_journal = json.loads(store.journal_path.read_text(encoding="utf-8"))

    fresh = PeopleStore(tmp_path)
    with pytest.raises(ValueError, match="גרסת יומן"):
        fresh._recover_version_transaction(malformed_journal)
    with pytest.raises(ValueError, match="גרסת יומן"):
        fresh.list_people()

    assert {path: path.read_bytes() for path in preserved_paths} == preserved_bytes
    assert fresh.journal_path.is_file()


def test_legacy_schema1_journal_keeps_original_size_limit(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("יומן ישן מוגבל")
    entry = store.save_map(person["id"], "מפה", sample_record())
    large_index = _add_large_people_index(store)
    journal = {
        "format": store.JOURNAL_FORMAT,
        "schema_version": 1,
        "person_id": person["id"],
        "map_id": entry["id"],
        "old_index_exists": True,
        "old_index": large_index,
        "new_index": large_index,
        "old_record": sample_record(),
        "new_record": sample_record(),
    }
    payload = json.dumps(journal, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    size = len(payload.encode("utf-8"))
    assert people_storage.MAX_JOURNAL_SCHEMA_1_BYTES < size
    assert size <= people_storage.MAX_JOURNAL_SCHEMA_2_BYTES
    before_index = store.index_path.read_bytes()
    store.journal_path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="יומן ההתאוששות גדול מדי"):
        store.list_people()
    assert store.index_path.read_bytes() == before_index
    assert store.journal_path.read_text(encoding="utf-8") == payload

def test_valid_schema1_journal_rolls_back_interrupted_legacy_update_in_fresh_store(
        tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("התאוששות יומן schema 1")
    original_record = sample_record()
    entry = store.save_map(person["id"], "מפה ותיקה", original_record)
    payload_path = store.map_path(person["id"], entry["id"])
    original_payload = payload_path.read_bytes()
    old_index_exists, old_index = store._read_index_document()
    old_index_bytes = store.index_path.read_bytes()

    # Simulate a map written by an older application build: no version
    # manifest or snapshots exist, so the next transaction uses journal v1.
    manifest_path = store._version_manifest_path(person["id"], entry["id"])
    version_directory = store._version_directory(person["id"], entry["id"])
    manifest_path.unlink()
    for snapshot in version_directory.iterdir():
        snapshot.unlink()
    version_directory.rmdir()

    new_record = sample_record("2024-07-03", "חיפה", "14:00")
    new_index = copy.deepcopy(old_index)
    new_person = next(item for item in new_index["people"] if item["id"] == person["id"])
    new_entry = next(item for item in new_person["maps"] if item["id"] == entry["id"])
    updated_at = people_storage._now()
    new_entry.update(store._map_metadata(
        new_entry["name"], new_record, entry["id"], new_entry["created_at"],
        updated_at, new_entry["is_primary"]))
    new_person["updated_at"] = updated_at

    monkeypatch.setattr(
        store, "_write",
        lambda _document: (_ for _ in ()).throw(
            OSError("simulated legacy index commit interruption")))
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)
    with pytest.raises(OSError, match="legacy index commit interruption"):
        store._commit_map_transaction(
            person_id=person["id"], map_id=entry["id"],
            old_index_exists=old_index_exists, old_index=old_index,
            new_index=new_index, old_record=original_record, new_record=new_record,
        )

    journal = json.loads(store.journal_path.read_text(encoding="utf-8"))
    assert journal["schema_version"] == 1
    assert store.journal_path.stat().st_size <= people_storage.MAX_JOURNAL_SCHEMA_1_BYTES
    assert payload_path.read_bytes() != original_payload
    assert store.index_path.read_bytes() == old_index_bytes
    monkeypatch.undo()

    recovered = PeopleStore(tmp_path)
    recovered.list_people()
    assert recovered.index_path.read_bytes() == old_index_bytes
    assert recovered.map_path(person["id"], entry["id"]).read_bytes() == original_payload
    assert recovered.read_map(person["id"], entry["id"]) == original_record
    assert not recovered.journal_path.exists()
    assert not manifest_path.exists()
    assert not version_directory.exists()
    assert not list(recovered.directory.glob(".people-*.tmp"))
    assert not list(recovered.directory.glob(".people-journal-*.tmp"))


def test_interrupted_version_update_recovers_from_journal_in_fresh_store(tmp_path, monkeypatch):
    store = PeopleStore(tmp_path)
    person = store.create_person("עדכון גרסה שנקטע")
    entry = store.save_map(person["id"], "מפה מקורית", sample_record())
    original_record = store.read_map(person["id"], entry["id"])
    original_history = store.list_map_versions(person["id"], entry["id"])
    original_manifest = store._version_manifest_path(person["id"], entry["id"]).read_bytes()
    monkeypatch.setattr(
        store, "_write",
        lambda _document: (_ for _ in ()).throw(OSError("simulated crash before index commit")))
    monkeypatch.setattr(store, "_recover_transaction", lambda: None)
    with pytest.raises(OSError, match="simulated crash"):
        store.update_map(
            person["id"], entry["id"], "גרסה חדשה",
            sample_record("2024-07-03", "תל אביב", "14:00"))
    assert store.journal_path.is_file()
    monkeypatch.undo()
    recovered = PeopleStore(tmp_path)
    assert recovered.read_map(person["id"], entry["id"]) == original_record
    assert recovered._version_manifest_path(person["id"], entry["id"]).read_bytes() == original_manifest
    history = recovered.list_map_versions(person["id"], entry["id"])
    assert len(history["versions"]) == len(original_history["versions"])
    assert history["versions"][-1]["is_current"]
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.rglob(".astrochart-*.tmp"))


def test_concurrent_updates_to_same_map_append_serial_versions(tmp_path):
    directory = str(tmp_path / "people")
    store = PeopleStore(directory)
    person = store.create_person("עדכונים מקבילים")
    entry = store.save_map(person["id"], "מפה", sample_record())
    ids = _run_two_processes(
        _concurrent_update_map,
        (
            (directory, person["id"], entry["id"], "2024-07-03", "תל אביב"),
            (directory, person["id"], entry["id"], "2024-07-04", "חיפה"),
        ),
    )
    history = store.list_map_versions(person["id"], entry["id"])
    assert [item["number"] for item in history["versions"]] == [1, 2, 3]
    assert history["versions"][-1]["is_current"]
    assert len({item["id"] for item in history["versions"]}) == 3
    assert store.read_map(person["id"], entry["id"]) == store.read_map_version(
        person["id"], entry["id"], history["current_version_id"])


def test_name_only_edit_updates_metadata_without_creating_chart_version(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("שינוי שם מפה")
    entry = store.save_map(person["id"], "שם ישן", sample_record())
    before = store.list_map_versions(person["id"], entry["id"])
    updated = store.update_map(person["id"], entry["id"], "שם חדש", sample_record())
    after = store.list_map_versions(person["id"], entry["id"])
    assert updated["name"] == "שם חדש"
    assert len(after["versions"]) == len(before["versions"]) == 1
    assert after["current_version_id"] == before["current_version_id"]


def test_legacy_metadata_only_update_keeps_original_payload_bytes(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("עדכון מפה ותיקה")
    entry = store.save_map(person["id"], "שם ישן", sample_record())
    payload_path = store.map_path(person["id"], entry["id"])
    original = payload_path.read_bytes()
    store._version_manifest_path(person["id"], entry["id"]).unlink()
    version_directory = store._version_directory(person["id"], entry["id"])
    for snapshot in version_directory.iterdir():
        snapshot.unlink()
    version_directory.rmdir()

    updated = store.update_map(person["id"], entry["id"], "שם חדש", sample_record())
    assert updated["name"] == "שם חדש"
    assert payload_path.read_bytes() == original
    assert len(store.list_map_versions(person["id"], entry["id"])["versions"]) == 1


def test_missing_manifest_with_orphan_snapshots_fails_closed(tmp_path):
    store = PeopleStore(tmp_path)
    person = store.create_person("snapshot ללא manifest")
    entry = store.save_map(person["id"], "מפה", sample_record())
    version = store.list_map_versions(person["id"], entry["id"])["versions"][0]
    snapshot = store._version_snapshot_path(person["id"], entry["id"], version["id"])
    original = snapshot.read_bytes()
    store._version_manifest_path(person["id"], entry["id"]).unlink()

    with pytest.raises(ValueError, match="snapshots ללא אינדקס"):
        store.list_map_versions(person["id"], entry["id"])
    assert snapshot.read_bytes() == original


@pytest.mark.parametrize("corrupt_orphan", [False, True])
def test_manifest_with_orphan_snapshot_fails_closed_and_preserves_files(
        tmp_path, corrupt_orphan):
    store = PeopleStore(tmp_path)
    person = store.create_person("snapshot יתום עם manifest")
    entry = store.save_map(person["id"], "מפה", sample_record())
    payload_path = store.map_path(person["id"], entry["id"])
    payload_bytes = payload_path.read_bytes()
    history = store.list_map_versions(person["id"], entry["id"])
    first = history["versions"][0]
    snapshot_path = store._version_snapshot_path(person["id"], entry["id"], first["id"])
    snapshot_bytes = snapshot_path.read_bytes()
    manifest_path = store._version_manifest_path(person["id"], entry["id"])
    manifest_bytes = manifest_path.read_bytes()
    orphan_id = "f" * 32
    if orphan_id == first["id"]:
        orphan_id = "e" * 32
    orphan_path = store._version_snapshot_path(person["id"], entry["id"], orphan_id)
    if corrupt_orphan:
        orphan_path.write_bytes(b"{broken orphan snapshot")
    else:
        store._save_record(orphan_path, sample_record("2024-07-03", "תל אביב", "14:00"))
    orphan_bytes = orphan_path.read_bytes()

    with pytest.raises(ValueError, match="יתומים"):
        store.list_map_versions(person["id"], entry["id"])

    assert payload_path.read_bytes() == payload_bytes
    assert manifest_path.read_bytes() == manifest_bytes
    assert snapshot_path.read_bytes() == snapshot_bytes
    assert orphan_path.read_bytes() == orphan_bytes


@pytest.mark.parametrize("operation", ["save", "update"])
def test_interrupted_durable_version_journal_recovers_before_payload_change(
        tmp_path, monkeypatch, operation):
    store = PeopleStore(tmp_path)
    person = store.create_person(f"יומן שנקטע {operation}")
    entry = store.save_map(person["id"], "מפה", sample_record()) if operation == "update" else None
    if entry:
        original = store.read_map(person["id"], entry["id"])
        store.list_map_versions(person["id"], entry["id"])
    real_atomic = store._atomic_write_text

    def interrupt_after_journal(path, payload, prefix):
        result = real_atomic(path, payload, prefix)
        if path == store.journal_path:
            raise OSError("interrupted after durable journal")
        return result

    monkeypatch.setattr(store, "_atomic_write_text", interrupt_after_journal)
    with pytest.raises(OSError, match="durable journal"):
        if operation == "save":
            store.save_map(person["id"], "מפה חדשה", sample_record("2024-07-03"))
        else:
            store.update_map(
                person["id"], entry["id"], "מפה חדשה",
                sample_record("2024-07-03", "תל אביב", "14:00"))
    assert store.journal_path.is_file()
    monkeypatch.undo()

    recovered = PeopleStore(tmp_path)
    saved_person = next(item for item in recovered.list_people() if item["id"] == person["id"])
    if operation == "save":
        assert saved_person["maps"] == []
    else:
        assert recovered.read_map(person["id"], entry["id"]) == original
        assert len(recovered.list_map_versions(person["id"], entry["id"])["versions"]) == 1
    assert not recovered.journal_path.exists()
    assert not list(recovered.directory.rglob(".astrochart-*.tmp"))
