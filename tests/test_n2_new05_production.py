"""NEW-05 R3: actual chart -> original RuleHits/R1 -> N2 -> Hebrew/JSON.

The 5-member case is an R1-contract fixture composed of five real, independently
validated R1 axis witness groups: today's R1 authored transition ontology
contains no five-member path. No custom or unsupported RuleHits are injected.
"""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

import astrochart.semantics_n2 as semantic_engine
from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.narrative_n2 import compose_narrative_n2, format_narrative_n2
from astrochart.semantics_n2 import build_personality_model, load_meaning_catalog
from astrochart.synthesis import synthesize


ROUTES = {
    2: (["יצירתיות", "תקשורת"],
        [("ונוס", 139.4), ("ירח", 73.4)]),
    3: (["יוזמה", "התמדה", "אחריות"],
        [("שמש", 12.4), ("מרקורי", 44.4), ("שבתאי", 288.4)]),
    4: (["יוזמה", "גמישות", "התמדה", "אחריות"],
        [("שמש", 12.4), ("מרקורי", 253.4),
         ("מאדים", 44.4), ("שבתאי", 288.4)]),
    5: (["יוזמה", "גמישות", "יציבות", "התמדה", "אחריות"],
        [("שמש", 12.4), ("מרקורי", 253.4), ("ירח", 44.4),
         ("מאדים", 44.4), ("שבתאי", 288.4)]),
}


