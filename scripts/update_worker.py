"""Standalone Windows update worker using only the Python standard library.

Copy the frozen onefile worker OUTSIDE the installed directory before launch.
Wait for the parent process, swap folders, keep old version, restart.
"""
import json
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


def main(args):
    if args == ["--self-test"]:
        print("UPDATER_WORKER_OK")
        return 0
    if len(args) != 5 or args[0] != "--apply":
        print("Usage: updater --apply INSTALL STAGE PID VERSION")
        return 2
    _, installed, stage, pid_text, version = args
    try:
        wait_for_process(int(pid_text))
        install(installed, stage, version)
        return 0
    except Exception as exc:
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "AstroBirthChart"
        base.mkdir(parents=True, exist_ok=True)
        (base / "update-error.txt").write_text(str(exc), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
