"""Offline-first updater driven by GitHub Releases SHA256 asset digests.

No telemetry or personal data. GitHub HTTPS and the repository account are
the trust anchors: an account compromise requires separate code signing.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from zipfile import ZipFile, BadZipFile

REPO = "toyro396133/astro-birth-chart-windows"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
API_HISTORY = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ASSET = "AstroBirthChart-Windows-x64.zip"
SETUP_ASSET = "AstroBirthChart-Setup.exe"
SETUP_DELTA_PREFIX = "AstroBirthChart-Setup-Delta-from-v"
INSTALLED_MARKER = "installed-by-setup.marker"
EXE = "AstroBirthChart.exe"
HELPER = "AstroBirthChartUpdater.exe"
MAX_ZIP = 350_000_000
MAX_UNZIP = 900_000_000
TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
HASH = re.compile(r"^sha256:([a-f0-9]{64})$")


class UpdateError(Exception):
    pass


def parts_version(v):
    if not isinstance(v, str) or not TAG.fullmatch("v" + v):
        raise UpdateError("פורמט גרסה לא תקין")
    return tuple(int(x) for x in v.split("."))


def is_newer(new, old):
    return parts_version(new) > parts_version(old)


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    digest: str
    size: int
    notes: str = ""
    delta_url: str = ""
    delta_digest: str = ""
    delta_size: int = 0
    delta_base: str = ""


class SecureRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise UpdateError("העדכון ניסה לעבור לחיבור לא מוצפן")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_https(url, timeout=20):
    if urlsplit(url).scheme != "https":
        raise UpdateError("עדכונים מותרים רק ב־HTTPS")
    return build_opener(SecureRedirect()).open(
        Request(url, headers={"User-Agent": "AstroBirthChart/Updater",
                              "Accept": "application/vnd.github+json"
                              if url in (API, API_HISTORY) else "application/octet-stream"}),
        timeout=timeout)


def parse_release(payload, asset_name=ASSET):
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise UpdateError("לא נמצאה גרסה יציבה")
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise UpdateError("תג גרסה לא תקין")
    if asset_name not in (ASSET, SETUP_ASSET):
        raise UpdateError("סוג חבילה לא מורשה")
    expected_url = f"https://github.com/{REPO}/releases/download/{tag}/{asset_name}"
    items = [a for a in payload.get("assets", []) if isinstance(a, dict)
             and a.get("name") == asset_name and a.get("state") == "uploaded"]
    if len(items) != 1 or items[0].get("browser_download_url") != expected_url:
        raise UpdateError("קובץ העדכון חסר או שמקורו אינו מורשה")
    item = items[0]
    digest = item.get("digest")
    match = HASH.fullmatch(digest) if isinstance(digest, str) else None
    size = item.get("size")
    if not match or type(size) is not int or not 0 < size <= MAX_ZIP:
        raise UpdateError("העדכון חסר חותמת SHA-256 או גודל תקין")
    body = payload.get("body")
    notes = body[:10000].replace("\r", "") if isinstance(body, str) else ""
    return Release(tag[1:], expected_url, match.group(1), size, notes)


def setup_delta_asset(payload, release, base_version):
    """Choose only the exact signed GitHub Release asset from installed to target.

    A missing or invalid patch never prevents the full installer from working.
    """
    parts_version(base_version)
    if not is_newer(release.version, base_version):
        return release
    name = (f"{SETUP_DELTA_PREFIX}{base_version}-to-v"
            f"{release.version}.exe")
    expected_url = (f"https://github.com/{REPO}/releases/download/"
                    f"v{release.version}/{name}")
    matching = [a for a in payload.get("assets", []) if isinstance(a, dict)
                and a.get("name") == name and a.get("state") == "uploaded"]
    if len(matching) != 1 or matching[0].get("browser_download_url") != expected_url:
        return release
    candidate = matching[0]
    digest = candidate.get("digest")
    match = HASH.fullmatch(digest) if isinstance(digest, str) else None
    size = candidate.get("size")
    if not match or type(size) is not int or not 0 < size < release.size:
        return release
    return replace(release, delta_url=expected_url, delta_digest=match.group(1),
                   delta_size=size, delta_base=base_version)


def selected_setup_download(release):
    """Return the actual asset metadata and mode; preserve full fallback."""
    if release.delta_size and release.delta_base:
        expected = (f"{SETUP_DELTA_PREFIX}{release.delta_base}-to-v"
                    f"{release.version}.exe")
        if release.delta_url.endswith("/" + expected):
            return (Release(release.version, release.delta_url,
                            release.delta_digest, release.delta_size), expected,
                    "setup-delta")
    return release, SETUP_ASSET, "setup"


def is_setup_delta_name(filename, version, source_version):
    if not isinstance(version, str) or not isinstance(source_version, str):
        return False
    try:
        parts_version(version)
        parts_version(source_version)
    except UpdateError:
        return False
    return filename == (
        f"{SETUP_DELTA_PREFIX}{source_version}-to-v{version}.exe"
    )


def summarize_release_changes(releases, installed, target):
    """Group release notes by version; never trust or render Markdown as HTML."""
    if not isinstance(releases, list):
        raise UpdateError("יומן הגרסאות אינו תקין")
    found = []
    seen = set()
    for item in releases:
        if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
            continue
        tag = item.get("tag_name")
        if not isinstance(tag, str) or not TAG.fullmatch(tag):
            continue
        version = tag[1:]
        if version in seen or not (is_newer(version, installed) and
                                   not is_newer(version, target)):
            continue
        seen.add(version)
        body = item.get("body")
        description = body[:10000].replace("\r", "") if isinstance(body, str) else ""
        found.append((version, description.strip() or "לא פורסם תיאור לגרסה זו"))
    found.sort(key=lambda row: parts_version(row[0]), reverse=True)
    return "\n\n".join(f"גרסה v{version}\n{body}" for version, body in found)[:24000]


def latest_release(asset_name=ASSET):
    from urllib.error import HTTPError
    try:
        with open_https(API) as response:
            raw = response.read(512_001)
            if len(raw) > 512_000:
                raise UpdateError("תגובת GitHub ארוכה מדי")
            payload = json.loads(raw)
            release = parse_release(payload, asset_name=asset_name)
        # A later update may skip several releases. A failure to load change
        # notes must never prevent the user from seeing a valid update.
        from . import __version__
        if asset_name == SETUP_ASSET:
            release = setup_delta_asset(payload, release, __version__)
        if is_newer(release.version, __version__):
            try:
                with open_https(API_HISTORY) as history_response:
                    history_raw = history_response.read(700_001)
                    if len(history_raw) > 700_000:
                        raise UpdateError("יומן גרסאות ארוך מדי")
                    notes = summarize_release_changes(
                        json.loads(history_raw), __version__, release.version)
                release = replace(release, notes=notes or release.notes)
            except (OSError, ValueError, UpdateError):
                pass
        return release
    except HTTPError as exc:
        if exc.code == 404:
            return None  # no releases published yet
        raise UpdateError(f"שגיאת GitHub: {exc.code}") from exc
    except (OSError, ValueError) as exc:
        raise UpdateError("לא ניתן לבדוק עדכונים כעת") from exc


def download_release(release, target):
    """The file is not trusted until both size and checksum match."""
    target = Path(target)
    digest = sha256()
    count = 0
    try:
        with open_https(release.url, timeout=30) as response, target.open("xb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > MAX_ZIP or count > release.size:
                    raise UpdateError("חבילת העדכון גדולה מהמידע שפורסם")
                digest.update(chunk)
                out.write(chunk)
        if count != release.size or digest.hexdigest() != release.digest:
            raise UpdateError("חתימת הקובץ לא תואמת ל־GitHub. העדכון בוטל")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def settings_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "AstroBirthChart" / "settings.json"


def _read_settings(path):
    """Read preferences defensively; malformed files have safe opt-out defaults."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def auto_updates_enabled(path=None):
    """Opt-in for checking on app launch; NEVER means automatic downloading."""
    return _read_settings(path or settings_path()).get("auto_updates") is True


