"""Verify the exact GitHub release ZIP layout and internal version descriptor."""
import json
from pathlib import Path
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from astrochart import __version__


def verify(path: Path) -> None:
    with ZipFile(path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError(f"Corrupt release ZIP entry: {corrupt}")
        names = set(archive.namelist())
        mandatory = {
            "AstroBirthChart/AstroBirthChart.exe",
            "AstroBirthChart/AstroBirthChartUpdater.exe",
            "AstroBirthChart/version.json",
            "AstroBirthChart/_internal/data/ephemeris/de440s.bsp",
        }
        absent = mandatory - names
        if absent:
            raise ValueError(f"Missing mandatory distribution files: {absent}")
        for name in names:
            if not name.startswith("AstroBirthChart/"):
                raise ValueError(f"Unexpected archive path: {name}")
        metadata = json.loads(archive.read("AstroBirthChart/version.json"))
        if metadata != {"version": __version__, "platform": "windows-x64"}:
            raise ValueError(f"Bad release manifest: {metadata}")
    print(f"WINDOWS_RELEASE_ZIP_OK: {path.name} v{__version__}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/verify_release_zip.py ARCHIVE.zip")
    verify(Path(sys.argv[1]))
