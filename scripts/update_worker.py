"""Standalone Windows update worker using only the Python standard library.

Copy the frozen onefile worker OUTSIDE the installed directory before launch.
Wait for the parent process, swap folders, keep old version, restart.
"""
import json
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import sys
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
    if (installed.name != "AstroBirthChart"
        or not (installed / "installed-by-setup.marker").is_file()
        or setup.name != "AstroBirthChart-Setup.exe" or not setup.is_file()):
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


def main(args):
    if args == ["--self-test"]:
        print("UPDATER_WORKER_OK")
        return 0
    try:
        if len(args) == 6 and args[0] == "--apply-setup":
            _, installed, setup, pid_text, version, digest = args
            wait_for_process(int(pid_text))
            folder = install_setup(installed, setup, version, digest)
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
