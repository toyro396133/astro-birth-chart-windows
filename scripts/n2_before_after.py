"""Produce complete old/new N2 reports from the audited commit, without sealed tuning.

The original six synthetic comparison fixtures are run in an isolated git
worktree at the failing baseline SHA; current results come from the same
fixtures on the current branch. All texts and trace JSON are retained.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "d40b55ce3cf7730ff8ce4f554d0b92fb7c392592"
DEST = ROOT / "qa-output" / "n2-before-after"


def call(*args, cwd=ROOT):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout


def main():
    baseline_dir = Path(tempfile.mkdtemp(prefix="astro-n2-baseline-")).resolve()
    shutil.rmtree(baseline_dir)
    try:
        call("git", "worktree", "add", "--detach", str(baseline_dir), BASELINE)
        call(sys.executable, str(baseline_dir / "scripts" / "n2_comparison.py"),
             cwd=baseline_dir)
        before = baseline_dir / "qa-output" / "n2-comparison"
        after = ROOT / "qa-output" / "n2-comparison"
        DEST.mkdir(parents=True, exist_ok=True)
        comparisons = []
        for old_file in sorted(before.glob("*-n2.txt")):
            name = old_file.name.removesuffix("-n2.txt")
            current_file = after / old_file.name
            if not current_file.exists():
                raise FileNotFoundError(current_file)
            original = old_file.read_text(encoding="utf-8").strip()
            revised = current_file.read_text(encoding="utf-8").strip()
            old_trace = json.loads((before / f"{name}-trace.json").read_text(
                encoding="utf-8"))
            new_trace = json.loads((after / f"{name}-trace.json").read_text(
                encoding="utf-8"))
            semantic_old = [
                p["semantic_text"] for s in old_trace["narrative"]["sections"]
                for p in s["paragraphs"] if p["kind"] in ("axis", "process")]
            semantic_new = [
                p["semantic_text"] for s in new_trace["narrative"]["sections"]
                for p in s["paragraphs"] if p["kind"] in ("axis", "process",
                                                        "process-abstention")]
            for label, text in (("before", original), ("after", revised)):
                (DEST / f"{name}-{label}-n2.txt").write_text(
                    text + "\n", encoding="utf-8")
            for label, trace in (("before", old_trace), ("after", new_trace)):
                (DEST / f"{name}-{label}-trace.json").write_text(json.dumps(
                    trace, ensure_ascii=False, indent=2), encoding="utf-8")
            comparisons.append({
                "case": name, "baseline_sha": BASELINE,
                "before_semantic_paragraphs": semantic_old,
                "after_semantic_paragraphs": semantic_new,
                "meaning_changed": semantic_old != semantic_new,
                "before_n2_full_file": f"{name}-before-n2.txt",
                "after_n2_full_file": f"{name}-after-n2.txt",
                "before_trace": f"{name}-before-trace.json",
                "after_trace": f"{name}-after-trace.json",
            })
        (DEST / "comparison-index.json").write_text(json.dumps(
            comparisons, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown = [
            "# N2 — Full baseline versus revised Hebrew reports",
            f"Baseline SHA: " + BASELINE,
            "All inputs are synthetic fixtures, not real people. "
            "These pairs are regression evidence, not a blind semantic review.",
        ]
        for item in comparisons:
            name = item["case"]
            old = (DEST / f"{name}-before-n2.txt").read_text(encoding="utf-8")
            new = (DEST / f"{name}-after-n2.txt").read_text(encoding="utf-8")
            markdown += [
                f"## {name}", "### BEFORE — complete N2 report",
                old, "### AFTER — complete N2 report", new,
            ]
        (DEST / "full-before-after.md").write_text(
            "\n\n".join(markdown) + "\n", encoding="utf-8")
        assert len(comparisons) == 6
        print("N2_BEFORE_AFTER_PASS", len(comparisons),
              "complete N2 pairs and evidence traces")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force",
                        str(baseline_dir)], cwd=ROOT, check=False,
                       capture_output=True)
        if baseline_dir.exists():
            shutil.rmtree(baseline_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
