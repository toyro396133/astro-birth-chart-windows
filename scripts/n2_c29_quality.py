"""C29 repair verification: identical charts on failing 9a8896a and revised code.

Uses a fresh deterministic cohort (NOT the old signed N2 holdout), plus
explicit rule-hit probes for all 9 problematic and 10 previously unobserved
rules. Writes full before/after text, JSON provenance and meaningful-coverage
metrics; never tunes content or accepts its own language quality.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA = "9a8896a4832f2ac78120268510f9de05641f41e3"
QA = ROOT / "qa-output" / "n2-c29-recheck"
NEW_SEED = 2026111297
TARGETS = [
    "sun-moon-trine", "venus-mars-trine", "moon-house-4",
    "moon-jupiter-trine", "venus-house-2", "jupiter-house-9",
    "mercury-sign-9", "venus-sign-10", "saturn-sign-1",
    "mercury-sign-3", "mercury-sign-4", "mercury-sign-11",
    "venus-sign-12", "mars-sign-1", "mars-sign-9",
    "jupiter-sign-1", "jupiter-sign-9", "saturn-sign-11",
]


def evaluate(checkout: Path, out: Path) -> None:
    # Imports are deliberately delayed until sys.path points at the chosen
    # exact source SHA, even though this worker file lives in the new branch.
    sys.path.insert(0, str(checkout / "src"))
    sys.path.insert(0, str(checkout / "scripts"))
    from astrochart.domain import BodyPosition, Chart, SIGNS, calculate_aspects
    from astrochart.interpretation import load_rulepack, interpret_chart
    from astrochart.synthesis import synthesize
    from astrochart.semantics_n2 import build_personality_model
    from astrochart.narrative_n2 import compose_narrative_n2, format_narrative_n2
    from n2_holdout import actual_jpl_holdout

    def target_chart(rule):
        when = rule["when"]
        if rule["type"] == "placement":
            index = SIGNS.index(when["sign"])
            bodies = [BodyPosition(when["body"], index * 30 + 12, False, (index,))]
        elif rule["type"] == "house":
            bodies = [BodyPosition(when["body"], 12, False, (0,),
                                   house=when["house"])]
        else:
            assert when["kind"] == "משולש"
            bodies = [BodyPosition(when["pair"][0], 12, False, (0,)),
                      BodyPosition(when["pair"][1], 132, False, (4,))]
        return Chart(bodies, calculate_aspects(bodies), None, None, False, [],
                     time_certainty="known")

    rules = {r["id"]: r for r in load_rulepack().rules}
    samples = actual_jpl_holdout(seed=NEW_SEED, count=12, prefix="fresh-jpl")
    samples.update({f"focus-{rid}": target_chart(rules[rid]) for rid in TARGETS})
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, chart in sorted(samples.items()):
        original = interpret_chart(chart)
        r1 = synthesize(chart, original)
        semantics = build_personality_model(r1, original)
        narrative = compose_narrative_n2(semantics)
        if name.startswith("focus-"):
            required = name.removeprefix("focus-")
            assert required in {h["rule_id"] for h in original["signals"]}, name
        text = format_narrative_n2(narrative)
        (out / f"{name}-full.txt").write_text(text + "\n", encoding="utf-8")
        trace = {"source_rule_ids": sorted({h["rule_id"] for h in original["signals"]}),
                 "r1_nodes": [n["id"] for n in r1["nodes"]],
                 "semantics": semantics, "narrative": narrative}
        (out / f"{name}-trace.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        process = [p for section in narrative["sections"] for p in section["paragraphs"]
                   if p["kind"] in ("process", "process-redundancy")]
        rows.append({
            "case": name, "source_rule_ids": trace["source_rule_ids"],
            "source_semantic_version": semantics["semantic_version"],
            "axis_example_rules": sorted({c["content"]["selected_rule_id"]
                  for c in semantics["claims"] if c["kind"] == "axis-example"}),
            "process_paragraphs": len([p for p in process if p["kind"] == "process"]),
            "process_redundancy_paragraphs": len([
                p for p in process if p["kind"] == "process-redundancy"]),
            "process_decisions": narrative.get("process_decisions", []),
            "suppressed_redundant_processes":
                len(narrative.get("suppressed_redundant_processes", [])),
            "abstentions": len(narrative["abstained_processes"]),
            "full_text_bytes": len(text.encode("utf-8")),
        })
    (out / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                     encoding="utf-8")


def report() -> None:
    old, new = QA / "failing-9a8896", QA / "repaired"
    a = {v["case"]: v for v in json.loads((old / "index.json").read_text("utf-8"))}
    b = {v["case"]: v for v in json.loads((new / "index.json").read_text("utf-8"))}
    assert set(a) == set(b) and len(a) == 30
    pairs = []
    full = ["# C29 — Complete before/after Hebrew reports",
            "Old code: " + BASELINE_SHA,
            "New code: current PR29 SHA; same fresh synthetic and computed chart inputs.",
            "Not empirical validation, and not the earlier sealed cohort."]
    before_process, after_process, redundant = Counter(), Counter(), Counter()
    source_signatures, conceptual_operations = Counter(), Counter()
    for name in sorted(a):
        before, after = a[name], b[name]
        assert before["source_rule_ids"] == after["source_rule_ids"], name
        old_text = (old / f"{name}-full.txt").read_text("utf-8")
        new_text = (new / f"{name}-full.txt").read_text("utf-8")
        full.extend([f"## {name}", "### Before", old_text,
                     "### After", new_text])
        before_process.update({"presented":before["process_paragraphs"]})
        after_process.update({"presented":after["process_paragraphs"]})
        redundant.update({"suppressed":after["suppressed_redundant_processes"]})
        for record in after["process_decisions"]:
            signature = tuple(sorted(zip(
                record["rule_ids"], record["evidence_keys"])))
            source_signatures[signature] += 1
            # This is a *structural* operation, not a lexical similarity.
            conceptual_operations[("list-focus-context-boundaries"
                                   if record["presentation"]["display"]
                                   else record["presentation"]["reason"])] += 1
        pairs.append({
            "case": name,
            "same_source_rule_ids": True,
            "full_text_changed": old_text != new_text,
            "before_axis_rules": before["axis_example_rules"],
            "after_axis_rules": after["axis_example_rules"],
            "before_displayed_processes": before["process_paragraphs"],
            "after_displayed_processes": after["process_paragraphs"],
            "after_suppressed": after["suppressed_redundant_processes"],
            "before_abstentions": before["abstentions"],
            "after_abstentions": after["abstentions"],
            "files": {
                "before": f"failing-9a8896/{name}-full.txt",
                "after": f"repaired/{name}-full.txt",
                "before_trace": f"failing-9a8896/{name}-trace.json",
                "after_trace": f"repaired/{name}-trace.json",
            },
        })
        if name.startswith("focus-") and name.removeprefix("focus-") in {
            "sun-moon-trine", "venus-mars-trine", "moon-house-4",
            "moon-jupiter-trine", "venus-house-2", "jupiter-house-9",
            "mercury-sign-9", "venus-sign-10", "saturn-sign-1",
        }:
            assert name.removeprefix("focus-") not in after["axis_example_rules"]
    metrics = {
        "base_sha": BASELINE_SHA, "new_seed": NEW_SEED,
        "fresh_computed_jpl_charts": 12, "focused_rule_probes": len(TARGETS),
        "total_unique_cases": len(pairs),
        "old_sealed_dataset_used_for_tuning": False,
        "before_process_paragraphs": before_process["presented"],
        "after_process_paragraphs": after_process["presented"],
        "after_suppressed_redundant_comparisons": redundant["suppressed"],
        "repeated_exact_selected_rule_evidence_pairs": sum(
            x - 1 for x in source_signatures.values() if x > 1),
        "distinct_selected_rule_evidence_signature_count": len(source_signatures),
        "comparison_operation_classes": dict(conceptual_operations),
        "changed_reports": sum(x["full_text_changed"] for x in pairs),
        "source_rule_sets_unchanged": True,
        "editorial_quality_not_accepted": True,
    }
    (QA / "before-after-index.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    (QA / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (QA / "all-full-before-after.md").write_text(
        "\n\n".join(full) + "\n", encoding="utf-8")
    print("C29_BEFORE_AFTER_PASS", json.dumps(metrics, ensure_ascii=False))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        assert len(sys.argv) == 4
        evaluate(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
        return
    previous = Path(tempfile.mkdtemp(prefix="c29-failing-")).resolve()
    shutil.rmtree(previous)
    try:
        subprocess.run(["git", "worktree", "add", "--detach", str(previous),
                        BASELINE_SHA], cwd=ROOT, check=True)
        binary = ROOT / "data" / "ephemeris" / "de440s.bsp"
        if binary.is_file():
            other = previous / "data" / "ephemeris" / binary.name
            other.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, other)
        for checkout, target in ((previous, QA / "failing-9a8896"),
                                 (ROOT, QA / "repaired")):
            subprocess.run([sys.executable, str(ROOT / "scripts" / "n2_c29_quality.py"),
                            "--worker", str(checkout), str(target)],
                           cwd=checkout, check=True)
        report()
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(previous)],
                       cwd=ROOT, check=False, capture_output=True)
        shutil.rmtree(previous, ignore_errors=True)


if __name__ == "__main__":
    main()
