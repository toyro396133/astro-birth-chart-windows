"""Independent editorial coverage gates; no old holdout cases used for tuning."""
from __future__ import annotations

from copy import deepcopy

from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.narrative_n2 import compose_narrative_n2, format_narrative_n2
from astrochart.semantics_n2 import build_personality_model, load_meaning_catalog
from astrochart.synthesis import synthesize


def _split_catalog():
    cat = load_meaning_catalog()
    baseline = deepcopy(cat)
    baseline["rule_readings"] = [
        r for r in cat["rule_readings"] if
        r["provenance"].get("interpretive_basis") != "unverified-original-rule-text-only"
    ]
    return baseline, cat


def _new_chart(*items, mode="known"):
    return Chart([
        BodyPosition(name, angle, False, (int(angle // 30),))
        for name, angle in items
    ], [], None, None, mode == "unknown", [], time_certainty=mode)


def test_new_catalog_is_bounded_and_traceable():
    base, cat = _split_catalog()
    rules = {r["id"]: r for r in load_rulepack().rules}
    before = {r["rule_id"]: r for r in base["rule_readings"]}
    after = {r["rule_id"]: r for r in cat["rule_readings"]}
    added = [r for id_, r in after.items() if id_ not in before]
    remaining = [r for id_, r in rules.items() if id_ not in after]
    assert len(rules) == 96 and len(before) == 26
    assert cat["catalog_version"] == "0.3.0"
    assert len(added) == 60 and len(after) == 86 and len(remaining) == 10
    assert all(r["polarity"] == -1 or r["type"] == "composite"
               for r in remaining)
    assert {(r["id"], r["type"]) for r in remaining} == {
        ("sun-moon-square", "aspect"), ("sun-moon-opposition", "aspect"),
        ("mercury-saturn-square", "aspect"), ("saturn-house-1", "house"),
        ("mercury-mars-square", "aspect"), ("mars-saturn-square", "aspect"),
        ("sun-aries-moon-taurus", "composite"),
        ("mercury-virgo-saturn-capricorn", "composite"),
        ("venus-libra-mars-libra", "composite"),
        ("sun-sagittarius-mercury-sagittarius", "composite"),
    }
    assert len({r["focus"] for r in added}) == len(added)
    assert len({r["setting"] for r in added}) == len(added)
    assert len({r["behavior"] for r in added}) == len(added)
    assert len({r["distinction"] for r in added}) == len(added)
    for meaning in added:
        rule = rules[meaning["rule_id"]]
        p = meaning["provenance"]
        assert meaning["source_rule_text"] == rule["text"]
        assert meaning["axis"] == rule["axis"]
        assert meaning["evidence_type"] == rule["type"]
        assert meaning["eligible_polarity"] == rule["polarity"] == 1
        assert p["review_status"] == "unverified"
        assert p["astrological_rule"] is False
        assert p["rule_review_status_at_authoring"] == rule["review_status"]
        assert p["original_source_url"] == rule["source_detail"]["url"]
        assert p["original_source_scope"] == rule["source_detail"]["scope"]
        assert "not" in p["origin"] or "unverified" in p["interpretive_basis"]
    for rid in before:
        assert after[rid] == before[rid], rid


def test_new_synthetic_map_comparisons_enrich_without_changing_r1_evidence():
    baseline, expanded = _split_catalog()
    cases = {
        "environment": _new_chart(("שמש", 106.4), ("ירח", 216.1)),
        "new-actions": _new_chart(("מאדים", 348.8), ("צדק", 162.3)),
        "aesthetics": _new_chart(("ונוס", 281.9), ("מרקורי", 218.1)),
        "mixed": _new_chart(("שמש", 141.1), ("מאדים", 166.2),
                            ("ונוס", 225.6), ("שבתאי", 331.4)),
    }
    changes = 0
    new_rules = {r["rule_id"] for r in expanded["rule_readings"]} - {
        r["rule_id"] for r in baseline["rule_readings"]}
    for name, chart in cases.items():
        hits = interpret_chart(chart)
        r1 = synthesize(chart, hits)
        frozen = deepcopy((hits, r1))
        old = build_personality_model(r1, hits, catalog=baseline)
        new = build_personality_model(r1, hits, catalog=expanded)
        old_report = compose_narrative_n2(old)
        new_report = compose_narrative_n2(new)
        assert (hits, r1) == frozen
        assert old["relationship_discovery_enabled"] is False
        assert new["relationship_discovery_enabled"] is False
        assert old["catalog_review_status"] == new["catalog_review_status"] == "unverified"
        assert all(set(c["rule_ids"]) <= {h["rule_id"] for h in hits["signals"]}
                   for c in new["claims"])
        assert all(c["source_refs"] and c["source_review_statuses"]
                   for c in new["claims"])
        before_set = {c["content"]["selected_rule_id"] for c in old["claims"]
                      if c["kind"] == "axis-example"}
        after_set = {c["content"]["selected_rule_id"] for c in new["claims"]
                     if c["kind"] == "axis-example"}
        assert before_set <= after_set or old["plan"]["primary"] != new["plan"]["primary"]
        if after_set & new_rules:
            changes += 1
        if format_narrative_n2(old_report) != format_narrative_n2(new_report):
            assert any(c["kind"] == "axis-example" and c["meaning_ids"]
                       for c in new["claims"])
    assert changes >= 2
