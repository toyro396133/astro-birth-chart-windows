"""Build and apply file-level delta updates for the *portable* Windows distribution.

The complete target manifest is mandatory: every reused local byte and every
downloaded byte is SHA-256 checked before the existing atomic folder swap.
Registered Inno Setup installations must continue to use the full installer.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from .updater import (
    ASSET, EXE, HELPER, INSTALLED_MARKER, MAX_UNZIP, UpdateError,
    download_release, extract_release,
)

ROOT = "AstroBirthChart/"
MANIFEST = "delta.json"
MAX_FILES = 3000
MAX_MANIFEST = 1_000_000
HEX = re.compile(r"^[a-f0-9]{64}$")
BAD = re.compile(r'[<>:"|?*\\\\\x00-\x1f]')
DEVICE = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\\.|$)", re.I)
REQUIRED = {
    EXE, HELPER, "version.json", "_internal/data/ephemeris/de440s.bsp",
}


def _relative(name):
    """Reject Windows-path ambiguities as well as traditional ZIP traversal."""
    if not isinstance(name, str) or not 0 < len(name) <= 240 or "\\\\" in name:
        raise UpdateError("שם קובץ לא בטוח בחבילת עדכון חלקי")
    parts = name.split("/")
    if any(not p or p in (".", "..") or p[-1] in (".", " ")
           or BAD.search(p) or DEVICE.match(p) for p in parts):
        raise UpdateError("נתיב לא בטוח בחבילת עדכון חלקי")
    return name


def _members(archive):
    """Extract verified, unique file index of a full release ZIP."""
    found, folded = {}, set()
    for info in archive.infolist():
        name = info.filename
        if name == ROOT and info.is_dir():
            continue
        if not name.startswith(ROOT):
            raise UpdateError("מבנה חבילת גרסה אינו תקין")
        suffix = name[len(ROOT):].rstrip("/") if info.is_dir() else name[len(ROOT):]
        _relative(suffix)
        if stat.S_ISLNK(info.external_attr >> 16):
            raise UpdateError("חבילת גרסה מכילה קישור סמלי")
        if info.is_dir():
            continue
        key = suffix.casefold()
        if key in folded or info.file_size < 0 or info.file_size > MAX_UNZIP:
            raise UpdateError("כפילויות או גדלים לא תקינים בחבילת גרסה")
        folded.add(key)
        found[suffix] = info
    if len(found) > MAX_FILES or not REQUIRED.issubset(found):
        raise UpdateError("קובצי גרסה חיוניים חסרים או מספר הקבצים חריג")
    if sum(i.file_size for i in found.values()) > MAX_UNZIP:
        raise UpdateError("חבילת גרסה גדולה מדי")
    # File/directory collisions are not allowed even if exact spellings differ.
    if any("/".join(k.split("/")[:n]).casefold() in folded
           for k in found for n in range(1, len(k.split("/")))):
        raise UpdateError("התנגשות בין תיקייה לקובץ")
    return found


def _copy_checked(source, target, expected_size, expected_hash=None):
    digest, count = sha256(), 0
    while True:
        block = source.read(1024 * 1024)
        if not block:
            break
        count += len(block)
        if count > expected_size:
            raise UpdateError("גודל קובץ בעדכון חלקי אינו תקין")
        digest.update(block)
        if target is not None:
            target.write(block)
    if count != expected_size or (
            expected_hash is not None and digest.hexdigest() != expected_hash):
        raise UpdateError("בדיקת SHA-256 של קובץ עדכון חלקי נכשלה")
    return digest.hexdigest()


def _release_version(archive, files):
    with archive.open(files["version.json"]) as source:
        try:
            value = json.loads(source.read(4096))
        except (ValueError, UnicodeDecodeError) as exc:
            raise UpdateError("קובץ גרסה לא תקין") from exc
    version = value.get("version") if isinstance(value, dict) else None
    if not isinstance(version, str) or value != {
            "version": version, "platform": "windows-x64"}:
        raise UpdateError("פרטי גרסה לא תקינים")
    from .updater import parts_version
    parts_version(version)
    return version


def create_delta(previous_zip, current_zip, destination):
    """Produce a single predecessor->current release asset, or None if not smaller.

    Each manifest entry describes the entire target install, including deleted
    files (implicitly omitted) and preserved files, never merely a patch list.
    """
    previous_zip, current_zip, destination = map(Path, (
        previous_zip, current_zip, destination))
    if destination.exists():
        raise UpdateError("קובץ עדכון חלקי כבר קיים")
    try:
        with ZipFile(previous_zip) as old, ZipFile(current_zip) as new:
            before, after = _members(old), _members(new)
            old_version, new_version = (
                _release_version(old, before), _release_version(new, after))
            from .updater import is_newer
            if not is_newer(new_version, old_version):
                raise UpdateError("גרסת היעד חייבת להיות חדשה מגרסת המקור")
            entries = []
            with ZipFile(destination, "x", ZIP_DEFLATED, compresslevel=6) as delta:
                for name, info in sorted(after.items()):
                    with new.open(info) as source:
                        digest = _copy_checked(source, None, info.file_size)
                    reuse = False
                    predecessor = before.get(name)
                    if predecessor and predecessor.file_size == info.file_size:
                        with old.open(predecessor) as source:
                            reuse = _copy_checked(
                                source, None, predecessor.file_size) == digest
                    if not reuse:
                        with new.open(info) as source, delta.open(
                                "payload/" + name, "w", force_zip64=True) as target:
                            _copy_checked(source, target, info.file_size, digest)
                    entries.append({
                        "path": name, "size": info.file_size, "sha256": digest,
                        "source": "copy" if reuse else "payload",
                    })
                descriptor = {
                    "schema": 1, "platform": "windows-x64",
                    "from_version": old_version, "to_version": new_version,
                    "files": entries,
                }
                delta.writestr(MANIFEST, json.dumps(
                    descriptor, ensure_ascii=False, separators=(",", ":")))
        if destination.stat().st_size >= current_zip.stat().st_size:
            destination.unlink()
            return None
        return destination
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def extract_delta(archive, installation, version, base_version):
    """Materialize and fully verify a future portable directory beside install.

    No currently installed file is modified. Any failure deletes staging; the
    caller can then download the complete release ZIP and apply the old path.
    """
    installation = Path(installation).resolve()
    if (installation.name != "AstroBirthChart" or
            not (installation / EXE).is_file() or
            (installation / INSTALLED_MARKER).exists()):
        raise UpdateError("עדכון חלקי מותר רק לגרסה ניידת תקינה")
    try:
        current = json.loads((installation / "version.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise UpdateError("גרסת ההתקנה המקומית חסרה") from exc
    if current != {"version": base_version, "platform": "windows-x64"}:
        raise UpdateError("גרסת המקור המקומית אינה תואמת לעדכון החלקי")
    stage = None
    try:
        with ZipFile(archive) as delta:
            metadata_entries = [i for i in delta.infolist() if i.filename == MANIFEST]
            if len(metadata_entries) != 1 or metadata_entries[0].file_size > MAX_MANIFEST:
                raise UpdateError("מניפסט עדכון חלקי חסר או גדול מדי")
            with delta.open(metadata_entries[0]) as source:
                spec = json.loads(source.read(MAX_MANIFEST + 1))
            if not isinstance(spec, dict) or set(spec) != {
                "schema", "platform", "from_version", "to_version", "files"} or (
                    spec["schema"], spec["platform"],
                    spec["from_version"], spec["to_version"]) != (
                    1, "windows-x64", base_version, version):
                raise UpdateError("גרסאות או מבנה העדכון החלקי אינם תואמים")
            records = spec["files"]
            if not isinstance(records, list) or not 1 <= len(records) <= MAX_FILES:
                raise UpdateError("רשימת קובצי עדכון חלקי אינה תקינה")
            wanted, reused, folded, total = {}, {}, set(), 0
            for record in records:
                if not isinstance(record, dict) or set(record) != {
                    "path", "size", "sha256", "source"}:
                    raise UpdateError("רשומת קובץ עדכון חלקי אינה תקינה")
                name = _relative(record["path"])
                size, digest, kind = record["size"], record["sha256"], record["source"]
                if (type(size) is not int or size < 0 or size > MAX_UNZIP or
                        not isinstance(digest, str) or not HEX.fullmatch(digest) or
                        kind not in ("copy", "payload") or name.casefold() in folded):
                    raise UpdateError("רשומת קובץ עדכון חלקי פגומה")
                folded.add(name.casefold())
                total += size
                if total > MAX_UNZIP:
                    raise UpdateError("גודל עדכון חלקי חורג מהמותר")
                (reused if kind == "copy" else wanted)[name] = (size, digest)
            if not REQUIRED.issubset(reused.keys() | wanted.keys()):
                raise UpdateError("חסרים קובצי הרצה חיוניים בעדכון חלקי")
            if any("/".join(k.split("/")[:n]).casefold() in folded
                   for k in (*reused, *wanted)
                   for n in range(1, len(k.split("/")))):
                raise UpdateError("התנגשות נתיבי קבצים בעדכון חלקי")
            expected = {MANIFEST} | {"payload/" + k for k in wanted}
            actual = [i.filename for i in delta.infolist()]
            if len(actual) != len(expected) or set(actual) != expected:
                raise UpdateError("הארכיון מכיל קבצים חסרים או לא מורשים")
            for info in delta.infolist():
                if (info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or
                        info.file_size > MAX_UNZIP):
                    raise UpdateError("קובץ ZIP לא מורשה בעדכון חלקי")
            stage = Path(tempfile.mkdtemp(
                prefix=".astrochart-stage-", dir=installation.parent))
            for name, (size, digest) in sorted({**reused, **wanted}.items()):
                destination = stage.joinpath(*name.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                if name in reused:
                    original = installation.joinpath(*name.split("/"))
                    if (not original.is_file() or original.is_symlink() or
                            not original.resolve().is_relative_to(installation) or
                            any(p.is_symlink() for p in original.parents
                                if p == installation or installation in p.parents)):
                        raise UpdateError("קובץ מקומי חסר או מצביע מחוץ להתקנה")
                    with original.open("rb") as source, destination.open("xb") as out:
                        _copy_checked(source, out, size, digest)
                else:
                    with delta.open("payload/" + name) as source, destination.open("xb") as out:
                        _copy_checked(source, out, size, digest)
            if json.loads((stage / "version.json").read_text("utf-8")) != {
                    "version": version, "platform": "windows-x64"}:
                raise UpdateError("קובץ גרסה אינו תואם למניפסט")
            return stage
    except BaseException as exc:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError("הכנת עדכון חלקי נכשלה") from exc


def prepare_portable_update(release, installation, base_version):
    """Try verified delta first, then verified full ZIP (never silently install)."""
    with tempfile.TemporaryDirectory(prefix="AstroChart-Download-") as folder:
        root = Path(folder)
        if release.delta is not None:
            try:
                archive = root / "delta.zip"
                download_release(release.delta, archive)
                return extract_delta(
                    archive, installation, release.version, base_version), "delta"
            except Exception:
                # No stage survives failed delta preparation; full asset is still
                # independently verified with its own GitHub digest.
                pass
        archive = root / ASSET
        download_release(release, archive)
        return extract_release(archive, installation, release.version), "full"
