"""Standalone Windows update worker using only the Python standard library.

Copy the frozen onefile worker OUTSIDE the installed directory before launch.
Wait for the parent process, swap folders, keep old version, restart.
"""
import json
from hashlib import sha256
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import time
import uuid


class InstallationError(Exception):
    pass


def wait_for_process(pid, seconds=90):
    if os.name == "nt":
        import ctypes
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = dll.OpenProcess(0x00100000, False, pid)
        if not handle:
            return
        try:
            if dll.WaitForSingleObject(handle, int(seconds * 1000)) != 0:
                raise InstallationError("היישום הקודם לא נסגר")
        finally:
            dll.CloseHandle(handle)
    else:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.2)
        raise InstallationError("היישום הקודם לא נסגר")


def install(installed, stage, version, launch=None):
    installed, stage = Path(installed).resolve(), Path(stage).resolve()
    if (installed.name != "AstroBirthChart" or not installed.is_dir()
        or not stage.is_dir() or installed.parent != stage.parent):
        raise InstallationError("תיקיות ההתקנה אינן חוקיות")
    if not (stage / "AstroBirthChart.exe").is_file():
        raise InstallationError("קובץ EXE חסר")
    if not (stage / "AstroBirthChartUpdater.exe").is_file():
        raise InstallationError("רכיב עדכון חסר")
    data = json.loads((stage / "version.json").read_text(encoding="utf-8"))
    if data != {"version": version, "platform": "windows-x64"}:
        raise InstallationError("חוסר התאמה בגרסת העדכון")
    old = installed.parent / (".astrochart-backup-" + uuid.uuid4().hex)
    launch = launch or (lambda exe: subprocess.Popen([str(exe)], cwd=exe.parent))
    installed.rename(old)
    moved = False
    try:
        stage.rename(installed)
        moved = True
        launch(installed / "AstroBirthChart.exe")
        return old
    except BaseException:
        if moved and installed.is_dir():
            shutil.rmtree(installed)
        old.rename(installed)
        raise



def install_setup(installed, setup, version, expected_digest, invoke=None):
    """Use Inno Setup for registered installs. Never folder-swap uninstall logs."""
    installed, setup = Path(installed).resolve(), Path(setup).resolve()
    delta = re.fullmatch(
        r"AstroBirthChart-Setup-Delta-from-v([0-9]+\.[0-9]+\.[0-9]+)-to-v([0-9]+\.[0-9]+\.[0-9]+)\.exe",
        setup.name)
    if (delta is not None and delta.group(2) != version):
        raise InstallationError("גרסת חבילת העדכון החלקי אינה תואמת")
    if delta is not None:
        try:
            base = json.loads((installed / "version.json").read_text("utf-8"))
        except (OSError, ValueError) as exc:
            raise InstallationError("אין אפשרות לזהות את גרסת המקור") from exc
        if base != {"version": delta.group(1), "platform": "windows-x64"}:
            raise InstallationError("גרסת המקור אינה תואמת לעדכון החלקי")
    if (installed.name != "AstroBirthChart"
        or not (installed / "installed-by-setup.marker").is_file()
        or (setup.name != "AstroBirthChart-Setup.exe" and delta is None)
        or not setup.is_file()):
        raise InstallationError("נתיב התקנה או קובץ מתקין אינם תקינים")
    if len(expected_digest) != 64 or any(c not in "0123456789abcdef" for c in expected_digest):
        raise InstallationError("חתימת העדכון אינה תקינה")
    checksum = sha256()
    with setup.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            checksum.update(chunk)
    if checksum.hexdigest() != expected_digest:
        raise InstallationError("אימות קובץ ההתקנה נכשל")
    arguments = [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                 "/NORESTART", "/SP-", "/DIR=" + str(installed)]
    if invoke is None:
        invoke = lambda command: subprocess.run(
            command, cwd=setup.parent, check=True, timeout=600)
    invoke(arguments)
    metadata = json.loads((installed / "version.json").read_text(encoding="utf-8"))
    if metadata != {"version": version, "platform": "windows-x64"}:
        raise InstallationError("הגרסה שהותקנה אינה תואמת לעדכון")
    if not (installed / "AstroBirthChart.exe").is_file():
        raise InstallationError("קובץ התוכנה חסר לאחר העדכון")
    return installed


def log_error(exc):
    folder = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "AstroBirthChart"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "update-error.txt").write_text(str(exc), encoding="utf-8")


class HttpsOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise InstallationError("Full fallback tried an insecure redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_full_fallback(version, url, expected_digest, expected_size):
    """Only the public, version-pinned GitHub Setup asset; verify every byte."""
    repository = "toyro396133/astro-birth-chart-windows"
    expected_url = (
        f"https://github.com/{repository}/releases/download/v{version}/"
        "AstroBirthChart-Setup.exe")
    if url != expected_url or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise InstallationError("Untrusted full-installer fallback metadata")
    try:
        size = int(expected_size)
    except (TypeError, ValueError) as exc:
        raise InstallationError("Invalid fallback size") from exc
    if not 0 < size <= 350_000_000 or str(size) != str(expected_size):
        raise InstallationError("Invalid fallback file size")
    temporary = Path(tempfile.mkdtemp(prefix="AstroChart-Fallback-")) / "AstroBirthChart-Setup.exe"
    digest = sha256()
    count = 0
    try:
        opener = build_opener(HttpsOnlyRedirect())
        with opener.open(
                Request(url, headers={"User-Agent": "AstroBirthChart/Updater"}),
                timeout=30) as source, temporary.open("xb") as target:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                count += len(block)
                if count > size:
                    raise InstallationError("Full-installer fallback exceeds published size")
                digest.update(block)
                target.write(block)
        if count != size or digest.hexdigest() != expected_digest:
            raise InstallationError("Full-installer fallback digest differs")
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        temporary.parent.rmdir()
        raise


def main(args):
    if args == ["--self-test"]:
        print("UPDATER_WORKER_OK")
        return 0
    try:
        if len(args) in (6, 9) and args[0] == "--apply-setup":
            _, installed, setup, pid_text, version, digest = args[:6]
            wait_for_process(int(pid_text))
            try:
                folder = install_setup(installed, setup, version, digest)
            except Exception:
                # A delta may be incompatible with modified local files.
                # The full installer has its own published SHA256 and size.
                if len(args) != 9 or "AstroBirthChart-Setup-Delta-from-v" not in Path(setup).name:
                    raise
                fallback = download_full_fallback(version, *args[6:])
                try:
                    folder = install_setup(installed, fallback, version, args[7])
                finally:
                    fallback.unlink(missing_ok=True)
                    fallback.parent.rmdir()
            subprocess.Popen([str(folder / "AstroBirthChart.exe")], cwd=folder)
            return 0
        if len(args) == 5 and args[0] == "--apply":
            _, installed, staging, pid_text, version = args
            wait_for_process(int(pid_text))
            install(installed, staging, version)
            return 0
        print("Usage: updater --apply INSTALL STAGE PID VERSION "
              "| --apply-setup INSTALL SETUP PID VERSION SHA256")
        return 2
    except Exception as exc:
        log_error(exc)
        return 1

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
