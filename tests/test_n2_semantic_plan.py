"""Regression gates for N2's complete-path content planning and abstentions."""
from __future__ import annotations

from copy import deepcopy

import pytest

from astrochart.narrative_n2 import (
    DeterministicHebrewRealizer, compose_narrative_n2, semantic_only_n2,
)
from astrochart.semantic_plan_n2 import build_process_content_plan
from astrochart.semantics_n2 import N2_SEMANTIC_VERSION, _axis_claims, load_meaning_catalog
from astrochart.interpretation import load_rulepack


def slot(axis, i, covered=True):
    rid = f"test-rule-{i}"
    return {
        "axis": axis, "witness_group": {"evidence_key": f"witness-{i}"},
        "witness": {
            "rule_id": rid, "evidence_key": f"witness-{i}",
            "evidence": f"ראיה {i}", "source_url": "https://example.test/source",
            "review_status": "unverified",
            "meaning_id": f"editorial-{i}" if covered else None,
            "focus": f"דגש מובחן {i}" if covered else None,
            "setting": f"בעת תכנון שלב {i}" if covered else None,
            "behavior": f"עשוי לבדוק אפשרות {i}" if covered else None,
            "distinction": f"הבחנה מקורית {i}" if covered else None,
            "limitation": f"אין בסיס לקבוע אירוע {i}" if covered else None,
        },
    }


def claim(identifier, kind, content, node):
    return {
        "id": identifier, "kind": kind, "content": content,
        "classification": ("synthesis_hypothesis" if kind == "process-reading"
                           else "possible_behavior_example"),
        "node_ids": [node], "rule_ids": [m["selected_rule_id"] for m in
                                       content["content_plan"]["members"]],
        "source_refs": ["https://example.test/source"],
        "source_review_statuses": ["unverified"],
        "evidence_keys": [m["selected_evidence_key"] for m in
                          content["content_plan"]["members"]],
        "evidence_roots": [f"root-{node}"], "meaning_ids": [],
        "audit_status": "hypothesis", "provisional_time": False,
    }


@pytest.mark.parametrize("missing_position", (0, 1, 2))
def test_partial_path_identifies_each_missing_position(missing_position):
    path = ["יצירתיות", "חשיבה", "תקשורת"]
    slots = [slot(axis, i, i != missing_position)
             for i, axis in enumerate(path)]
    plan = build_process_content_plan(path, slots, "עיבוד", None, True)
    assert plan["path"] == path
    assert len(plan["members"]) == 3
    assert plan["coverage"]["covered_members"] == 2
    assert plan["coverage"]["missing_members"] == [{
        "position": missing_position, "axis": path[missing_position],
        "selected_rule_id": f"test-rule-{missing_position}",
    }]
    assert plan["comparison_is_supported"]
    assert not plan["new_cross_axis_assertion_supported"]
    assert not plan["supported_readings"]
    components = [{
        "axis": m["axis"], "focus": m["documented_meaning"]["focus"],
        "setting": m["documented_meaning"]["setting"],
        "limit": m["documented_meaning"]["limit"],
    } for m in plan["members"] if m["meaning_covered"]]
    texts = [
        claim("base", "process-reading", {
            "path": path, "slots": slots, "content_plan": plan,
            "proof_search_complete": True}, "r1-node"),
        claim("compare", "process-example", {
            "components": components, "content_plan": plan}, "r1-node"),
    ]
    semantic, evidence = DeterministicHebrewRealizer().process(texts, 0)
    assert "השוואה חלקית בלבד" in semantic
    assert "2 מתוך 3" in semantic
    assert path[missing_position] in semantic
    assert f"לרכיב {path[missing_position]}" in semantic
    assert " → ".join(path) in semantic
    assert "ראיות המסלול" in evidence
    assert "גורם לאחר" in semantic and "אינן מוכיחות" in semantic


def test_complete_path_keeps_all_contexts_and_no_causal_claim():
    path = ["יוזמה", "התמדה", "אחריות"]
    slots = [slot(axis, i) for i, axis in enumerate(path)]
    plan = build_process_content_plan(path, slots, "ביצוע", "r1", True)
    assert plan["coverage"]["complete"]
    assert len(plan["supported_readings"]) == 1
    assert len(plan["distinctions"]) == 3
    assert all(x["licensed_as"] == "comparison-only"
               for x in plan["distinctions"])
    assert "psychological-causality" in plan["unsupported_links"]
    assert plan["synthesis_status"] == "hypothesis-not-proven"
    assert not plan["new_cross_axis_assertion_supported"]
    # Different selected witnesses produce different content plans, even when
    # all three R1 axis labels remain identical.
    alternate = deepcopy(slots)
    alternate[1]["witness"]["focus"] = "שינוי מוקד מבוסס ראיה אחרת"
    other = build_process_content_plan(path, alternate, "ביצוע", "r1", True)
    assert other["distinctions"] != plan["distinctions"]


