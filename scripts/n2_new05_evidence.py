"""NEW-05-R3 audit evidence from real R1-selected witness groups.

This is a deterministic test-only report, not a new interpretation rule, a
modified R1 algorithm or a source-approved reading. It uses only synthetic
chart positions and an explicitly identified test-only catalog override.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import astrochart.semantics_n2 as semantic_engine
from astrochart.interpretation import load_rulepack
from astrochart.semantics_n2 import load_meaning_catalog
from test_n2_new05_production import (
    _generate, _input, _selected_route, _scenario, _assert_lineage,
)

DEST = ROOT / "qa-output" / "n2-new05-r3"


def write(name, model, report, text, hits, r1):
    _assert_lineage(model, report, hits, r1)
    (DEST / f"{name}-full-hebrew.txt").write_text(text+"\n", encoding="utf-8")
    (DEST / f"{name}-full-trace.json").write_text(
        json.dumps({"semantic": model, "narrative": report},
                   ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    matrix = []
    for n in (2, 3, 4, 5):
        for scenario in ("full", "partial", "missing", "indistinct"):
            hits, r1, catalog, target, rules = _scenario(n, scenario)
            model, report, text = _generate(hits, r1, catalog)
            name = f"path-{n}-{scenario}"
            write(name, model, report, text, hits, r1)
            decision = report["process_decisions"][0]
            matrix.append({
                "case": name, "source": (
                    "R1-authored-path" if n != 5
                    else "synthetic-5-member-R1-contract-using-real-witnesses"),
                "path": decision["path"],
                "selected_rule_ids": rules,
                "comparison": decision["comparison"],
                "combined_assertion": decision["combined_assertion"],
                "abstained_comparison": bool(report["abstained_processes"]),
            })

    # One report, 3 R1-produced paths; demonstrate missing, indistinct
    # and allowed-comparison-but-no-combined-assertion side by side.
    positions = [
        ("שמש", 12.4), ("מרקורי", 44.4), ("שבתאי", 288.4),
        ("ונוס", 139.4), ("ירח", 73.4),
        ("צדק", 164.4), ("מאדים", 223.4),
    ]
    hits, r1 = _input(positions)
    paths = [
        ["חשיבה", "תקשורת"],
        ["יצירתיות", "תקשורת"],
        ["יוזמה", "התמדה", "אחריות"],
    ]
    selected = [_selected_route(r1, p) for p in paths]
    assert all(selected)
    r1["summary"]["top_hypotheses"] = [node["id"] for node in selected]
    semantic_engine.MAX_PROCESSES = 3
    catalog = deepcopy(load_meaning_catalog())
    # Keep the original NEW-05 demonstration independent of PR29's expanded
    # catalog so its planned three distinct decisions remain reproducible.
    catalog["rule_readings"] = [r for r in catalog["rule_readings"]
                                if "interpretive_basis" not in r["provenance"]]
    rule = next(r for r in load_rulepack().rules if r["id"] == "venus-sign-5")
    original = next(r for r in catalog["rule_readings"]
                    if r["rule_id"] == "moon-sign-3")
    test_only = deepcopy(original)
    test_only.update({
        "id": "new05-fixture.venus-sign-5", "rule_id": "venus-sign-5",
        "axis": rule["axis"], "source_rule_text": rule["text"],
        "evidence_type": rule["type"],
    })
    catalog["rule_readings"].append(test_only)
    model, report, text = _generate(hits, r1, catalog)
    assert [x["comparison"]["reason"] for x in report["process_decisions"]] == [
        "missing-catalog-coverage", "no-meaningful-distinction",
        "documented-distinct-readings"]
    assert len(report["abstained_processes"]) == 2
    write("three-reasons-one-report", model, report, text, hits, r1)
    (DEST / "matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    paragraphs = [p for s in report["sections"] for p in s["paragraphs"]
                  if p["kind"] in ("process", "process-abstention")]
    sample = [
        "# NEW-05 R3 — production-chain example",
        "All inputs synthetic. This triple is selected from real R1-created "
        "nodes and uses one test-only unverified duplicate editorial reading.",
        "N2 comparisons do NOT justify a new combined-meaning assertion.",
        "## Full generated comparison paragraph (semantic + original evidence)",
        *(p["text"] for p in paragraphs if p["kind"] == "process"),
        "## Full generated grouped abstention paragraph",
        *(p["text"] for p in paragraphs if p["kind"] == "process-abstention"),
        "## All three process decision JSON objects",
        "```json",
        json.dumps(report["process_decisions"], ensure_ascii=False, indent=2),
        "```",
        "## Full-trace location",
        "three-reasons-one-report-full-trace.json (all original R1/N2 claims)",
    ]
    (DEST / "example-paragraphs-and-json.md").write_text(
        "\n\n".join(sample)+"\n", encoding="utf-8")
    print("N2_NEW05_R3_CHAIN_PASS", len(matrix),
          "path/scenario cases; 3 distinct decisions in one report")


if __name__ == "__main__":
    main()
