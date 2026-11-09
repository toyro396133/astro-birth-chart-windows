import json

import pytest

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

    first = store.create_person("דוד כהן", "אדם ראשון")
    second = store.create_person("דוד כהן", "אדם אחר")

    assert first["id"] != second["id"]
    assert store.get_person(first["id"])["name"] == "דוד כהן"
    assert len(store.list_people()) == 2

    renamed = store.update_person(first["id"], "דוד לוי", "פרטים מעודכנים")
    assert renamed["id"] == first["id"]
    assert store.get_person(first["id"])["name"] == "דוד לוי"
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
    store.directory.mkdir(parents=True)
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
