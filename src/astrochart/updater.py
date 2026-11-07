"""Offline-first updater driven by GitHub Releases SHA256 asset digests.

No telemetry or personal data. GitHub HTTPS and the repository account are
the trust anchors: an account compromise requires separate code signing.
"""
from dataclasses import dataclass
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
ASSET = "AstroBirthChart-Windows-x64.zip"
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
                              if url == API else "application/octet-stream"}),
        timeout=timeout)


def parse_release(payload):
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise UpdateError("לא נמצאה גרסה יציבה")
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise UpdateError("תג גרסה לא תקין")
    expected_url = f"https://github.com/{REPO}/releases/download/{tag}/{ASSET}"
    items = [a for a in payload.get("assets", []) if isinstance(a, dict)
             and a.get("name") == ASSET and a.get("state") == "uploaded"]
    if len(items) != 1 or items[0].get("browser_download_url") != expected_url:
        raise UpdateError("קובץ העדכון חסר או שמקורו אינו מורשה")
    item = items[0]
    match = HASH.fullmatch(item.get("digest", ""))
    size = item.get("size")
    if not match or type(size) is not int or not 0 < size <= MAX_ZIP:
        raise UpdateError("העדכון חסר חותמת SHA-256 או גודל תקין")
    return Release(tag[1:], expected_url, match.group(1), size)


def latest_release():
    from urllib.error import HTTPError
    try:
        with open_https(API) as response:
            raw = response.read(512_001)
            if len(raw) > 512_000:
                raise UpdateError("תגובת GitHub ארוכה מדי")
            return parse_release(json.loads(raw))
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


def auto_updates_enabled(path=None):
    try:
        return json.loads(Path(path or settings_path()).read_text("utf-8")).get("auto_updates") is True
    except (OSError, ValueError, AttributeError):
        return False


def save_auto_updates(enabled, path=None):
    path = Path(path or settings_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8",
                                     prefix=".settings-", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump({"auto_updates": bool(enabled)}, handle)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