@pytest.mark.parametrize("count", (1, 2, 3, 4))
def test_axis_evidence_count_meaning_count_example_count_are_separate(count):
    axis = "אחריות"
    claims = [{
        "kind": "axis-meaning", "content": {
            "axis": axis, "definition": "אחריות", "independent_evidence_count": count,
        },
    }]
    for i in range(count):
        claims.append({"kind": "rule-anchor", "content": {
            "chart_evidence": f"ראיה {i}", "selected_rule_id": f"rule-{i}",
            "review_status": "unverified", "selected_source_url": None,
            "rule_text": f"נוסח {i}",
        }})
        if i < 3:
            claims.append({"kind": "axis-example", "content": {
                "focus": f"מוקד {i}", "distinction": f"הבדל {i}",
                "situation": f"במצב {i}", "behavior": f"עשוי לשקול {i}",
                "limit": f"אין להסיק {i}", "evidence_type": "sign",
            }})
    text, evidence = DeterministicHebrewRealizer().axis(claims, 0, secondary=False)
    assert evidence.count("• ") == count
    if count >= 2:
        assert f"מתוך {count} קבוצות" in text
        assert f"ל־{min(count, 3)} יש פירוש" in text
        assert f"מובאות {min(count, 2)} דוגמאות" in text
    if count == 3:
        assert "שני הדפוסים" not in text
        assert "מוקד 2" in text and "במצב 2" not in text
    if count == 4:
        assert "לקבוצת ראיה אחת נוספת" in text


def test_two_abstentions_collapse_but_both_paths_and_proof_remain():
    paths = [["יצירתיות", "חשיבה"], ["יוזמה", "אחריות"]]
    claims, groups = [], []
    for i, path in enumerate(paths):
        slots = [slot(axis, j + i * 3, False) for j, axis in enumerate(path)]
        plan = build_process_content_plan(path, slots, "ביצוע", None, True)
        c = claim(f"process-{i}", "process-reading", {
            "path": path, "slots": slots, "content_plan": plan,
            "proof_search_complete": True,
        }, f"r1-node-{i}")
        claims.append(c)
        groups.append([c["id"]])
    semantics = {
        "semantic_version": N2_SEMANTIC_VERSION,
        "claims": claims, "plan": {
            "primary": [], "secondary": [], "processes": groups, "tensions": [],
        },
        "time_mode": "known", "warnings": [],
        "source_engine_version": "r1", "source_rule_pack": "test-pack",
    }
    report = compose_narrative_n2(semantics)
    section = next(x for x in report["sections"] if x["id"] == "processes")
    assert len(section["paragraphs"]) == 1
    paragraph = section["paragraphs"][0]
    assert paragraph["kind"] == "process-abstention"
    assert set(paragraph["claim_ids"]) == {c["id"] for c in claims}
    assert len(paragraph["abstained_paths"]) == 2
    assert report["abstained_processes"] == paragraph["abstained_paths"]
    assert all(x["coverage"]["covered_members"] == 0
               for x in report["abstained_processes"])
    assert all(" → ".join(path) in paragraph["semantic_text"] for path in paths)
    assert len([x for x in semantic_only_n2(report) if "אותרו" in x]) == 1


def test_one_abstained_path_has_natural_singular_hebrew():
    path = ["יצירתיות", "חשיבה"]
    slots = [slot(axis, i, False) for i, axis in enumerate(path)]
    plan = build_process_content_plan(path, slots, "עיבוד", None, True)
    c = claim("single-process", "process-reading", {
        "path": path, "slots": slots, "content_plan": plan,
        "proof_search_complete": True}, "single-node")
    model = {
        "semantic_version": N2_SEMANTIC_VERSION, "claims": [c],
        "plan": {"primary": [], "secondary": [],
                 "processes": [[c["id"]]], "tensions": []},
        "time_mode": "known", "warnings": [],
        "source_engine_version": "r1", "source_rule_pack": "test-pack",
    }
    narrative = compose_narrative_n2(model)
    p = next(p for s in narrative["sections"] for p in s["paragraphs"]
             if p["kind"] == "process-abstention")
    assert "אותר מסלול נוסף" in p["semantic_text"]
    assert "אותרו 1 מסלולים" not in p["semantic_text"]
    assert len(narrative["abstained_processes"]) == 1


