"""Emit a version descriptor alongside the frozen app after build."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from astrochart import __version__

if __name__ == "__main__":
    target = root / "dist" / "AstroBirthChart" / "version.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"version": __version__, "platform": "windows-x64"}, indent=2),
        encoding="utf-8"
    )
    print("Built version manifest:", __version__)