def _input(positions, *, time_mode="known"):
    chart = Chart([
        BodyPosition(name, degree, False, (int(degree // 30),))
        for name, degree in positions
    ], [], None, None, time_mode == "unknown", [], time_certainty=time_mode)
    hits = interpret_chart(chart)
    r1 = synthesize(chart, hits)
    return hits, r1


def _selected_route(r1, path):
    return next((n for n in r1["nodes"]
                 if n["type"] == "synthesis" and n["path"] == path), None)


def _inject_five_member_contract_node(r1, path):
    """Reuse genuine axis facts, not claims or manufactured source attestations."""
    axes = {n["axis"]: n for n in r1["nodes"] if n["type"] == "axis"}
    assert set(path) <= set(axes)
    witnesses = [axes[axis]["available_facts"][0] for axis in path]
    roots = [root for w in witnesses for root in w["roots"]]
    assert len(set(roots)) == len(roots)  # no duplicate physical dependency
    template = next(n for n in r1["nodes"] if n["type"] == "synthesis")
    record = deepcopy(template)
    record.update({
        "id": "n2-new05-five-member-contract",
        "path": list(path), "level": len(path)-1,
        "domain": "ביצוע", "relation": "functional-composition",
        "selected_witnesses_by_axis": dict(zip(path, witnesses)),
        "independent_facts": witnesses,
        "evidence_roots": sorted(set(roots)),
        "rule_ids": sorted({rid for w in witnesses for rid in w["rule_ids"]}),
        "source_refs": sorted({url for w in witnesses for url in w["source_refs"]}),
        "source_review_statuses": sorted({
            status for w in witnesses for status in w["review_statuses"]}),
        "proof_search": {"complete": True, "states": 0, "limit": 20000},
        "audit_status": "hypothesis",
    })
    r1["nodes"].append(record)
    return record


def _scenario(size, scenario):
    path, positions = ROUTES[size]
    hits, r1 = _input(positions)
    target = (_inject_five_member_contract_node(r1, path) if size == 5
              else _selected_route(r1, path))
    assert target is not None, f"Expected R1 path not discovered: {path}"
    r1["summary"]["top_hypotheses"] = [target["id"]]
    catalog = deepcopy(load_meaning_catalog())
    # Original NEW-05 fixture semantics require the frozen 26-rule baseline,
    # even when the attached PR29 content catalog has more editorial examples.
    catalog["rule_readings"] = [r for r in catalog["rule_readings"]
                                if "interpretive_basis" not in r["provenance"]]
    originals = {r["id"]: r for r in load_rulepack().rules}
    chosen = []
    for axis in path:
        g = target["selected_witnesses_by_axis"][axis]
        key = g["evidence_key"]
        matching = sorted((h for h in hits["signals"]
                           if h["axis"] == axis and h["evidence_key"] == key
                           and h["polarity"] == 1 and not h.get("modifier_only")),
                          key=lambda h: (-h["weight"], h["rule_id"]))
        assert matching and matching[0]["rule_id"] in originals
        chosen.append(matching[0]["rule_id"])
    # Editorial readings used here are *controlled test data* tied to each
    # true selected canonical rule. They never enter the shipped catalog.
    template = catalog["rule_readings"][0]
    catalog["rule_readings"] = [
        reading for reading in catalog["rule_readings"]
        if reading["rule_id"] not in chosen
    ]
    for i, rid in enumerate(chosen):
        rule = originals[rid]
        reading = deepcopy(template)
        reading.update({
            "id": "new05-fixture."+rid,
            "rule_id": rid, "axis": rule["axis"],
            "source_rule_text": rule["text"],
            "evidence_type": rule["type"],
            "focus": "מוקד זהה" if scenario == "indistinct" else f"מוקד מוכח במסגרת בדיקה {i}",
            "distinction": ("הבחנה זהה" if scenario == "indistinct"
                            else f"הבחנה סמלית נבדלת {i}"),
            "setting": f"זירת בדיקה {i}",
            "behavior": f"עשוי לשקול אפשרות {i}",
            "limit": "אין להסיק התנהגות שהתרחשה",
            "eligible_polarity": 1,
        })
        # The test never upgrades a meaning to approved.
        reading["provenance"]["review_status"] = "unverified"
        catalog["rule_readings"].append(reading)
    if scenario == "missing":
        catalog["rule_readings"] = [
            item for item in catalog["rule_readings"]
            if item["rule_id"] not in set(chosen[1:])]
    elif scenario == "partial":
        catalog["rule_readings"] = [
            item for item in catalog["rule_readings"]
            if item["rule_id"] != chosen[-1]]
    return hits, r1, catalog, target, chosen


def _generate(hits, r1, catalog):
    model = build_personality_model(r1, hits, catalog=catalog)
    report = compose_narrative_n2(model)
    serialized = json.loads(json.dumps(
        {"semantic": model, "narrative": report}, ensure_ascii=False))
    assert serialized["narrative"] == report
    assert serialized["semantic"] == model
    return model, report, format_narrative_n2(report)


def _assert_lineage(model, report, hits, r1):
    claims = {c["id"]: c for c in model["claims"]}
    real_hits = {h["rule_id"] for h in hits["signals"]}
    real_nodes = {node["id"] for node in r1["nodes"]}
    assert len(report["process_decisions"]) == len(model["plan"]["processes"])
    for entry in report["process_decisions"]:
        subset = [claims[cid] for cid in entry["claim_ids"]]
        for key in ("rule_ids", "node_ids", "source_refs", "evidence_keys",
                    "evidence_roots", "source_review_statuses", "meaning_ids"):
            assert entry[key] == sorted({v for c in subset for v in c[key]})
        assert set(entry["rule_ids"]) <= real_hits
        assert set(entry["node_ids"]) <= real_nodes
        assert entry["source_refs"] and entry["evidence_keys"]
        assert all(c["audit_status"] == "hypothesis" for c in subset)
        assert entry["combined_assertion"] == {
            "permitted": False, "reason": "no-supported-combined-assertion"}
        assert any(c["kind"] == "process-reading" for c in subset)
    for section in report["sections"]:
        for para in section["paragraphs"]:
            subset = [claims[cid] for cid in para["claim_ids"]]
            if subset:
                for key in ("rule_ids", "node_ids", "source_refs",
                            "evidence_keys", "evidence_roots",
                            "source_review_statuses", "meaning_ids"):
                    assert para[key] == sorted({v for c in subset for v in c[key]})


@pytest.mark.parametrize("size", [2, 3, 4, 5])
@pytest.mark.parametrize("scenario", ["full", "partial", "missing", "indistinct"])
def test_production_chain_matrix_2_to_5_with_decisions_and_proof(size, scenario):
    hits, r1, catalog, target, chosen = _scenario(size, scenario)
    model, report, text = _generate(hits, r1, catalog)
    assert len(model["plan"]["processes"]) == 1
    _assert_lineage(model, report, hits, r1)
    path_decision = report["process_decisions"][0]
    assert path_decision["path"] == target["path"]
    assert len(path_decision["path"]) == size
    cp = next(c["content"]["content_plan"] for c in model["claims"]
              if c["kind"] == "process-reading")
    assert cp["coverage"]["total_members"] == size
    assert [m["selected_rule_id"] for m in cp["members"]] == chosen
    assert not cp["new_cross_axis_assertion_supported"]
    assert len(cp["members"]) == size
    if scenario in ("full", "indistinct"):
        assert cp["coverage"]["complete"]
    else:
        assert not cp["coverage"]["complete"]
    expected_compare = scenario == "full" or (
        scenario == "partial" and size >= 3)
    assert path_decision["comparison"]["permitted"] == expected_compare
    assert len(report["abstained_processes"]) == (0 if expected_compare else 1)
    paths = [p for sec in report["sections"] for p in sec["paragraphs"]
             if p["kind"] in ("process", "process-redundancy",
                                "process-abstention")]
    assert len(paths) == 1
    if expected_compare:
        assert paths[0]["kind"] in ("process", "process-redundancy")
        if paths[0]["kind"] == "process":
            assert paths[0]["interpretation_decisions"] == path_decision
            assert "אינן מוכיחות" in text or "אינו ראיה" in text
        else:
            assert path_decision["presentation"]["reason"] == "no-novel-comparison"
            assert len(report["suppressed_redundant_processes"]) == 1
            assert paths[0]["suppressed_paths"][0]["claim_ids"] == path_decision["claim_ids"]
        assert "לא נוצרה השוואה פרשנית" not in text
    else:
        assert paths[0]["kind"] == "process-abstention"
        assert report["abstained_processes"][0]["claim_ids"] == path_decision["claim_ids"]
        if scenario == "indistinct":
            assert path_decision["comparison"]["reason"] == "no-meaningful-distinction"
            assert "אין הבחנה" in text or "אינן מציגות הבחנה" in text
        else:
            assert path_decision["comparison"]["reason"] == "missing-catalog-coverage"
            assert "חסר פירוש" in text


def test_three_different_decisions_in_one_production_model(monkeypatch):
    # All three candidates are REAL R1 paths produced from one synthetic
    # chart; only display selection and test-only catalog readings change.
    positions = [
        ("שמש", 12.4), ("מרקורי", 44.4), ("שבתאי", 288.4),
        ("ונוס", 139.4), ("ירח", 73.4),
        ("צדק", 164.4), ("מאדים", 223.4),
    ]
    hits, r1 = _input(positions)
    routes = [
        ["חשיבה", "תקשורת"],         # missing (one reading)
        ["יצירתיות", "תקשורת"],      # full, but indistinct
        ["יוזמה", "התמדה", "אחריות"], # compared, no new combined assertion
    ]
    selected = [_selected_route(r1, path) for path in routes]
    assert all(selected), "The test must exercise real R1-selected path nodes"
    r1["summary"]["top_hypotheses"] = [node["id"] for node in selected]
    monkeypatch.setattr(semantic_engine, "MAX_PROCESSES", 3)

    catalog = deepcopy(load_meaning_catalog())
    # Original NEW-05 fixture semantics require the frozen 26-rule baseline,
    # even when the attached PR29 content catalog has more editorial examples.
    catalog["rule_readings"] = [r for r in catalog["rule_readings"]
                                if "interpretive_basis" not in r["provenance"]]
    originals = {r["id"]: r for r in load_rulepack().rules}
    # Add ONLY the one missing editorial entry needed for the indistinct pair.
    # This entry copies an existing documented reading solely as a test case.
    existing = next(r for r in catalog["rule_readings"]
                    if r["rule_id"] == "moon-sign-3")
    duplicate = deepcopy(existing)
    duplicate.update({
        "id": "new05-fixture.venus-sign-5",
        "rule_id": "venus-sign-5", "axis": originals["venus-sign-5"]["axis"],
        "source_rule_text": originals["venus-sign-5"]["text"],
        "evidence_type": originals["venus-sign-5"]["type"],
    })
    catalog["rule_readings"].append(duplicate)
    model, report, text = _generate(hits, r1, catalog)
    _assert_lineage(model, report, hits, r1)
    assert len(report["process_decisions"]) == 3
    assert [d["path"] for d in report["process_decisions"]] == routes
    assert [d["comparison"]["reason"] for d in report["process_decisions"]] == [
        "missing-catalog-coverage",
        "no-meaningful-distinction",
        "documented-distinct-readings",
    ]
    assert [d["comparison"]["permitted"] for d in report["process_decisions"]] == [
        False, False, True]
    assert all(d["combined_assertion"]["reason"] ==
               "no-supported-combined-assertion" for d in report["process_decisions"])
    assert len(report["abstained_processes"]) == 2
    paragraphs = [p for sec in report["sections"] for p in sec["paragraphs"]
                  if p["kind"] in ("process", "process-redundancy",
                                     "process-abstention")]
    assert paragraphs[0]["kind"] in ("process", "process-redundancy")
    assert paragraphs[1]["kind"] == "process-abstention"
    abstention = paragraphs[1]
    assert len(abstention["abstained_paths"]) == 2
    assert abstention["abstained_paths"] == report["abstained_processes"]
    assert "לרכיב חשיבה חסר פירוש" in abstention["semantic_text"]
    assert "אין הבחנה" in text or "אינן מציגות הבחנה" in text
    assert ("אינן מוכיחות" in paragraphs[0]["semantic_text"] or
            "אין מכך מסקנה" in paragraphs[0]["semantic_text"])
    assert sum(p["kind"] == "process-abstention" for p in paragraphs) == 1


@pytest.mark.parametrize("missing_count,phrase", [
    (1, "לרכיב חשיבה חסר פירוש"),
    (2, "לרכיבים חשיבה ותקשורת חסר פירוש"),
    (3, "לרכיבים חשיבה, תקשורת והתבוננות חסר פירוש"),
])
def test_hebrew_missing_members_singular_and_plural_via_realizer(missing_count, phrase):
    from astrochart.narrative_n2 import _abstention_reason
    names = ["חשיבה", "תקשורת", "התבוננות"]
    cp = {
        "coverage": {"missing_members": [
            {"axis": axis, "position": i, "selected_rule_id": f"rule-{i}"}
            for i, axis in enumerate(names[:missing_count])]},
        "comparison_is_supported": False,
    }
    reason, message = _abstention_reason(cp)
    assert reason == "missing-catalog-coverage"
    assert phrase in message
    assert ("לרכיבים" if missing_count != 1 else "לרכיב") in message
