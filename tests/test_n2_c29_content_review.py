"""C29 independent of old N2 holdouts: interpreter-subject, withheld meaning,
source-scope, 10 previously unobserved rules and non-lexical redundancy tests.
"""
from __future__ import annotations

import pytest

from astrochart.domain import BodyPosition, Chart, SIGNS, calculate_aspects
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.narrative_n2 import compose_narrative_n2, format_narrative_n2
from astrochart.n2_catalog_comparison_policy import presentation_decision
from astrochart.semantics_n2 import build_personality_model, load_meaning_catalog
from astrochart.synthesis import synthesize


SYMBOLIC_ONLY = (
    "sun-moon-trine", "venus-mars-trine", "moon-house-4",
    "moon-jupiter-trine", "venus-house-2", "jupiter-house-9",
)
QUARANTINED = ("mercury-sign-9", "venus-sign-10", "saturn-sign-1")
UNOBSERVED = (
    "mercury-sign-3", "mercury-sign-4", "mercury-sign-11",
    "venus-sign-12", "mars-sign-1", "mars-sign-9",
    "jupiter-sign-1", "jupiter-sign-9", "saturn-sign-11",
    "venus-mars-trine",
)
OVERLAPS = (
    ("sun-sign-4", "moon-sign-4"),
    ("moon-sign-8", "moon-sign-11"),
    ("sun-sign-12", "moon-sign-12"),
    ("sun-sign-8", "mercury-sign-8"),
    ("venus-sign-3", "venus-sign-9"),
    ("sun-sign-9", "jupiter-sign-9"),
)


def _chart_for_rule(rule: dict) -> Chart:
    when = rule["when"]
    if rule["type"] == "placement":
        body = BodyPosition(when["body"], SIGNS.index(when["sign"]) * 30 + 12,
                            False, (SIGNS.index(when["sign"]),))
        return Chart([body], [], None, None, False, [], time_certainty="known")
    if rule["type"] == "house":
        body = BodyPosition(when["body"], 12, False, (0,), house=when["house"])
        return Chart([body], [], None, None, False, [], time_certainty="known")
    if rule["type"] == "aspect":
        assert when["kind"] == "משולש"
        first = BodyPosition(when["pair"][0], 12, False, (0,))
        second = BodyPosition(when["pair"][1], 132, False, (4,))
        bodies = [first, second]
        return Chart(bodies, calculate_aspects(bodies), None, None, False, [],
                     time_certainty="known")
    raise AssertionError("only placement, house and trine are expected")


def _run(rule_id: str):
    rule = next(r for r in load_rulepack().rules if r["id"] == rule_id)
    chart = _chart_for_rule(rule)
    hits = interpret_chart(chart)
    assert rule_id in {h["rule_id"] for h in hits["signals"]}
    r1 = synthesize(chart, hits)
    model = build_personality_model(r1, hits)
    report = compose_narrative_n2(model)
    assert model["relationship_discovery_enabled"] is False
    assert model["catalog_review_status"] == "unverified"
    assert report["source_rule_pack"] == model["source_rule_pack"]
    return model, report


@pytest.mark.parametrize("rule_id", SYMBOLIC_ONLY)
def test_all_six_interpreter_subject_failures_are_quarantined(rule_id):
    catalog = load_meaning_catalog()
    explanations = {r["rule_id"]: r for r in catalog["symbolic_explanations"]}
    readings = {r["rule_id"] for r in catalog["rule_readings"]}
    assert rule_id not in readings
    e = explanations[rule_id]
    assert e["kind"] == "symbolic-explanation"
    assert e["display_policy"] == "non-behavioral-metadata-only-not-personality-N2"
    assert e["provenance"]["individual_external_source_verified"] is False
    assert e["provenance"]["review_status"] == "unverified"
    assert "בעל המפה עשוי" not in e["explanation"]
    model, report = _run(rule_id)
    assert not [c for c in model["claims"]
                if c["kind"] == "axis-example"
                and c["content"]["selected_rule_id"] == rule_id]
    assert all(rule_id not in c["rule_ids"] for c in model["claims"]
               if c["kind"] == "axis-example")
    # A rule-anchor may still be present: original R1 evidence is not removed.
    for section in report["sections"]:
        for paragraph in section["paragraphs"]:
            assert not ("בעל המפה עשוי לתאר" in paragraph["semantic_text"] or
                        "בעל המפה עשוי להמחיש" in paragraph["semantic_text"] or
                        "בעל המפה עשוי להציג אפשרות" in paragraph["semantic_text"])


