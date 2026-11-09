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
import stat
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from pathlib import Path

from .chart_storage import read_record, save_record, validate_record

FORMAT = "astro-birth-chart-people"
SCHEMA_VERSION = 1
MAX_INDEX_BYTES = 4 * 1024 * 1024
MAX_PEOPLE = 5000
MAX_MAPS_PER_PERSON = 1000
MAX_MAP_VERSIONS = 1000
VERSION_FORMAT = "astro-birth-chart-map-versions"
VERSION_SCHEMA_VERSION = 1
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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
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
    seen_map_ids = set()
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
            if map_id in seen_maps or map_id in seen_map_ids:
                raise ValueError("מזהה מפה כפול בקובץ")
            seen_maps.add(map_id)
            seen_map_ids.add(map_id)
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
            if chart["unknown_time"] != (chart["clock"] is None):
                raise ValueError("דגל השעה אינו תואם לשעת המפה")
            primary_count += int(chart["is_primary"])
        if maps and primary_count != 1:
            raise ValueError("לאדם עם מפות חייבת להיות מפה ראשית אחת בלבד")
    return document


_THREAD_LOCKS = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(key: str):
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


class PeopleStore:
    """Local people index with process locking, recovery journal and safe paths."""

    JOURNAL_FORMAT = "astro-birth-chart-people-transaction"
    JOURNAL_SCHEMA = 2
    JOURNAL_NAME = ".people-transaction.json"
    VERSION_FORMAT = VERSION_FORMAT
    VERSION_SCHEMA_VERSION = VERSION_SCHEMA_VERSION
    LOCK_NAME = ".people.lock"

    def __init__(self, directory: str | os.PathLike | None = None):
        selected = Path(directory) if directory is not None else default_people_directory()
        self.directory = selected.expanduser().absolute()
        self.index_path = self.directory / "people.json"
        self.maps_path = self.directory / "maps"
        self.journal_path = self.directory / self.JOURNAL_NAME
        self.lock_path = self.directory / self.LOCK_NAME

    @staticmethod
    def _lexists(path: Path) -> bool:
        try:
            path.lstat()
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(info.st_mode):
            return True
        attributes = getattr(info, "st_file_attributes", 0)
        if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction):
            try:
                if is_junction():
                    return True
            except OSError:
                return True
        return False

    def _assert_safe_path(self, path: Path, *, kind: str | None = None) -> None:
        """Reject links/reparse points at every store-relative component."""
        path = Path(path).absolute()
        try:
            relative = path.relative_to(self.directory)
        except ValueError as exc:
            raise ValueError("הנתיב המבוקש נמצא מחוץ למאגר האנשים") from exc

        current = self.directory
        for component in ((),) + tuple((part,) for part in relative.parts):
            if component:
                current = current / component[0]
            if self._is_reparse_point(current):
                raise ValueError("קישור סמלי או נקודת הפניה במאגר האנשים אינם מותרים")
            if self._lexists(current):
                info = current.lstat()
                if current == self.directory and not stat.S_ISDIR(info.st_mode):
                    raise ValueError("תיקיית מאגר האנשים אינה תיקייה רגילה")
                if current == path and kind == "dir" and not stat.S_ISDIR(info.st_mode):
                    raise ValueError("רכיב הנתיב שאמור להיות תיקייה אינו תיקייה")
                if current == path and kind == "file" and not stat.S_ISREG(info.st_mode):
                    raise ValueError("רכיב הנתיב שאמור להיות קובץ אינו קובץ רגיל")

        try:
            root_real = self.directory.resolve(strict=False)
            candidate_real = path.resolve(strict=False)
            common = os.path.commonpath((str(root_real), str(candidate_real)))
        except (OSError, ValueError) as exc:
            raise ValueError("לא ניתן לאמת את הנתיב במאגר האנשים") from exc
        if os.path.normcase(common) != os.path.normcase(str(root_real)):
            raise ValueError("הנתיב הקנוני נמצא מחוץ למאגר האנשים")

    def _ensure_directory(self, path: Path) -> None:
        path = Path(path).absolute()
        self._assert_safe_path(path, kind="dir")
        if not self._lexists(self.directory):
            self.directory.parent.mkdir(parents=True, exist_ok=True)
            self._assert_safe_path(self.directory, kind="dir")
            created_root = False
            try:
                self.directory.mkdir()
                created_root = True
            except FileExistsError:
                pass
            if created_root:
                self._fsync_directory(self.directory.parent)
            self._assert_safe_path(self.directory, kind="dir")

        relative = path.relative_to(self.directory)
        current = self.directory
        for part in relative.parts:
            current = current / part
            self._assert_safe_path(current, kind="dir")
            if not self._lexists(current):
                created_child = False
                try:
                    current.mkdir()
                    created_child = True
                except FileExistsError:
                    pass
                if created_child:
                    self._fsync_directory(current.parent)
            self._assert_safe_path(current, kind="dir")

    MOVEFILE_REPLACE_EXISTING = 0x00000001
    MOVEFILE_WRITE_THROUGH = 0x00000008

    @staticmethod
    def _move_file_ex_w(source, destination, flags: int) -> None:
        """Call the Windows MoveFileExW API and preserve its failure code."""
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file_ex = kernel32.MoveFileExW
        move_file_ex.argtypes = (
            wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        move_file_ex.restype = wintypes.BOOL
        if not move_file_ex(str(source), str(destination), flags):
            error = ctypes.get_last_error()
            raise OSError(error, ctypes.FormatError(error), str(destination))

    def _replace_file(self, source, destination, *, platform=None) -> None:
        """Replace a file durably before returning.

        Windows uses MOVEFILE_WRITE_THROUGH for the rename itself. POSIX
        flushes the containing directory after os.replace; any fsync error
        propagates, including EIO/ENOSPC and filesystems that reject directory
        fsync. There is deliberately no unsafe best-effort fallback.
        """
        selected_platform = os.name if platform is None else platform
        if selected_platform == "nt":
            flags = self.MOVEFILE_REPLACE_EXISTING | self.MOVEFILE_WRITE_THROUGH
            self._move_file_ex_w(source, destination, flags)
            return
        os.replace(source, destination)
        self._fsync_directory(Path(destination).parent)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        # Windows critical replacements use MoveFileExW(WRITE_THROUGH). A
        # journal that reappears after an unflushed unlink is harmless: both
        # payload and index were made durable before the journal was removed,
        # and recovery is idempotent.
        if os.name == "nt":
            return
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, flags)
        try:
            # Fail closed. EIO/ENOSPC and unsupported-directory-fsync errors
            # are not swallowed because no equivalent fallback is guaranteed.
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @contextmanager
    def _locked(self):
        """Serialize threads and processes for the complete read/modify/write."""
        self._ensure_directory(self.directory)
        self._assert_safe_path(self.lock_path, kind="file")
        key = os.path.normcase(str(self.directory.resolve(strict=True)))
        local_lock = _thread_lock_for(key)
        with local_lock:
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.lock_path, flags, 0o600)
            lock_stream = os.fdopen(descriptor, "r+b")
            try:
                self._assert_safe_path(self.lock_path, kind="file")
                if os.name == "nt":
                    import msvcrt
                    lock_stream.seek(0, os.SEEK_END)
                    if lock_stream.tell() == 0:
                        lock_stream.write(b"\0")
                        lock_stream.flush()
                        os.fsync(lock_stream.fileno())
                    lock_stream.seek(0)
                    msvcrt.locking(lock_stream.fileno(), msvcrt.LK_LOCK, 1)
                    try:
                        yield
                    finally:
                        lock_stream.seek(0)
                        msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)
            finally:
                lock_stream.close()

    def _atomic_write_text(self, path: Path, payload: str, prefix: str) -> None:
        self._ensure_directory(path.parent)
        self._assert_safe_path(path, kind="file")
        descriptor, temporary = tempfile.mkstemp(
            prefix=prefix, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._assert_safe_path(path, kind="file")
            self._replace_file(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _remove_file(self, path: Path) -> None:
        self._assert_safe_path(path, kind="file")
        if self._lexists(path):
            path.unlink()
            # On POSIX this fsyncs the parent after unlink. On Windows a
            # stale journal may reappear after a crash, but it is safe because
            # the payload and index replacements were already write-through.
            self._fsync_directory(path.parent)

    def _save_record(self, path: Path, record: dict) -> None:
        self._assert_safe_path(path, kind="file")
        self._ensure_directory(path.parent)
        save_record(path, record, replace_func=self._replace_file)

    def _read_index_document(self) -> tuple[bool, dict | None]:
        self._assert_safe_path(self.index_path, kind="file")
        if not self._lexists(self.index_path):
            return False, None
        try:
            if self.index_path.stat().st_size > MAX_INDEX_BYTES:
                raise ValueError("קובץ האנשים גדול מדי")
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("לא ניתן לקרוא את קובץ האנשים; הקובץ המקורי נשמר ללא שינוי") from exc
        return True, _validate_document(payload)

    def _has_map_payloads(self) -> bool:
        self._assert_safe_path(self.maps_path, kind="dir")
        if not self._lexists(self.maps_path):
            return False
        pending = [self.maps_path]
        while pending:
            folder = pending.pop()
            self._assert_safe_path(folder, kind="dir")
            with os.scandir(folder) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    if self._is_reparse_point(child):
                        raise ValueError("נמצאה נקודת הפניה בתיקיית המפות; הקבצים לא שונו")
                    self._assert_safe_path(child)
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(child)
                    elif entry.is_file(follow_symlinks=False) and entry.name.endswith(".astrochart.json"):
                        return True
        return False

    def _read_unlocked(self) -> dict:
        exists, document = self._read_index_document()
        if exists:
            return document
        if self._has_map_payloads():
            raise ValueError(
                "קובץ האנשים חסר אך נמצאו קובצי מפה שמורים. "
                "הנתונים המקוריים נשמרו; נדרשת התאוששות של האינדקס.")
        return {"format": FORMAT, "schema_version": SCHEMA_VERSION, "people": []}

    def _read(self) -> dict:
        with self._locked():
            self._recover_transaction()
            return self._read_unlocked()

    def _write(self, document: dict) -> None:
        _validate_document(document)
        payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(payload.encode("utf-8")) > MAX_INDEX_BYTES:
            raise ValueError("קובץ האנשים גדול מדי")
        self._atomic_write_text(self.index_path, payload, ".people-")

    def _cleanup_temporary_files(self) -> None:
        if not self._lexists(self.directory):
            return
        with os.scandir(self.directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                self._assert_safe_path(path)
                if entry.is_file(follow_symlinks=False) and (
                    (entry.name.startswith(".people-") and entry.name.endswith(".tmp"))
                    or (entry.name.startswith(".people-journal-") and entry.name.endswith(".tmp"))
                ):
                    self._remove_file(path)

        self._assert_safe_path(self.maps_path, kind="dir")
        if not self._lexists(self.maps_path):
            return
        pending = [self.maps_path]
        while pending:
            folder = pending.pop()
            with os.scandir(folder) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    self._assert_safe_path(path)
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                    elif entry.is_file(follow_symlinks=False) and (
                        entry.name.startswith(".astrochart-") and entry.name.endswith(".tmp")
                    ):
                        self._remove_file(path)

    def _recover_transaction(self) -> None:
        self._assert_safe_path(self.journal_path, kind="file")
        if not self._lexists(self.journal_path):
            self._cleanup_temporary_files()
            return
        try:
            if self.journal_path.stat().st_size > MAX_INDEX_BYTES + 2 * 262144 + 65536:
                raise ValueError("יומן ההתאוששות גדול מדי")
            journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("יומן התאוששות פגום; הנתונים המקוריים נשמרו") from exc

        expected = {
            "format", "schema_version", "person_id", "map_id",
            "old_index_exists", "old_index", "new_index",
            "old_record", "new_record",
        }
        if (isinstance(journal, dict) and journal.get("schema_version") == self.JOURNAL_SCHEMA):
            self._recover_version_transaction(journal)
            return
        if not isinstance(journal, dict) or set(journal) != expected:
            raise ValueError("מבנה יומן ההתאוששות אינו מוכר; הנתונים נשמרו")
        if (journal["format"] != self.JOURNAL_FORMAT
                or type(journal["schema_version"]) is not int
                or journal["schema_version"] != 1):
            raise ValueError("גרסת יומן ההתאוששות אינה נתמכת; הנתונים נשמרו")
        person_id = _valid_id(journal["person_id"], "אדם")
        map_id = _valid_id(journal["map_id"], "מפה")
        if type(journal["old_index_exists"]) is not bool:
            raise ValueError("מצב האינדקס ביומן אינו תקין")
        old_index = _validate_document(journal["old_index"])
        new_index = _validate_document(journal["new_index"])
        new_record = validate_record(journal["new_record"])
        old_record = validate_record(journal["old_record"]) if journal["old_record"] is not None else None
        if not any(
            person["id"] == person_id and any(item["id"] == map_id for item in person["maps"])
            for person in new_index["people"]
        ):
            raise ValueError("יומן ההתאוששות אינו תואם למפה המיועדת")
        target = self.map_path(person_id, map_id)
        current_exists, current_index = self._read_index_document()

        if current_exists and current_index == new_index:
            # Index commit completed: make sure its payload is durable, then
            # finish by removing the journal.
            self._ensure_directory(target.parent)
            try:
                current_record = read_record(target)
                if current_record != new_record:
                    self._save_record(target, new_record)
            except (OSError, ValueError):
                self._save_record(target, new_record)
            self._fsync_directory(target.parent)
        elif current_exists == journal["old_index_exists"] and (
            (not current_exists) or current_index == old_index
        ):
            # Index commit did not happen: restore the previous payload (or
            # remove a newly-created payload) while the old index stays intact.
            if old_record is None:
                self._remove_file(target)
            else:
                self._ensure_directory(target.parent)
                try:
                    current_record = read_record(target)
                except (OSError, ValueError):
                    current_record = None
                if current_record != old_record:
                    self._save_record(target, old_record)
        else:
            raise ValueError(
                "נמצא שינוי חיצוני המתנגש ביומן ההתאוששות. "
                "הקבצים נשמרו ללא דריסה ונדרשת בדיקה ידנית.")

        self._remove_file(self.journal_path)
        self._cleanup_temporary_files()

    def _version_directory(self, person_id: str, map_id: str) -> Path:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        path = self.maps_path / person_id / f"{map_id}.versions"
        self._assert_safe_path(path, kind="dir")
        return path

    def _version_manifest_path(self, person_id: str, map_id: str) -> Path:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        path = self.maps_path / person_id / f"{map_id}.versions.json"
        self._assert_safe_path(path, kind="file")
        return path

    def _version_snapshot_path(self, person_id: str, map_id: str, version_id: str) -> Path:
        version_id = _valid_id(version_id, "גרסה")
        path = self._version_directory(person_id, map_id) / f"{version_id}.astrochart.json"
        self._assert_safe_path(path, kind="file")
        return path

    @staticmethod
    def _validate_version_manifest(manifest: object, person_id: str, map_id: str) -> dict:
        expected = {
            "format", "schema_version", "person_id", "map_id",
            "current_version_id", "versions",
        }
        if not isinstance(manifest, dict) or set(manifest) != expected:
            raise ValueError("מבנה היסטוריית הגרסאות אינו מוכר; הנתונים נשמרו")
        if (manifest["format"] != VERSION_FORMAT
                or type(manifest["schema_version"]) is not int
                or manifest["schema_version"] != VERSION_SCHEMA_VERSION
                or manifest["person_id"] != person_id
                or manifest["map_id"] != map_id):
            raise ValueError("היסטוריית הגרסאות אינה תואמת למפה או לגרסה נתמכת")
        versions = manifest["versions"]
        if not isinstance(versions, list) or not 1 <= len(versions) <= MAX_MAP_VERSIONS:
            raise ValueError("רשימת גרסאות המפה אינה תקינה")
        seen = set()
        for index, version in enumerate(versions, 1):
            if not isinstance(version, dict) or set(version) != {
                "id", "number", "created_at", "restored_from"
            }:
                raise ValueError("רשומת גרסת מפה אינה תקינה")
            version_id = _valid_id(version["id"], "גרסה")
            if version_id in seen or type(version["number"]) is not int or version["number"] != index:
                raise ValueError("מספר או מזהה גרסת מפה כפול/לא רציף")
            _valid_timestamp(version["created_at"], "גרסת מפה")
            restored_from = version["restored_from"]
            if restored_from is not None and restored_from not in seen:
                raise ValueError("מקור השחזור אינו גרסה קודמת")
            seen.add(version_id)
        current_id = _valid_id(manifest["current_version_id"], "גרסה נוכחית")
        if current_id != versions[-1]["id"]:
            raise ValueError("הגרסה הנוכחית חייבת להיות הגרסה האחרונה בהיסטוריה")
        return manifest

    def _read_version_manifest(self, person_id: str, map_id: str) -> dict | None:
        path = self._version_manifest_path(person_id, map_id)
        if not self._lexists(path):
            directory = self._version_directory(person_id, map_id)
            if self._lexists(directory):
                with os.scandir(directory) as entries:
                    if any(True for _ in entries):
                        raise ValueError(
                            "נמצאו snapshots ללא אינדקס גרסאות; נדרשת התאוששות ידנית והקבצים נשמרו")
            return None
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("קובץ היסטוריית הגרסאות גדול מדי")
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("לא ניתן לקרוא את היסטוריית הגרסאות; הקובץ המקורי נשמר") from exc
        return self._validate_version_manifest(manifest, person_id, map_id)

    def _write_version_manifest(self, person_id: str, map_id: str, manifest: dict) -> None:
        manifest = self._validate_version_manifest(manifest, person_id, map_id)
        payload = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(payload.encode("utf-8")) > 1024 * 1024:
            raise ValueError("קובץ היסטוריית הגרסאות גדול מדי")
        self._atomic_write_text(
            self._version_manifest_path(person_id, map_id), payload, ".astrochart-version-")

    def _write_version_snapshot(
        self, person_id: str, map_id: str, version_id: str, record: dict,
    ) -> None:
        target = self._version_snapshot_path(person_id, map_id, version_id)
        self._ensure_directory(target.parent)
        if self._lexists(target):
            existing = read_record(target)
            if existing != validate_record(record):
                raise ValueError("snapshot קיים אינו תואם לגרסה; ההיסטוריה נשמרה ללא שינוי")
            return
        self._save_record(target, record)

    def _remove_empty_version_directory(self, person_id: str, map_id: str) -> None:
        directory = self._version_directory(person_id, map_id)
        if not self._lexists(directory):
            return
        with os.scandir(directory) as entries:
            if next(entries, None) is not None:
                return
        directory.rmdir()
        self._fsync_directory(directory.parent)

    def _ensure_version_history(
        self, person_id: str, map_id: str, entry: dict, document: dict,
        old_index_exists: bool, old_index: dict,
    ) -> dict:
        manifest = self._read_version_manifest(person_id, map_id)
        current_record = read_record(self.map_path(person_id, map_id))
        if manifest is not None:
            current_snapshot = None
            for version in manifest["versions"]:
                snapshot = read_record(self._version_snapshot_path(
                    person_id, map_id, version["id"]))
                if version["id"] == manifest["current_version_id"]:
                    current_snapshot = snapshot
            if current_snapshot != current_record:
                raise ValueError(
                    "הגרסה הנוכחית אינה תואמת לקובץ המפה; נדרשת התאוששות וההיסטוריה נשמרה")
            return manifest

        version_id = uuid.uuid4().hex
        manifest = {
            "format": self.VERSION_FORMAT,
            "schema_version": self.VERSION_SCHEMA_VERSION,
            "person_id": person_id,
            "map_id": map_id,
            "current_version_id": version_id,
            "versions": [{
                "id": version_id, "number": 1,
                "created_at": entry["created_at"], "restored_from": None,
            }],
        }
        self._commit_version_transaction(
            person_id=person_id, map_id=map_id,
            old_index_exists=old_index_exists, old_index=old_index,
            new_index=document, old_record=current_record, new_record=current_record,
            old_manifest_exists=False, old_manifest=None,
            new_manifest=manifest, version_id=version_id,
            new_version_record=current_record,
        )
        return manifest

    def _next_version_manifest(
        self, person_id: str, map_id: str, old_manifest: dict,
        *, restored_from: str | None = None,
    ) -> tuple[dict, str]:
        versions = copy.deepcopy(old_manifest["versions"])
        if len(versions) >= MAX_MAP_VERSIONS:
            raise ValueError("הגעת למכסת גרסאות המפה")
        version_id = uuid.uuid4().hex
        versions.append({
            "id": version_id, "number": len(versions) + 1,
            "created_at": _now(), "restored_from": restored_from,
        })
        manifest = {
            "format": self.VERSION_FORMAT,
            "schema_version": self.VERSION_SCHEMA_VERSION,
            "person_id": person_id, "map_id": map_id,
            "current_version_id": version_id, "versions": versions,
        }
        return self._validate_version_manifest(manifest, person_id, map_id), version_id

    def _recover_version_transaction(self, journal: dict) -> None:
        expected = {
            "format", "schema_version", "operation", "person_id", "map_id",
            "old_index_exists", "old_index", "new_index", "old_record", "new_record",
            "old_manifest_exists", "old_manifest", "new_manifest",
            "version_id", "new_version_record",
        }
        if set(journal) != expected or journal.get("format") != self.JOURNAL_FORMAT:
            raise ValueError("מבנה יומן גרסאות אינו מוכר; הנתונים נשמרו")
        if journal["operation"] != "map_version" or journal["schema_version"] != self.JOURNAL_SCHEMA:
            raise ValueError("סוג או גרסת יומן גרסאות אינם נתמכים; הנתונים נשמרו")
        person_id = _valid_id(journal["person_id"], "אדם")
        map_id = _valid_id(journal["map_id"], "מפה")
        version_id = _valid_id(journal["version_id"], "גרסה")
        if type(journal["old_index_exists"]) is not bool or type(journal["old_manifest_exists"]) is not bool:
            raise ValueError("דגלי קיום ביומן הגרסאות אינם תקינים")
        old_index = _validate_document(journal["old_index"])
        new_index = _validate_document(journal["new_index"])
        old_record = validate_record(journal["old_record"]) if journal["old_record"] is not None else None
        new_record = validate_record(journal["new_record"])
        new_version_record = validate_record(journal["new_version_record"])
        if new_version_record != new_record:
            raise ValueError("snapshot הגרסה אינו תואם ל-payload הנוכחי ביומן")
        old_manifest = (
            self._validate_version_manifest(journal["old_manifest"], person_id, map_id)
            if journal["old_manifest_exists"] else None
        )
        if not journal["old_manifest_exists"] and journal["old_manifest"] is not None:
            raise ValueError("יומן הגרסאות כולל manifest ישן בלתי צפוי")
        new_manifest = self._validate_version_manifest(journal["new_manifest"], person_id, map_id)
        if new_manifest["current_version_id"] != version_id:
            raise ValueError("מזהה הגרסה ביומן אינו תואם ל-manifest החדש")
        if not any(
            person["id"] == person_id and any(item["id"] == map_id for item in person["maps"])
            for person in new_index["people"]
        ):
            raise ValueError("יומן הגרסאות אינו תואם למפה המיועדת")

        target = self.map_path(person_id, map_id)
        manifest_path = self._version_manifest_path(person_id, map_id)
        snapshot_path = self._version_snapshot_path(person_id, map_id, version_id)
        current_exists, current_index = self._read_index_document()

        if current_exists and current_index == new_index:
            self._ensure_directory(target.parent)
            self._write_version_snapshot(person_id, map_id, version_id, new_version_record)
            try:
                current_record = read_record(target)
            except (OSError, ValueError):
                current_record = None
            if current_record != new_record:
                self._save_record(target, new_record)
            self._write_version_manifest(person_id, map_id, new_manifest)
            self._fsync_directory(target.parent)
        elif current_exists == journal["old_index_exists"] and (
            (not current_exists) or current_index == old_index
        ):
            if old_record is None:
                self._remove_file(target)
            else:
                self._ensure_directory(target.parent)
                try:
                    current_record = read_record(target)
                except (OSError, ValueError):
                    current_record = None
                if current_record != old_record:
                    self._save_record(target, old_record)
            if journal["old_manifest_exists"]:
                self._write_version_manifest(person_id, map_id, old_manifest)
            else:
                self._remove_file(manifest_path)
            self._remove_file(snapshot_path)
            self._remove_empty_version_directory(person_id, map_id)
        else:
            raise ValueError(
                "נמצא שינוי חיצוני המתנגש ביומן גרסאות. "
                "הקבצים נשמרו ללא דריסה ונדרשת בדיקה ידנית.")

        self._remove_file(self.journal_path)
        self._cleanup_temporary_files()

    def _commit_version_transaction(
        self, *, person_id: str, map_id: str, old_index_exists: bool,
        old_index: dict, new_index: dict, old_record: dict | None, new_record: dict,
        old_manifest_exists: bool, old_manifest: dict | None, new_manifest: dict,
        version_id: str, new_version_record: dict,
    ) -> None:
        journal = {
            "format": self.JOURNAL_FORMAT, "schema_version": self.JOURNAL_SCHEMA,
            "operation": "map_version", "person_id": person_id, "map_id": map_id,
            "old_index_exists": old_index_exists, "old_index": old_index,
            "new_index": new_index, "old_record": old_record, "new_record": new_record,
            "old_manifest_exists": old_manifest_exists, "old_manifest": old_manifest,
            "new_manifest": new_manifest, "version_id": version_id,
            "new_version_record": new_version_record,
        }
        payload = json.dumps(journal, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(payload.encode("utf-8")) > MAX_INDEX_BYTES + 2 * 262144 + 2 * 1024 * 1024:
            raise ValueError("יומן גרסאות המפה גדול מדי")
        target = self.map_path(person_id, map_id)
        self._atomic_write_text(self.journal_path, payload, ".people-journal-")
        try:
            self._write_version_snapshot(person_id, map_id, version_id, new_version_record)
            self._ensure_directory(target.parent)
            # Lazy migration of a legacy map must not rewrite its current
            # payload; only a changed payload is replaced during a new version.
            if old_record != new_record or not self._lexists(target):
                self._save_record(target, new_record)
            self._write_version_manifest(person_id, map_id, new_manifest)
            self._write(new_index)
            self._remove_file(self.journal_path)
        except Exception:
            try:
                self._recover_transaction()
            except Exception:
                pass
            raise

    def _commit_map_transaction(
        self, *, person_id: str, map_id: str, old_index_exists: bool,
        old_index: dict, new_index: dict, old_record: dict | None, new_record: dict,
    ) -> None:
        journal = {
            "format": self.JOURNAL_FORMAT,
            "schema_version": 1,
            "person_id": person_id,
            "map_id": map_id,
            "old_index_exists": old_index_exists,
            "old_index": old_index,
            "new_index": new_index,
            "old_record": old_record,
            "new_record": new_record,
        }
        payload = json.dumps(journal, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(payload.encode("utf-8")) > MAX_INDEX_BYTES + 2 * 262144 + 65536:
            raise ValueError("יומן ההתאוששות גדול מדי")
        target = self.map_path(person_id, map_id)
        self._atomic_write_text(self.journal_path, payload, ".people-journal-")
        try:
            self._ensure_directory(target.parent)
            if old_record != new_record or not self._lexists(target):
                self._save_record(target, new_record)
            self._write(new_index)
            self._remove_file(self.journal_path)
        except Exception:
            # Best-effort immediate recovery. If the filesystem remains
            # unavailable, the durable journal is retained for the next read.
            try:
                self._recover_transaction()
            except Exception:
                pass
            raise

    def list_people(self) -> list[dict]:
        with self._locked():
            self._recover_transaction()
            document = self._read_unlocked()
            return sorted(
                copy.deepcopy(document["people"]),
                key=lambda item: (item["name"].casefold(), item["created_at"], item["id"]),
            )

    def get_person(self, person_id: str) -> dict | None:
        person_id = _valid_id(person_id, "אדם")
        with self._locked():
            self._recover_transaction()
            person = next(
                (item for item in self._read_unlocked()["people"] if item["id"] == person_id),
                None,
            )
            return copy.deepcopy(person) if person else None

    def create_person(self, name: str, notes: str = "") -> dict:
        name = _valid_text(name, "שם אדם", 120, required=True)
        notes = _valid_text(notes, "הערות", 4000, multiline=True)
        with self._locked():
            self._recover_transaction()
            document = self._read_unlocked()
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
        notes = _valid_text(notes, "הערות", 4000, multiline=True)
        with self._locked():
            self._recover_transaction()
            document = self._read_unlocked()
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
        target = self.maps_path / person_id / f"{map_id}.astrochart.json"
        self._assert_safe_path(target, kind="file")
        return target

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
        record = validate_record(record)
        with self._locked():
            self._recover_transaction()
            old_index_exists, old_index = self._read_index_document()
            document = self._read_unlocked()
            person = next((item for item in document["people"] if item["id"] == person_id), None)
            if person is None:
                raise KeyError("יש לבחור אדם קיים לפני שמירת מפה")
            if len(person["maps"]) >= MAX_MAPS_PER_PERSON:
                raise ValueError("הגעת למכסת המפות לאדם זה")
            now = _now()
            map_id = uuid.uuid4().hex
            entry = self._map_metadata(name, record, map_id, now, now, not person["maps"])
            target = self.map_path(person_id, map_id)
            manifest_path = self._version_manifest_path(person_id, map_id)
            version_directory = self._version_directory(person_id, map_id)
            if self._lexists(target) or self._lexists(manifest_path) or self._lexists(version_directory):
                raise FileExistsError("מזהה המפה כבר קיים")
            version_id = uuid.uuid4().hex
            manifest = {
                "format": self.VERSION_FORMAT,
                "schema_version": self.VERSION_SCHEMA_VERSION,
                "person_id": person_id,
                "map_id": map_id,
                "current_version_id": version_id,
                "versions": [{
                    "id": version_id, "number": 1,
                    "created_at": now, "restored_from": None,
                }],
            }
            person["maps"].append(entry)
            person["updated_at"] = now
            old_snapshot = old_index if old_index_exists else {
                "format": FORMAT, "schema_version": SCHEMA_VERSION, "people": []
            }
            self._commit_version_transaction(
                person_id=person_id, map_id=map_id,
                old_index_exists=old_index_exists, old_index=old_snapshot,
                new_index=document, old_record=None, new_record=record,
                old_manifest_exists=False, old_manifest=None,
                new_manifest=manifest, version_id=version_id,
                new_version_record=record,
            )
            return copy.deepcopy(entry)

    def update_map(self, person_id: str, map_id: str, name: str, record: dict) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        record = validate_record(record)
        with self._locked():
            self._recover_transaction()
            old_index_exists, old_index = self._read_index_document()
            document = self._read_unlocked()
            person = next((item for item in document["people"] if item["id"] == person_id), None)
            if person is None:
                raise KeyError("האדם המבוקש אינו קיים")
            entry = next((item for item in person["maps"] if item["id"] == map_id), None)
            if entry is None:
                raise KeyError("המפה אינה משויכת לאדם זה")
            target = self.map_path(person_id, map_id)
            old_record = read_record(target)
            manifest = self._ensure_version_history(
                person_id, map_id, entry, document, old_index_exists, old_index)
            now = _now()
            metadata = self._map_metadata(
                name, record, map_id, entry["created_at"], now, entry["is_primary"])
            if record == old_record:
                metadata_changed = any(entry.get(key) != value for key, value in metadata.items())
                if metadata_changed:
                    entry.update(metadata)
                    person["updated_at"] = now
                    self._commit_map_transaction(
                        person_id=person_id, map_id=map_id,
                        old_index_exists=old_index_exists, old_index=old_index,
                        new_index=document, old_record=old_record, new_record=old_record,
                    )
                return copy.deepcopy(entry)

            new_manifest, version_id = self._next_version_manifest(
                person_id, map_id, manifest)
            entry.update(metadata)
            person["updated_at"] = now
            self._commit_version_transaction(
                person_id=person_id, map_id=map_id,
                old_index_exists=old_index_exists, old_index=old_index,
                new_index=document, old_record=old_record, new_record=record,
                old_manifest_exists=True, old_manifest=manifest,
                new_manifest=new_manifest, version_id=version_id,
                new_version_record=record,
            )
            return copy.deepcopy(entry)

    def list_map_versions(self, person_id: str, map_id: str) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        with self._locked():
            self._recover_transaction()
            document = self._read_unlocked()
            person = next((item for item in document["people"] if item["id"] == person_id), None)
            entry = next((item for item in person["maps"] if item["id"] == map_id), None) if person else None
            if entry is None:
                raise KeyError("המפה אינה משויכת לאדם זה")
            old_index_exists, old_index = self._read_index_document()
            manifest = self._ensure_version_history(
                person_id, map_id, entry, document, old_index_exists, old_index)
            versions = copy.deepcopy(manifest["versions"])
            for version in versions:
                version["is_current"] = version["id"] == manifest["current_version_id"]
            return {"current_version_id": manifest["current_version_id"], "versions": versions}

    def read_map_version(self, person_id: str, map_id: str, version_id: str) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        version_id = _valid_id(version_id, "גרסה")
        with self._locked():
            self._recover_transaction()
            document = self._read_unlocked()
            person = next((item for item in document["people"] if item["id"] == person_id), None)
            entry = next((item for item in person["maps"] if item["id"] == map_id), None) if person else None
            if entry is None:
                raise KeyError("המפה אינה משויכת לאדם זה")
            old_index_exists, old_index = self._read_index_document()
            manifest = self._ensure_version_history(
                person_id, map_id, entry, document, old_index_exists, old_index)
            if not any(version["id"] == version_id for version in manifest["versions"]):
                raise KeyError("גרסת המפה המבוקשת אינה קיימת")
            return read_record(self._version_snapshot_path(person_id, map_id, version_id))

    def restore_map_version(self, person_id: str, map_id: str, version_id: str) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        version_id = _valid_id(version_id, "גרסה")
        with self._locked():
            self._recover_transaction()
            old_index_exists, old_index = self._read_index_document()
            document = self._read_unlocked()
            person = next((item for item in document["people"] if item["id"] == person_id), None)
            entry = next((item for item in person["maps"] if item["id"] == map_id), None) if person else None
            if entry is None:
                raise KeyError("המפה אינה משויכת לאדם זה")
            manifest = self._ensure_version_history(
                person_id, map_id, entry, document, old_index_exists, old_index)
            selected = next((item for item in manifest["versions"] if item["id"] == version_id), None)
            if selected is None:
                raise KeyError("גרסת המפה המבוקשת אינה קיימת")
            if version_id == manifest["current_version_id"]:
                return copy.deepcopy(entry)
            old_record = read_record(self.map_path(person_id, map_id))
            restored_record = read_record(self._version_snapshot_path(person_id, map_id, version_id))
            new_manifest, new_version_id = self._next_version_manifest(
                person_id, map_id, manifest, restored_from=version_id)
            now = _now()
            entry.update(self._map_metadata(
                entry["name"], restored_record, map_id, entry["created_at"],
                now, entry["is_primary"]))
            person["updated_at"] = now
            self._commit_version_transaction(
                person_id=person_id, map_id=map_id,
                old_index_exists=old_index_exists, old_index=old_index,
                new_index=document, old_record=old_record, new_record=restored_record,
                old_manifest_exists=True, old_manifest=manifest,
                new_manifest=new_manifest, version_id=new_version_id,
                new_version_record=restored_record,
            )
            return copy.deepcopy(entry)

    def read_map(self, person_id: str, map_id: str) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        with self._locked():
            self._recover_transaction()
            person = next(
                (item for item in self._read_unlocked()["people"] if item["id"] == person_id),
                None,
            )
            if person is None or not any(item["id"] == map_id for item in person["maps"]):
                raise KeyError("המפה אינה משויכת לאדם זה")
            target = self.map_path(person_id, map_id)
            self._assert_safe_path(target, kind="file")
            return read_record(target)

    def set_primary_map(self, person_id: str, map_id: str) -> dict:
        person_id = _valid_id(person_id, "אדם")
        map_id = _valid_id(map_id, "מפה")
        with self._locked():
            self._recover_transaction()
            document = self._read_unlocked()
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
