"""Offline, versioned chart records; opening always requires recalculation."""
import copy
import json
import pytest

from astrochart.chart_storage import (
    SCHEMA_VERSION, export_results, make_record, read_record, save_record,
    validate_record,
)
from astrochart.domain import BodyPosition, Chart


@pytest.fixture
def data():
    return {
        "date_mode": "gregorian", "civil_date": "2024-07-01",
        "clock": "12:30", "gregorian_date": "2024-07-01",
        "hebrew_year": 5784, "hebrew_month": 10, "hebrew_day": 25,
        "phase": "day", "unknown_time": False, "estimated_time": False,
        "city": "ירושלים", "latitude": 31.7683, "longitude": 35.2137,
        "zone": "Asia/Jerusalem",
    }


def test_local_roundtrip_is_versioned_and_recalculation_only(tmp_path, data):
    record = make_record(data, "0.3.1")
    target = tmp_path / "sample.astrochart.json"
    save_record(target, record)
    assert target.exists()
    loaded = read_record(target)
    assert loaded == record
    assert loaded["schema_version"] == SCHEMA_VERSION
    assert loaded["calculation_method"]["houses"] == "whole-sign"
    assert loaded["recalculation_required_on_open"] is True
    assert "derived_data" not in loaded


def test_corrupt_schema_and_numerical_input_are_rejected(tmp_path, data):
    record = make_record(data, "0.3.1")
    modified = copy.deepcopy(record)
    modified["schema_version"] = 999
    with pytest.raises(ValueError):
        validate_record(modified)
    modified = copy.deepcopy(record)
    modified["input"]["latitude"] = float("nan")
    with pytest.raises(ValueError):
        validate_record(modified)
    modified = copy.deepcopy(record)
    modified["input"]["unknown_time"] = "false"
    with pytest.raises(ValueError):
        validate_record(modified)
    path = tmp_path / "invalid.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(ValueError):
        read_record(path)


def test_unknown_time_roundtrip_never_saves_an_invented_clock(data, tmp_path):
    data["clock"] = None
    data["unknown_time"] = True
    record = make_record(data, "0.3.1")
    chart = Chart([BodyPosition("שמש", 12.0, False)], [], None, None, True, [])
    structured = export_results(chart, record)
    assert structured["derived_data"]["hour_is_unknown"]
    assert structured["derived_data"]["sampled_midpoint_not_birth_position"]
    assert structured["input_record"]["input"]["clock"] is None
    save_record(tmp_path / "unknown.json", record)
    assert read_record(tmp_path / "unknown.json")["input"]["clock"] is None


def test_invalid_timezone_and_bad_file_size(tmp_path, data):
    modified = dict(data, zone="Zone/NotValid")
    with pytest.raises(ValueError):
        make_record(modified, "0.3.1")
    path = tmp_path / "too-big.json"
    path.write_text("x" * 300000, encoding="utf-8")
    with pytest.raises(ValueError, match="גדול"):
        read_record(path)