@pytest.mark.parametrize("rule_id", QUARANTINED)
def test_three_axis_mismatches_no_longer_license_personal_behavior(rule_id):
    catalog = load_meaning_catalog()
    assert rule_id not in {r["rule_id"] for r in catalog["rule_readings"]}
    entry = next(r for r in catalog["withheld_editorial_readings"]
                 if r["rule_id"] == rule_id)
    assert entry["status"] == "quarantined-from-N2-display"
    assert entry["reason"] and entry["review_status"] == "unverified"
    model, _ = _run(rule_id)
    assert not any(c["kind"] == "axis-example" and
                   c["content"]["selected_rule_id"] == rule_id
                   for c in model["claims"])


@pytest.mark.parametrize("rule_id", UNOBSERVED)
def test_all_ten_previously_unseen_rules_have_real_targeted_rule_hits(rule_id):
    model, report = _run(rule_id)
    catalog = load_meaning_catalog()
    behavioral = {r["rule_id"] for r in catalog["rule_readings"]}
    examples = [c for c in model["claims"] if c["kind"] == "axis-example"
                and c["content"]["selected_rule_id"] == rule_id]
    if rule_id == "venus-mars-trine":
        assert not examples
        assert rule_id not in behavioral
        assert any(x["rule_id"] == rule_id
                   for x in catalog["symbolic_explanations"])
    else:
        assert rule_id in behavioral
        assert len(examples) == 1
        claim = examples[0]
        assert claim["meaning_ids"] and claim["source_refs"]
        assert claim["source_review_statuses"]
        assert claim["content"]["editorial_review_status"] == "unverified"
    assert isinstance(format_narrative_n2(report), str)


def test_all_new_behavioral_readings_are_explicitly_not_externally_verified():
    catalog = load_meaning_catalog()
    old = [r for r in catalog["rule_readings"]
           if "interpretive_basis" not in r["provenance"]]
    new = [r for r in catalog["rule_readings"]
           if r["provenance"].get("interpretive_basis")]
    assert len(old) == 26 and len(new) == 51
    assert len(catalog["symbolic_explanations"]) == 6
    assert len(catalog["withheld_editorial_readings"]) == 3
    assert len(catalog["rule_readings"]) == 77
    for r in new:
        p = r["provenance"]
        assert p["specific_external_source_verified"] is False
        assert p["external_evidence_status"] == "not-established"
        assert p["source_support_type"] == "general-framework-only"
        assert p["review_status"] == "unverified"
        assert p["editorial_extrapolation"] and p["unverified_items"]
        assert p["original_source_scope"]


@pytest.mark.parametrize("a,b", OVERLAPS)
def test_overlapping_pairs_are_not_presented_as_independently_validated(a,b):
    catalog = load_meaning_catalog()
    readings = {r["rule_id"]: r for r in catalog["rule_readings"]}
    for id_ in (a,b):
        r=readings[id_]
        assert r["provenance"]["specific_external_source_verified"] is False
        assert r["provenance"]["review_status"] == "unverified"
    assert readings[a]["source_rule_text"] != readings[b]["source_rule_text"]
    assert readings[a]["evidence_type"] in ("placement","house","aspect")
    assert readings[b]["evidence_type"] in ("placement","house","aspect")


def test_no_novel_comparison_uses_evidence_identity_not_wording():
    members = [
        {"position": 0, "axis": "יוזמה", "selected_rule_id": "a",
         "selected_evidence_key": "key-a",
         "meaning_covered": True, "documented_meaning": {
             "id": "meaning-a", "focus": "התחלה"}},
        {"position": 1, "axis": "אחריות", "selected_rule_id": "b",
         "selected_evidence_key": "key-b",
         "meaning_covered": True, "documented_meaning": {
             "id": "meaning-b", "focus": "המשכיות"}},
    ]
    plan={"comparison_is_supported": True, "members": members}
    visible={("a","key-a","meaning-a"),("b","key-b","meaning-b")}
    result=presentation_decision(plan, visible, set())
    assert result["display"] is False
    assert result["reason"]=="no-novel-comparison"
    assert result["basis"]=="all-exact-selected-meanings-already-explained-as-axes"
    members[0]["documented_meaning"]["focus"] = "שם שונה לאותו רעיון"
    assert presentation_decision(plan, visible, set())["display"] is False
    assert presentation_decision(plan, visible-{("b","key-b","meaning-b")},
                                 set())["display"] is True
    sig = presentation_decision(plan, set(), set())["signature"]
    assert presentation_decision(plan, set(), {sig})["reason"]=="no-novel-comparison"