def auto_install_enabled(path=None):
    """Opt-in for installation after an explicit Download click."""
    return _read_settings(path or settings_path()).get("auto_install") is True


def _save_setting(name, enabled, path=None):
    path = Path(path or settings_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    values = _read_settings(path)
    values[name] = bool(enabled)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8",
                                     prefix=".settings-", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(values, handle)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_auto_updates(enabled, path=None):
    _save_setting("auto_updates", enabled, path)


def save_auto_install(enabled, path=None):
    _save_setting("auto_install", enabled, path)


def extract_release(archive, installation, version):
    """Sibling staging, limits on size/count, no zip-slip/symlinks/collisions."""
    installation = Path(installation).resolve()
    if installation.name != "AstroBirthChart" or not (installation / EXE).is_file():
        raise UpdateError("עדכון אוטומטי דורש תיקיית התקנה AstroBirthChart תקינה")
    stage = Path(tempfile.mkdtemp(prefix=".astrochart-stage-", dir=installation.parent))
    try:
        with ZipFile(archive) as z:
            if len(z.infolist()) > 3000:
                raise UpdateError("מספר הקבצים בחבילה גדול מדי")
            total, seen = 0, set()
            for info in z.infolist():
                name = info.filename
                if name == "AstroBirthChart/" and info.is_dir():
                    continue
                if "\\" in name or "\x00" in name:
                    raise UpdateError("שם לא חוקי בחבילת עדכון")
                segments = name.rstrip("/").split("/")
                if len(segments) < 2 or segments[0] != "AstroBirthChart" or any(
                    p in ("", ".", "..") or ":" in p for p in segments):
                    raise UpdateError("מבנה תיקיות לא תקין בחבילת עדכון")
                rel = Path(*segments[1:])
                normalized = str(rel).casefold()
                if normalized in seen and not info.is_dir():
                    raise UpdateError("שם קובץ כפול בחבילת עדכון")
                seen.add(normalized)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise UpdateError("חבילת העדכון מכילה קישור סמלי")
                total += info.file_size
                if total > MAX_UNZIP:
                    raise UpdateError("חבילת העדכון גדולה מדי לאחר חילוץ")
                dest = stage / rel
                if info.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as source, dest.open("xb") as out:
                        shutil.copyfileobj(source, out, length=1024 * 1024)
        manifest = json.loads((stage / "version.json").read_text("utf-8"))
        if manifest != {"version": version, "platform": "windows-x64"}:
            raise UpdateError("קובץ העדכון מכיל גרסה אחרת")
        if not (stage / EXE).is_file() or not (stage / HELPER).is_file():
            raise UpdateError("קובצי הרצה חסרים בחבילת העדכון")
        if not (stage / "_internal/data/ephemeris/de440s.bsp").is_file():
            raise UpdateError("קובץ האפמריס חסר")
        return stage
    except (BadZipFile, OSError, ValueError, KeyError) as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise UpdateError("חבילת העדכון פגומה") from exc
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def install_directory():
    if not getattr(sys, "frozen", False):
        raise UpdateError("התקנת עדכון אוטומטית זמינה רק בגרסת EXE")
    return Path(sys.executable).resolve().parent


def launch_install(stage, installed, version):
    """Updater is copied OUTSIDE the install directory to unlock the EXE."""
    from astrochart import __version__
    installed, stage = Path(installed).resolve(), Path(stage).resolve()
    if not is_newer(version, __version__):
        raise UpdateError("גרסת העדכון אינה חדשה יותר")
    if stage.parent != installed.parent:
        raise UpdateError("תיקיית הכנת העדכון נמצאת בכונן אחר")
    helper = installed / HELPER
    if not helper.is_file():
        raise UpdateError("חסר רכיב העדכון העצמאי")
    location = Path(tempfile.mkdtemp(prefix="AstroChartUpdater-")) / HELPER
    shutil.copy2(helper, location)
    subprocess.Popen([str(location), "--apply", str(installed), str(stage),
                      str(os.getpid()), version], cwd=location.parent, close_fds=True)



def is_installed_setup(install_dir):
    """Official setup marker: never folder-swap a Windows-registered install."""
    directory = Path(install_dir)
    return (directory / INSTALLED_MARKER).is_file()


def launch_setup_install(downloaded_setup, installed, version, expected_digest, fallback_release=None):
    """Install with Inno Setup *without* invalidating Windows uninstall records.

    A separate helper waits for the application to exit, rechecks the already
    verified installer SHA-256 and invokes the genuine Inno Setup installer.
    """
    from astrochart import __version__
    installed = Path(installed).resolve()
    downloaded_setup = Path(downloaded_setup).resolve()
    if not is_newer(version, __version__):
        raise UpdateError("גרסת העדכון אינה חדשה יותר")
    if (not is_installed_setup(installed)
            or not (downloaded_setup.name == SETUP_ASSET or
                    is_setup_delta_name(downloaded_setup.name, version, __version__))
            or not downloaded_setup.is_file()
            or not HASH.fullmatch("sha256:" + str(expected_digest))):
        raise UpdateError("מתקין העדכון אינו מאומת או שההתקנה אינה רשומה ב־Windows")
    worker = installed / HELPER
    if not worker.is_file():
        raise UpdateError("רכיב העדכון העצמאי חסר")
    location = Path(tempfile.mkdtemp(prefix="AstroChartUpdater-")) / HELPER
    shutil.copy2(worker, location)
    command = [
        str(location), "--apply-setup", str(installed), str(downloaded_setup),
        str(os.getpid()), version, expected_digest
    ]
    if fallback_release is not None:
        expected_url = (f"https://github.com/{REPO}/releases/download/"
                        f"v{version}/{SETUP_ASSET}")
        if (downloaded_setup.name == SETUP_ASSET or
                fallback_release.version != version or
                fallback_release.url != expected_url or
                not HASH.fullmatch("sha256:" + fallback_release.digest) or
                type(fallback_release.size) is not int or
                not 0 < fallback_release.size <= MAX_ZIP):
            raise UpdateError("נתוני חבילת הגיבוי אינם תקינים")
        command.extend([fallback_release.url, fallback_release.digest,
                        str(fallback_release.size)])
    subprocess.Popen(command, cwd=location.parent, close_fds=True)
