"""Fresh computed-map comparison: 26 rule readings versus 86 (same R1 evidence).

No earlier holdout cohorts are used for content tuning. --sealed is a second
new seed for independent post-freeze checking. This is software/editorial QA,
not scientific validation of the symbolic interpretation.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from astrochart.interpretation import interpret_chart
from astrochart.narrative_n2 import (
    compose_narrative_n2, format_narrative_n2, semantic_only_n2,
)
from astrochart.semantics_n2 import build_personality_model, load_meaning_catalog
from astrochart.synthesis import synthesize
from n2_holdout import actual_jpl_holdout, fixture

DEVELOPMENT_SEED = 2026111071
SEALED_SEED = 2026111123


def catalog_pair():
    expanded = load_meaning_catalog()
    baseline = deepcopy(expanded)
    baseline["rule_readings"] = [
        r for r in expanded["rule_readings"]
        if r["provenance"].get("interpretive_basis")
        != "unverified-original-rule-text-only"
    ]
    assert len(baseline["rule_readings"]) == 26
    assert len(expanded["rule_readings"]) == 86
    return baseline, expanded


def produce_pair(chart, baseline, expanded):
    hits = interpret_chart(chart)
    r1 = synthesize(chart, hits)
    before = build_personality_model(r1, hits, catalog=baseline)
    after = build_personality_model(r1, hits, catalog=expanded)
    before_report, after_report = (
        compose_narrative_n2(before), compose_narrative_n2(after))
    real_source = {h["rule_id"] for h in hits["signals"]}
    nodes = {n["id"] for n in r1["nodes"]}
    for model, report in ((before, before_report), (after, after_report)):
        assert all(set(c["rule_ids"]) <= real_source and
                   set(c["node_ids"]) <= nodes and c["source_review_statuses"]
                   for c in model["claims"])
        assert not model["relationship_discovery_enabled"]
        assert model["catalog_review_status"] == "unverified"
        for p in (p for s in report["sections"] for p in s["paragraphs"]
                  if p["claim_ids"]):
            related = [c for c in model["claims"] if c["id"] in p["claim_ids"]]
            for key in ("rule_ids", "node_ids", "source_refs", "meaning_ids",
                        "evidence_keys", "source_review_statuses"):
                assert p[key] == sorted({v for c in related for v in c[key]})
    return ({"model": before, "report": before_report},
            {"model": after, "report": after_report},
            sorted(real_source))


def main():
    sealed = "--sealed" in sys.argv
    seed = SEALED_SEED if sealed else DEVELOPMENT_SEED
    prefix = "sealed" if sealed else "development"
    target = ROOT / "qa-output" / ("n2-catalog-sealed" if sealed else "n2-catalog-impact")
    target.mkdir(parents=True, exist_ok=True)
    baseline, expanded = catalog_pair()
    charts = actual_jpl_holdout(seed=seed, count=16,
                                prefix="catalog-" + prefix + "-jpl")
    charts.update({
        "catalog-environment": fixture(("שמש", 102.8, None),
                                       ("ירח", 212.4, None)),
        "catalog-aesthetics": fixture(("ונוס", 284.4, None),
                                      ("מרקורי", 218.4, None)),
        "catalog-action": fixture(("מאדים", 342.4, None),
                                  ("צדק", 164.4, None)),
        "catalog-uncertain": fixture(("שמש", 102.8, None),
                                     ("ירח", 212.4, None), mode="unknown"),
    })
    rows, full = [], [
        "# N2 catalog expansion: full paired reports",
        f"New computed-map seed: {seed}; previously used N2 holdouts excluded.",
        "These texts are symbolic, editorial and unverified; they do not measure personality.",
    ]
    repeats_before, repeats_after = Counter(), Counter()
    for case, chart in charts.items():
        before, after, source = produce_pair(chart, baseline, expanded)
        for label, entry in (("before", before), ("after", after)):
            model, report = entry["model"], entry["report"]
            text = format_narrative_n2(report)
            (target / f"{case}-{label}-full.txt").write_text(
                text + "\n", encoding="utf-8")
            (target / f"{case}-{label}-trace.json").write_text(
                json.dumps({"semantic": model, "narrative": report},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            full.extend([f"## {case} — {label}", text])
            repetitions = repeats_before if label == "before" else repeats_after
            repetitions.update(semantic_only_n2(report))
        bp, ap = before["report"], after["report"]
        old_claims, new_claims = before["model"]["claims"], after["model"]["claims"]
        old_meaning = {c["content"]["selected_rule_id"] for c in old_claims
                       if c["kind"] == "axis-example"}
        new_meaning = {c["content"]["selected_rule_id"] for c in new_claims
                       if c["kind"] == "axis-example"}
        rows.append({
            "case": case, "time_mode": before["model"]["time_mode"],
            "source_rule_ids": source,
            "before_axis_meanings_displayed": len(old_meaning),
            "after_axis_meanings_displayed": len(new_meaning),
            "new_meaning_rules_displayed": sorted(new_meaning - old_meaning),
            "before_abstained_paths": len(bp["abstained_processes"]),
            "after_abstained_paths": len(ap["abstained_processes"]),
            "before_comparison_processes": sum(c["kind"] == "process-example"
                                              for c in old_claims),
            "after_comparison_processes": sum(c["kind"] == "process-example"
                                             for c in new_claims),
            "full_narrative_changed": format_narrative_n2(bp)
                                      != format_narrative_n2(ap),
            "source_rule_evidence_unchanged": True,
        })
        assert rows[-1]["after_abstained_paths"] <= rows[-1]["before_abstained_paths"]
    totals = {
        "seed": seed, "cases": len(rows),
        "real_jpl_charts": 16, "synthetic_controls": len(charts) - 16,
        "catalog_rules_before": 26, "catalog_rules_after": 86,
        "changed_reports": sum(r["full_narrative_changed"] for r in rows),
        "new_rule_meanings_displayed": len({
            rule for r in rows for rule in r["new_meaning_rules_displayed"]}),
        "abstentions_before": sum(r["before_abstained_paths"] for r in rows),
        "abstentions_after": sum(r["after_abstained_paths"] for r in rows),
        "comparison_processes_before": sum(r["before_comparison_processes"] for r in rows),
        "comparison_processes_after": sum(r["after_comparison_processes"] for r in rows),
        "exact_semantic_repeat_extras_before":
            sum(n - 1 for n in repeats_before.values() if n > 1),
        "exact_semantic_repeat_extras_after":
            sum(n - 1 for n in repeats_after.values() if n > 1),
        "source_and_node_lineage_verified": True,
        "editorial_review_status": "PENDING_INDEPENDENT",
    }
    assert totals["changed_reports"] > 0
    (target / "comparison-index.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "aggregate.json").write_text(
        json.dumps(totals, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "full-before-after.md").write_text(
        "\n\n".join(full) + "\n", encoding="utf-8")
    print("N2_CATALOG_IMPACT_PASS", json.dumps(totals, ensure_ascii=False))


if __name__ == "__main__":
    main()
