"""Create an optional portable delta between two already-built release ZIPs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from astrochart.delta_updates import create_delta


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: create_delta.py PREVIOUS.zip CURRENT.zip DELTA.zip")
    output = create_delta(*(Path(p) for p in sys.argv[1:]))
    if output is None:
        print("DELTA_SKIPPED: delta is not smaller than the full release")
    else:
        print(f"DELTA_READY: {output.name} ({output.stat().st_size} bytes)")
