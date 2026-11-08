"""Regression gates for N2's complete-path content planning and abstentions."""
from __future__ import annotations

from copy import deepcopy

import pytest

from astrochart.narrative_n2 import (
    DeterministicHebrewRealizer, compose_narrative_n2, semantic_only_n2,
)
from astrochart.semantic_plan_n2 import build_process_content_plan
from astrochart.semantics_n2 import N2_SEMANTIC_VERSION


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
        assert "ל־1 קבוצות ראיה" in text


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