def test_missing_first_axis_witness_does_not_renumber_later_meanings():
    def anchor(i):
        return {
            "kind": "rule-anchor", "evidence_keys": [f"group-{i}"],
            "content": {"chart_evidence": f"ראיה {i}", "selected_rule_id": f"r{i}",
                        "review_status": "unverified", "selected_source_url": None,
                        "rule_text": "נוסח כללי"},
        }
    def example(i):
        return {
            "kind": "axis-example", "evidence_keys": [f"group-{i}"],
            "content": {"focus": f"מוקד {i}", "distinction": f"הבחנה {i}",
                        "situation": f"מצב {i}", "behavior": f"עשוי לשקול {i}",
                        "limit": f"אין להסיק {i}", "evidence_type": "placement"},
        }
    claims = [{"kind": "axis-meaning", "content": {
        "axis": "חשיבה", "definition": "הגדרה",
        "independent_evidence_count": 3,
    }}] + [anchor(i) for i in (0, 1, 2)] + [example(1), example(2)]
    semantic, proof = DeterministicHebrewRealizer().axis(
        claims, 0, secondary=False)
    assert "מוקד 1 (קבוצת ראיה 2)" in semantic
    assert "מוקד 2 (קבוצת ראיה 3)" in semantic
    assert "מוקד 1 (קבוצת ראיה 1)" not in semantic
    assert proof.count("• ") == 3


def test_four_real_catalog_rules_are_covered_even_when_only_three_are_displayed():
    """The four rule IDs in the independent audit are all truly covered."""
    rule_ids = ["sun-sign-10", "moon-sign-10", "mercury-sign-10", "mars-sign-10"]
    canonical = {r["id"]: r for r in load_rulepack().rules}
    catalog = load_meaning_catalog()
    readings = {x["rule_id"]: x for x in catalog["rule_readings"]}
    assert all(rid in readings and canonical[rid]["axis"] == "אחריות"
               for rid in rule_ids)
    groups, signals = [], []
    for i, rid in enumerate(rule_ids):
        rule = canonical[rid]
        url = rule["source_detail"]["url"]
        key, evidence = f"unique-group-{i}", f"ראיה מקורית {i}"
        groups.append({
            "rule_ids": [rid], "source_refs": [url],
            "review_statuses": [rule["review_status"]],
            "evidence_key": key, "roots": [f"root-{i}"],
            "details": [evidence],
        })
        signals.append({
            "axis": "אחריות", "polarity": 1, "evidence_key": key,
            "rule_id": rid, "text": rule["text"], "evidence": evidence,
            "weight": 1, "modifier_only": False,
            "review_status": rule["review_status"],
            "provisional": False, "source_url": url, "source": rule["source"],
        })
    node = {
        "id": "r1-test-four-evidences", "type": "axis", "axis": "אחריות",
        "independent_facts": groups, "rule_ids": sorted(rule_ids),
        "source_refs": sorted(set(g["source_refs"][0] for g in groups)),
        "source_review_statuses": sorted(set(g["review_statuses"][0]
                                              for g in groups)),
        "audit_status": "symbolic-input",
    }
    axis_entry = next(e for e in catalog["entries"] if e["axis"] == "אחריות")
    def create(reading_set):
        return _axis_claims(node, axis_entry,
                            {"signals": signals, "time_mode": "known"},
                            reading_set, {r["id"]: r["type"] for r in canonical.values()})
    full = create(readings)
    content = full[0]["content"]
    assert content["independent_evidence_count"] == 4
    assert content["catalog_coverage_count"] == 4
    assert content["displayed_meaning_count"] == 3
    assert content["rule_conditioned_coverage"] == 3  # legacy displayed alias
    assert content["catalog_missing_evidence_keys"] == []
    assert content["omitted_due_to_display_limit"] == ["unique-group-3"]
    assert len([c for c in full if c["kind"] == "rule-anchor"]) == 4
    assert len([c for c in full if c["kind"] == "axis-example"]) == 3
    text, evidence = DeterministicHebrewRealizer().axis(full, 0, secondary=False)
    assert "ל־4 יש פירוש עריכתי" in text
    assert "מוצגות כאן 3 הרחבות בלבד בשל מגבלת אורך" in text
    assert "אין פירוש התנהגותי ייחודי במאגר" not in text
    assert evidence.count("• ") == 4
    assert set(content["catalog_covered_evidence_keys"]) == {
        f"unique-group-{i}" for i in range(4)}
    assert all(c["source_refs"] and c["rule_ids"] for c in full)

    # The *same* evidence, now with one catalog reading genuinely absent.
    reduced = create({k: v for k, v in readings.items() if k != rule_ids[-1]})
    reduced_content = reduced[0]["content"]
    assert reduced_content["catalog_coverage_count"] == 3
    assert reduced_content["displayed_meaning_count"] == 3
    assert reduced_content["catalog_missing_evidence_keys"] == ["unique-group-3"]
    text_missing, _ = DeterministicHebrewRealizer().axis(
        reduced, 0, secondary=False)
    assert "לקבוצת ראיה אחת נוספת אין פירוש" in text_missing


