"""Post-freeze N2 acceptance: NEW seed; never tune against sealed JPL cases.

Produces full N1/N2 Hebrew, semantic-only text, claim/provenance JSON,
independent rule-coverage impact, and verifiable quantitative safety gates.
Language quality and depth still require independent human review.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import sys

from n2_holdout import actual_jpl_holdout, evaluate, fixture
from n2_comparison import produce
from astrochart.interpretation import load_rulepack
from astrochart.semantics_n2 import load_meaning_catalog

ROOT = Path(__file__).resolve().parents[1] / "qa-output" / "n2-acceptance"
ACCEPTANCE_SEED = 2026110863  # development verification after instrumentation
FINAL_ACCEPTANCE_SEED = 2026110891  # frozen code, new untouched acceptance input


def controls():
    return {
        "new-two-readings": fixture(
            ("שמש", 254.4, None), ("מרקורי", 51.2, None), ("מאדים", 51.2, None)),
        "new-one-reading": fixture(
            ("שמש", 254.4, None), ("מרקורי", 51.2, None)),
        "new-opposite-reading": fixture(
            ("שמש", 254.4, None), ("מאדים", 51.2, None)),
        "new-time-known": fixture(("שמש", 118.6, 10), ("שבתאי", 294.2, None)),
        "new-time-estimated": fixture(
            ("שמש", 118.6, None), ("שבתאי", 294.2, None), mode="estimated"),
        "new-time-unknown": fixture(
            ("שמש", 118.6, None), ("שבתאי", 294.2, None), mode="unknown"),
    }


def audit(reports, *, seed):
    all_claims, all_paragraphs, processes = 0, 0, 0
    partial, complete, abstained, missing, comparisons = 0, 0, 0, 0, 0
    example_counts = []
    selected_rules, absent_path_rules, active_rules = Counter(), Counter(), Counter()
    semantic_texts = Counter()
    for name, report in reports.items():
        model, narrative = report["semantic"], report["narrative_n2"]
        claims = {c["id"]: c for c in model["claims"]}
        all_claims += len(claims)
        active_rules.update(set(report["source_rule_ids"]))
        for c in claims.values():
            if c["kind"] == "axis-meaning":
                example_counts.append({
                    "case": name, "axis": c["axis"],
                    "independent_evidence_count": c["content"]["independent_evidence_count"],
                    "rule_conditioned_coverage": c["content"]["rule_conditioned_coverage"],
                })
            if c["kind"] == "process-reading":
                processes += 1
                plan = c["content"]["content_plan"]
                path, members = plan["path"], plan["members"]
                assert len(path) == len(members)
                assert path == [m["axis"] for m in members]
                assert all(m["selected_witness"]["rule_id"] == m["selected_rule_id"]
                           for m in members)
                assert not plan["new_cross_axis_assertion_supported"]
                assert not any(x["licensed_as"] != "comparison-only"
                               for x in plan["distinctions"])
                assert plan["synthesis_status"] == "hypothesis-not-proven"
                for member in members:
                    selected_rules[member["selected_rule_id"]] += 1
                    if not member["meaning_covered"]:
                        absent_path_rules[member["selected_rule_id"]] += 1
                coverage = plan["coverage"]
                missing += len(coverage["missing_members"])
                complete += int(coverage["complete"])
                partial += int(not coverage["complete"]
                               and coverage["covered_members"] >= 2)
            if c["kind"] == "process-example":
                comparisons += 1
                assert c["content"]["reading_type"] == "attributed-comparison-not-new-edge"
        for section in narrative["sections"]:
            for p in section["paragraphs"]:
                all_paragraphs += 1
                assert set(p["claim_ids"]) <= set(claims)
                # Editorial disclosures may carry a status summary without
                # citing an individual claim; attribution unions only apply
                # to evidence-backed paragraphs.
                if p["claim_ids"]:
                    for key in ("node_ids", "rule_ids", "source_refs",
                                "source_review_statuses", "evidence_keys",
                                "evidence_roots", "meaning_ids"):
                        assert p[key] == sorted({
                            value for cid in p["claim_ids"]
                            for value in claims[cid].get(key, [])
                        }), (name, key)
                if p["kind"] in ("axis", "process", "process-abstention"):
                    semantic_texts[p["semantic_text"]] += 1
                if p["kind"] == "process":
                    cp = p["process_content_plan"]
                    if not cp["coverage"]["complete"]:
                        assert "השוואה חלקית בלבד" in p["semantic_text"]
                        for m in cp["coverage"]["missing_members"]:
                            assert m["axis"] in p["semantic_text"]
        abstained += len(narrative["abstained_processes"])
        for a in narrative["abstained_processes"]:
            assert set(a["claim_ids"]) <= set(claims)
            assert a["path"] and a["coverage"]["covered_members"] <= a["coverage"]["total_members"]
    rules = {r["id"]: r for r in load_rulepack().rules}
    curated = {r["rule_id"] for r in load_meaning_catalog()["rule_readings"]}
    assert len(rules) == 96 and len(curated) == 26
    uncovered = []
    for rid, rule in sorted(rules.items()):
        if rid in curated:
            continue
        txt = rule.get("text", "")
        # Mechanical triage signal, NOT an automatic editorial judgment.
        source_has_symbolic_language = any(
            s in txt for s in ("סמל", "משמש", "נתפס", "מתאר", "נקשר", "מייצג"))
        uncovered.append({
            "rule_id": rid, "axis": rule.get("axis"), "evidence_type": rule.get("type"),
            "review_status": rule.get("review_status", "unverified"),
            "original_rule_text": txt,
            "encounters_in_new_reports": active_rules[rid],
            "selected_as_r1_path_witness": selected_rules[rid],
            "selected_without_editorial_meaning": absent_path_rules[rid],
            "editorial_triage": ("original-symbolic-language-present-review-needed"
                                 if source_has_symbolic_language
                                 else "requires-editorial-research"),
            "automatic_meaning_added": False,
        })
    assert len(uncovered) == 70
    return {
        "acceptance_seed": seed, "cases": len(reports),
        "source": "new JPL charts and new synthetic controls; not an empirical validation",
        "full_provenanced_claims": all_claims, "narrative_paragraphs": all_paragraphs,
        "r1_paths": processes, "fully_covered_paths": complete,
        "partially_covered_paths": partial, "missing_path_members": missing,
        "abstained_paths": abstained, "comparison_claims": comparisons,
        "axis_reading_counts": example_counts,
        "semantic_exact_repeat_extras": sum(v - 1 for v in semantic_texts.values() if v > 1),
        "uncovered_rule_count": len(uncovered), "uncovered_rule_impact": uncovered,
        "fidelity_gate": "PASS", "semantic_depth_human_review": "PENDING_INDEPENDENT",
        "natural_hebrew_human_review": "PENDING_INDEPENDENT",
    }


def main():
    final = "--final" in sys.argv
    seed = FINAL_ACCEPTANCE_SEED if final else ACCEPTANCE_SEED
    root = ROOT.parent / ("n2-final-acceptance" if final else "n2-acceptance")
    charts = actual_jpl_holdout(seed=seed, count=12,
                                prefix="jpl-new-final" if final else "jpl-accept-new")
    charts.update(controls())
    metrics = evaluate(root, charts, check_pairs=False, seed=seed)
    reports = {name: produce(chart) for name, chart in charts.items()}
    # Unresolved polarity is intentionally an extra fixture, not a real chart.
    conflict = produce(fixture(("שמש", 16.6, None)), conflict=True)
    reports["new-opposing-fixture"] = conflict
    (root / "new-opposing-fixture-n2.txt").write_text(
        conflict["n2"] + "\n", encoding="utf-8")
    (root / "new-opposing-fixture-trace.json").write_text(json.dumps({
        "semantics": conflict["semantic"], "narrative": conflict["narrative_n2"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    result = audit(reports, seed=seed)
    assert any(c["kind"] == "unresolved-tension"
               for c in conflict["semantic"]["claims"])
    (root / "acceptance-quality.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "uncovered-rules-impact.json").write_text(
        json.dumps(result["uncovered_rule_impact"], ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("N2_FINAL_ACCEPTANCE_PASS" if final else "N2_NEW_ACCEPTANCE_PASS",
          len(reports), "cases",
          "new JPL", metrics["real_jpl_charts"],
          "paths", result["r1_paths"], "uncovered", result["uncovered_rule_count"])


if __name__ == "__main__":
    main()
