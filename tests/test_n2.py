"""N2 evidence, differential maps, time uncertainty, and Hebrew quality gates."""
from copy import deepcopy
import json

import pytest

from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.synthesis import synthesize, FUNCTIONS
from astrochart.narrative import compose_narrative, format_narrative
from astrochart.semantics_n2 import build_personality_model, load_meaning_catalog
from astrochart.narrative_n2 import compose_narrative_n2, format_narrative_n2


def chart(sun=12.4, *, unknown=False, estimated=False, full=True):
    bodies = [BodyPosition("שמש", sun, False, (int(sun // 30),))]
    if full:
        bodies += [BodyPosition("מרקורי", 35.0, False, (1,)),
                   BodyPosition("שבתאי", 286.0, False, (9,))]
    return Chart(bodies, [], None, None, unknown, [],
                 time_certainty=("unknown" if unknown else
                                 "estimated" if estimated else "known"))


def run(c):
    evidence = interpret_chart(c)
    r1 = synthesize(c, evidence)
    semantic = build_personality_model(r1, evidence)
    narrative = compose_narrative_n2(semantic)
    return evidence, r1, semantic, narrative


def test_catalog_is_editorial_and_rules_remain_unmodified():
    catalog = load_meaning_catalog()
    assert len(catalog["entries"]) == len(FUNCTIONS) == 13
    assert {item["axis"] for item in catalog["entries"]} == set(FUNCTIONS)
    assert all(not item["provenance"]["astrological_rule"]
               and item["provenance"]["review_status"] == "unverified"
               for item in catalog["entries"])
    assert len(load_rulepack().rules) == 96
    assert catalog["catalog_version"] == "0.1.0"


def test_n2_is_attributed_and_more_concrete_than_n1():
    evidence, r1, semantic, narrative = run(chart())
    nodes = {n["id"]: n for n in r1["nodes"]}
    rules = {h["rule_id"] for h in evidence["signals"]}
    meanings = {e["id"] for e in load_meaning_catalog()["entries"]}
    text = format_narrative_n2(narrative)
    old = format_narrative(compose_narrative(r1))
    assert "פרשנות אישית" in text
    assert "מול משימה חדשה" in text or "מצטברות מטלות" in text
    assert "חוזקה" not in old or "פעולת" in old
    assert "כאשר" in text and "הקושי" in text or "קושי" in text
    assert "אבחון אישיות" in text
    assert semantic["relationship_discovery_enabled"] is False
    assert semantic["catalog_review_status"] == "unverified"
    assert semantic["claims"]
    for claim in semantic["claims"]:
        assert claim["node_ids"] and set(claim["node_ids"]) <= set(nodes)
        assert claim["rule_ids"] and set(claim["rule_ids"]) <= rules
        assert set(claim["meaning_ids"]) <= meanings
        assert claim["classification"] in {
            "existing_rule", "editorial_extension", "possible_behavior_example",
            "synthesis_hypothesis", "unresolved_tension"}
        if claim["classification"] == "existing_rule":
            assert claim["content"]["selected_rule_id"] in claim["rule_ids"]
        if claim["classification"] == "synthesis_hypothesis":
            assert claim["audit_status"] == "hypothesis"
    ids = {c["id"] for c in semantic["claims"]}
    for section in narrative["sections"]:
        for p in section["paragraphs"]:
            assert set(p["claim_ids"]) <= ids
            if p["claim_ids"]:
                assert p["rule_ids"] and p["node_ids"]
                assert p["source_review_statuses"]
                assert p["meaning_ids"] or "existing_rule" in p["classifications"]
    # No mutation of upstream report or source evidence.
    frozen = deepcopy(r1), deepcopy(evidence)
    assert semantic == build_personality_model(r1, evidence)
    assert narrative == compose_narrative_n2(semantic)
    assert (r1, evidence) == frozen


def test_changed_material_rule_changes_personality_content_not_just_name():
    _, _, aries, a = run(chart(12.4, full=False))
    _, _, gemini, b = run(chart(72.4, full=False))
    x, y = format_narrative_n2(a), format_narrative_n2(b)
    assert x != y
    assert "יוזמה" in x and "גמישות" in y
    assert "צעד ראשון" in x and "חלופות" in y
    assert "sun-sign-1" in {r for c in aries["claims"] for r in c["rule_ids"]}
    assert "sun-sign-3" in {r for c in gemini["claims"] for r in c["rule_ids"]}


def test_irrelevant_same_sign_degree_does_not_change_prose():
    _, _, s1, n1 = run(chart(11.2, full=False))
    _, _, s2, n2 = run(chart(13.4, full=False))
    assert s1 == s2 and n1 == n2


def test_uncertainty_modes_do_not_invent_aspects_or_houses():
    for known, estimated, unknown in [(True, False, False),
                                      (False, True, False),
                                      (False, False, True)]:
        _, r1, semantic, narrative = run(chart(
            unknown=unknown, estimated=estimated))
        mode = "known" if known else "estimated" if estimated else "unknown"
        assert semantic["time_mode"] == narrative["time_mode"] == mode
        assert all(c["provisional_time"] == (not known)
                   for c in semantic["claims"])
        disclosure = narrative["sections"][-1]["paragraphs"][0]["text"]
        if unknown:
            assert "שעת הלידה אינה ידועה" in disclosure
        if estimated:
            assert "שעת הלידה משוערת" in disclosure
        assert all(not c["content"].get("house")
                   and not c["content"].get("aspect")
                   for c in semantic["claims"])


def test_unresolved_tension_has_both_original_polarities_without_context():
    c = chart(full=False)
    interpretation = deepcopy(interpret_chart(c))
    opposite = deepcopy(interpretation["signals"][0])
    opposite.update(rule_id="n2-fixture-opposition", polarity=-1,
                    review_status="reviewed",
                    source_url="https://example.org/contradiction")
    interpretation["signals"].append(opposite)
    r1 = synthesize(c, interpretation)
    semantic = build_personality_model(r1, interpretation)
    tension = next(c for c in semantic["claims"]
                   if c["classification"] == "unresolved_tension")
    polarities = tension["evidence_by_polarity"]
    assert "n2-fixture-opposition" in polarities["negative"]["rule_ids"]
    assert "n2-fixture-opposition" not in polarities["positive"]["rule_ids"]
    assert "https://example.org/contradiction" in polarities["negative"]["source_refs"]
    assert tension["audit_status"] == "unresolved"
    assert tension["content"]["context"] is None
    assert not [c for c in semantic["claims"]
                if c["axis"] == "יוזמה" and c["kind"] == "axis-example"]
    assert "אינו מאפשר להכריע" in format_narrative_n2(compose_narrative_n2(semantic))


def test_r1_forgery_is_rejected_not_rendered():
    c = chart()
    interpretation, r1, semantic, _ = run(c)
    invalid = deepcopy(r1)
    axis = next(n for n in invalid["nodes"] if n["type"] == "axis")
    axis["rule_ids"] = ["fabricated-rule"]
    result = build_personality_model(invalid, interpretation)
    assert not [c for c in result["claims"] if c["node_ids"] == [axis["id"]]
                and c["classification"] in ("existing_rule", "editorial_extension")]
    assert result["claims"] != semantic["claims"]


def test_empty_r1_makes_no_personality_claims():
    source = {"nodes": [], "summary": {"top_hypotheses": [],
                                        "leading_axes": []},
              "time_mode": "known", "warnings": []}
    semantic = build_personality_model(source)
    narrative = compose_narrative_n2(semantic)
    assert not semantic["claims"]
    text = format_narrative_n2(narrative)
    assert "אין די" in text
    assert "המערכת אינה משלימה" in text


def test_no_duplicate_claims_paragraphs_and_diff_with_source():
    _, _, s, report = run(chart())
    ids = [c["id"] for c in s["claims"]]
    assert len(ids) == len(set(ids))
    paragraphs = [p for section in report["sections"] for p in section["paragraphs"]]
    content = [p["text"] for p in paragraphs]
    assert len(content) == len(set(content))
    assert all(len(p) < 1300 for p in content)
    assert all(len(p["text"]) > 100 for p in paragraphs
               if p["kind"] in ("axis", "process"))
    assert json.dumps(s, ensure_ascii=False)


def test_report_time_mode_mismatch_fails_closed():
    evidence, r1, _, _ = run(chart())
    invalid = deepcopy(evidence)
    invalid["time_mode"] = "unknown"
    with pytest.raises(ValueError, match="שעת הלידה"):
        build_personality_model(r1, invalid)