@pytest.mark.parametrize("missing_positions", [(), (0,), (2,), (0, 2, 4)])
def test_five_member_path_preserves_all_members_and_selected_lineage(missing_positions):
    path = ["יוזמה", "יציבות", "התמדה", "אחריות", "חשיבה"]
    slots = [slot(axis, i, i not in missing_positions)
             for i, axis in enumerate(path)]
    plan = build_process_content_plan(path, slots, "עיבוד", "selected-r1", True)
    assert len(plan["members"]) == 5
    assert [m["selected_rule_id"] for m in plan["members"]] == [
        f"test-rule-{i}" for i in range(5)]
    assert [m["position"] for m in plan["coverage"]["missing_members"]] == list(
        missing_positions)
    assert plan["coverage"]["covered_members"] == 5 - len(missing_positions)
    assert plan["comparison_is_supported"]  # distinguishable available meanings
    base = claim("five-base", "process-reading", {
        "path": path, "slots": slots, "content_plan": plan,
        "proof_search_complete": True}, "five-r1")
    comparison = claim("five-example", "process-example", {
        "path": path, "content_plan": plan, "components": [{
            "axis": m["axis"], "focus": m["documented_meaning"]["focus"],
            "setting": m["documented_meaning"]["setting"],
            "limit": m["documented_meaning"]["limit"]
        } for m in plan["members"] if m["meaning_covered"]]}, "five-r1")
    model = {
        "semantic_version": N2_SEMANTIC_VERSION,
        "claims": [base, comparison],
        "plan": {"primary": [], "secondary": [],
                 "processes": [[base["id"], comparison["id"]]], "tensions": []},
        "time_mode": "known", "warnings": [],
        "source_engine_version": "r1", "source_rule_pack": "test-pack",
    }
    result = compose_narrative_n2(model)
    p = next(p for s in result["sections"] for p in s["paragraphs"]
             if p["kind"] == "process")
    assert p["process_content_plan"]["path"] == path
    assert p["process_content_plan"]["members"] == plan["members"]
    assert p["claim_ids"] == ["five-base", "five-example"]
    assert " → ".join(path) in p["semantic_text"]
    assert "גורם לאחר" in p["semantic_text"] or "קשר סיבתי" in p["semantic_text"]
    if missing_positions:
        assert "השוואה חלקית בלבד" in p["semantic_text"]
        assert f"{5 - len(missing_positions)} מתוך 5" in p["semantic_text"]
        for i in missing_positions:
            assert path[i] in p["semantic_text"]
    else:
        assert "כל 5 הרכיבים" in p["semantic_text"]


@pytest.mark.parametrize("reason", [
    "missing-catalog-coverage", "no-meaningful-distinction",
    "no-supported-combined-assertion",
])
def test_abstention_reason_and_hebrew_explanation_are_truthful(reason):
    path = ["יוזמה", "התמדה", "אחריות", "חשיבה"]
    slots = [slot(axis, i, reason != "missing-catalog-coverage" or i != 2)
             for i, axis in enumerate(path)]
    if reason == "no-meaningful-distinction":
        for x in slots:
            x["witness"]["focus"] = "מוקד משותף"
            x["witness"]["distinction"] = "הבחנה זהה"
    plan = build_process_content_plan(path, slots, "עיבוד", None, True)
    c = claim("abstention", "process-reading", {
        "path": path, "slots": slots, "content_plan": plan,
        "proof_search_complete": True}, "r1-abstention")
    model = {
        "semantic_version": N2_SEMANTIC_VERSION, "claims": [c],
        "plan": {"primary": [], "secondary": [],
                 "processes": [[c["id"]]], "tensions": []},
        "time_mode": "known", "warnings": [],
        "source_engine_version": "r1", "source_rule_pack": "test-pack",
    }
    result = compose_narrative_n2(model)
    record = result["abstained_processes"][0]
    paragraph = next(p for sec in result["sections"] for p in sec["paragraphs"]
                     if p["kind"] == "process-abstention")
    assert record["reason"] == reason
    assert record["reason_explanation"] in paragraph["semantic_text"]
    assert paragraph["claim_ids"] == [c["id"]]
    assert record["coverage"] == plan["coverage"]
    assert len(record["rule_ids"]) == 4
    assert len(record["path"]) == 4
    if reason == "missing-catalog-coverage":
        assert "אחריות" in record["reason_explanation"]
    elif reason == "no-meaningful-distinction":
        assert not plan["comparison_is_supported"]
    else:
        assert plan["comparison_is_supported"]
        assert not plan["new_cross_axis_assertion_supported"]
