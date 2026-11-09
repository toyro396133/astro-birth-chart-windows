"""Local-first people and per-person chart index.

Chart payloads remain the existing validated .astrochart.json records. This
module adds stable person/map IDs and stores those records under a private
per-user application-data directory. Legacy standalone chart files remain
readable and are never migrated or deleted implicitly.
"""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import uuid
from datetime import date, datetime, time, timezone
from pathlib import Path

from .chart_storage import read_record, save_record, validate_record

FORMAT = "astro-birth-chart-people"
SCHEMA_VERSION = 1
MAX_INDEX_BYTES = 4 * 1024 * 1024
MAX_PEOPLE = 5000
MAX_MAPS_PER_PERSON = 1000
_ID = re.compile(r"^[0-9a-f]{32}$")


def default_people_directory() -> Path:
    """Return a per-user local directory; never use the installation folder."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "AstroBirthChart" / "people"
    if os.name == "nt":
        return Path.home() / "AppData" / "Local" / "AstroBirthChart" / "people"
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "AstroBirthChart" / "people"
    return Path.home() / ".local" / "share" / "AstroBirthChart" / "people"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _valid_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"מזהה {field} אינו תקין")
    return value


def _valid_text(value: object, field: str, maximum: int, *, required=False,
                multiline=False) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"שדה {field} אינו תקין")
    value = value.strip()
    if required and not value:
        raise ValueError(f"חובה למלא {field}")
    allowed = "\t\r\n" if multiline else ""
    if any(ord(char) < 32 and char not in allowed for char in value):
        raise ValueError(f"שדה {field} מכיל תווי בקרה")
    return value


def _valid_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"תאריך {field} אינו תקין")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"תאריך {field} אינו תקין") from exc
    return value


def _validate_document(document: object) -> dict:
    if not isinstance(document, dict) or set(document) != {
        "format", "schema_version", "people"
    }:
        raise ValueError("קובץ האנשים אינו במבנה נתמך")
    if document["format"] != FORMAT or type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("גרסת קובץ האנשים אינה נתמכת")
    people = document["people"]
    if not isinstance(people, list) or len(people) > MAX_PEOPLE:
        raise ValueError("רשימת האנשים אינה תקינה או גדולה מדי")
    seen_people = set()
    for person in people:
        if not isinstance(person, dict) or set(person) != {
            "id", "name", "notes", "created_at", "updated_at", "maps"
        }:
            raise ValueError("רשומת אדם אינה תקינה")
        person_id = _valid_id(person["id"], "אדם")
        if person_id in seen_people:
            raise ValueError("מזהה אדם כפול בקובץ")
        seen_people.add(person_id)
        _valid_text(person["name"], "שם אדם", 120, required=True)
        _valid_text(person["notes"], "הערות", 4000, multiline=True)
        _valid_timestamp(person["created_at"], "יצירה")
        _valid_timestamp(person["updated_at"], "עדכון")
        maps = person["maps"]
        if not isinstance(maps, list) or len(maps) > MAX_MAPS_PER_PERSON:
            raise ValueError("רשימת המפות אינה תקינה או גדולה מדי")
        seen_maps = set()
        primary_count = 0
        for chart in maps:
            if not isinstance(chart, dict) or set(chart) != {
                "id", "name", "created_at", "updated_at", "is_primary",
                "civil_date", "city", "clock", "unknown_time"
            }:
                raise ValueError("רשומת מפה אינה תקינה")
            map_id = _valid_id(chart["id"], "מפה")
            if map_id in seen_maps:
                raise ValueError("מזהה מפה כפול אצל אותו אדם")
            seen_maps.add(map_id)
            _valid_text(chart["name"], "שם מפה", 120, required=True)
            _valid_timestamp(chart["created_at"], "יצירת מפה")
            _valid_timestamp(chart["updated_at"], "עדכון מפה")
            try:
                date.fromisoformat(chart["civil_date"])
            except (TypeError, ValueError) as exc:
                raise ValueError("תאריך המפה אינו תקין") from exc
            _valid_text(chart["city"], "מקום", 160)
            if chart["clock"] is not None:
                try:
                    time.fromisoformat(_valid_text(chart["clock"], "שעה", 20))
                except ValueError as exc:
                    raise ValueError("שעת המפה אינה תקינה") from exc
            if type(chart["unknown_time"]) is not bool or type(chart["is_primary"]) is not bool:
                raise ValueError("דגלי המפה אינם תקינים")
            primary_count += int(chart["is_primary"])
        if primary_count > 1:
            raise ValueError("לאדם יכולה להיות מפה ראשית אחת בלבד")
    return document


class PeopleStore:
    """Atomic metadata index with chart files addressed only by generated IDs."""

    def __init__(self, directory: str | os.PathLike | None = None):
        self.directory = Path(directory) if directory is not None else default_people_directory()
        self.index_path = self.directory / "people.json"

    def _read(self) -> dict:
        if not self.index_path.exists():
            return {"format": FORMAT, "schema_version": SCHEMA_VERSION, "people": []}
        try:
            if self.index_path.stat().st_size > MAX_INDEX_BYTES:
                raise ValueError("קובץ האנשים גדול מדי")
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("לא ניתן לקרוא את קובץ האנשים; הקובץ המקורי נשמר ללא שינוי") from exc
        return _validate_document(payload)

    def _write(self, document: dict) -> None:
        _validate_document(document)
        payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        encoded = payload.encode("utf-8")
        if len(encoded) > MAX_INDEX_BYTES:
            raise ValueError("קובץ האנשים גדול מדי")
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".people-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.index_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list_people(self) -> list[dict]:
        document = self._read()
        return sorted(copy.deepcopy(document["people"]), key=lambda item: (item["name"].casefold(), item["created_at"], item["id"]))

    def get_person(self, person_id: str) -> dict | None:
        person_id = _valid_id(person_id, "אדם")
        person = next((item for item in self._read()["people"] if item["id"] == person_id), None)
        return copy.deepcopy(person) if person else None

    def create_person(self, name: str, notes: str = "") -> dict:
        name = _valid_text(name, "שם אדם", 120, required=True)
        notes = _valid_text(notes, "הערות", 4000, multiline=True)
        document = self._read()
        if len(document["people"]) >= MAX_PEOPLE:
            raise ValueError("הגעת למכסת האנשים המקומית")
        now = _now()
        person = {
            "id": uuid.uuid4().hex,
            "name": name,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
            "maps": [],
        }
        document["people"].append(person)
        self._write(document)
        return copy.deepcopy(person)

    def update_person(self, person_id: str, name: str, notes: str = "") -> dict:
        person_id = _valid_id(person_id, "אדם")
        name = _valid_text(name, "שם אדם", 120, required=True)
        notes = _valid_text(notes, "הערות", 4000)
        document = self._read()
        person = next((item for item in document["people"] if item["id"] == person_id), None)
        if person is None:
            raise KeyError("האדם המבוקש אינו קיים")
        person["name"] = name
        person["notes"] = notes
        person["updated_at"] = _now()
        self._write(document)
        return copy.deepcopy(person)

    def map_path(self, person_id: str, map_id: str) -> Path:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        return self.directory / "maps" / person_id / f"{map_id}.astrochart.json"

    @staticmethod
    def _map_metadata(name: str, record: dict, map_id: str, created_at: str,
                      updated_at: str, is_primary: bool) -> dict:
        values = validate_record(record)["input"]
        return {
            "id": map_id,
            "name": _valid_text(name, "שם מפה", 120, required=True),
            "created_at": created_at,
            "updated_at": updated_at,
            "is_primary": bool(is_primary),
            "civil_date": values["civil_date"],
            "city": values["city"],
            "clock": values["clock"],
            "unknown_time": values["unknown_time"],
        }

    def save_map(self, person_id: str, name: str, record: dict) -> dict:
        person_id = _valid_id(person_id, "אדם")
        document = self._read()
        person = next((item for item in document["people"] if item["id"] == person_id), None)
        if person is None:
            raise KeyError("יש לבחור אדם קיים לפני שמירת מפה")
        if len(person["maps"]) >= MAX_MAPS_PER_PERSON:
            raise ValueError("הגעת למכסת המפות לאדם זה")
        now = _now()
        map_id = uuid.uuid4().hex
        entry = self._map_metadata(name, record, map_id, now, now, not person["maps"])
        target = self.map_path(person_id, map_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        save_record(target, record)
        person["maps"].append(entry)
        person["updated_at"] = now
        self._write(document)
        return copy.deepcopy(entry)

    def update_map(self, person_id: str, map_id: str, name: str, record: dict) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        document = self._read()
        person = next((item for item in document["people"] if item["id"] == person_id), None)
        if person is None:
            raise KeyError("האדם המבוקש אינו קיים")
        entry = next((item for item in person["maps"] if item["id"] == map_id), None)
        if entry is None:
            raise KeyError("המפה אינה משויכת לאדם זה")
        now = _now()
        metadata = self._map_metadata(
            name, record, map_id, entry["created_at"], now, entry["is_primary"])
        target = self.map_path(person_id, map_id)
        save_record(target, record)
        entry.update(metadata)
        person["updated_at"] = now
        self._write(document)
        return copy.deepcopy(entry)

    def read_map(self, person_id: str, map_id: str) -> dict:
        person = self.get_person(person_id)
        if person is None or not any(item["id"] == map_id for item in person["maps"]):
            raise KeyError("המפה אינה משויכת לאדם זה")
        return read_record(self.map_path(person_id, map_id))

    def set_primary_map(self, person_id: str, map_id: str) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        document = self._read()
        person = next((item for item in document["people"] if item["id"] == person_id), None)
        if person is None:
            raise KeyError("האדם המבוקש אינו קיים")
        if not any(item["id"] == map_id for item in person["maps"]):
            raise KeyError("המפה אינה משויכת לאדם זה")
        now = _now()
        for entry in person["maps"]:
            entry["is_primary"] = entry["id"] == map_id
        person["updated_at"] = now
        self._write(document)
        return copy.deepcopy(next(item for item in person["maps"] if item["id"] == map_id))
