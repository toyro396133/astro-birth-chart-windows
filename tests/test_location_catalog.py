"""Offline bilingual lookup and locally saved favorite coordinates."""
import json

import pytest

from astrochart.locations import CITIES
from astrochart.location_catalog import (
    MANUAL_LABEL, catalog_labels, load_favorites, resolve_location,
    save_favorite, validate_favorite,
)


def test_city_aliases_reference_existing_coordinates():
    assert resolve_location("Jerusalem") == CITIES["ירושלים"]
    assert resolve_location("  TEL   AVIV ") == CITIES["תל אביב"]
    assert resolve_location("New York City") == CITIES["ניו יורק"]
    assert resolve_location("עיר שאינה במאגר") is None
    labels = catalog_labels()
    assert MANUAL_LABEL in labels and "לונדון" in labels and "London" in labels


def test_favorites_roundtrip_locally_without_network(tmp_path):
    path = tmp_path / "places.json"
    entries = save_favorite("מקום מדידה", 31.2, 34.5, "Asia/Jerusalem", path)
    assert entries["מקום מדידה"] == [31.2, 34.5, "Asia/Jerusalem"]
    assert load_favorites(path) == entries
    assert resolve_location("מקום מדידה", entries) == (31.2, 34.5, "Asia/Jerusalem")
    assert "מקום מדידה" in catalog_labels(entries)


def test_invalid_coordinates_time_zone_and_overrides_rejected(tmp_path):
    path = tmp_path / "places.json"
    for name, lat, lon, zone in (
        ("ירושלים", 31.0, 35.0, "Asia/Jerusalem"),
        ("חדש", 90.0, 20.0, "Asia/Jerusalem"),
        ("חדש", float("nan"), 20.0, "Asia/Jerusalem"),
        ("חדש", 31.0, 200.0, "Asia/Jerusalem"),
        ("חדש", 31.0, 20.0, "Invalid/Timezone"),
    ):
        with pytest.raises(ValueError):
            save_favorite(name, lat, lon, zone, path)
    assert not path.exists()


def test_corrupt_or_oversized_favorite_file_is_ignored(tmp_path):
    path = tmp_path / "places.json"
    path.write_text("{broken", encoding="utf-8")
    assert load_favorites(path) == {}
    path.write_text(" " * 65537, encoding="utf-8")
    assert load_favorites(path) == {}
    path.write_text(json.dumps({"version": 1, "favorites": {
        "בעלים לא תקינים": [91, 0, "Asia/Jerusalem"],
        "מקום תקין": [32, 34, "Asia/Jerusalem"],
    }}, ensure_ascii=False), encoding="utf-8")
    assert set(load_favorites(path)) == {"מקום תקין"}
