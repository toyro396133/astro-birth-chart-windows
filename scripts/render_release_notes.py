"""Generate official GitHub Release notes from the approved package journal."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from astrochart.changelog import render_release_notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(
        render_release_notes(args.version), encoding="utf-8")


if __name__ == "__main__":
    main()
