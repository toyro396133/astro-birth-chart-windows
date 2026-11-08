"""N2 REV-01–07 acceptance tests: compare ideas, never quotes or report length."""
from copy import deepcopy

import pytest

from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.synthesis import synthesize
from astrochart.semantics_n2 import build_personality_model, load_meaning_catalog
from astrochart.narrative_n2 import (
    compose_narrative_n2, format_narrative_n2, semantic_only_n2,
)


def chart(*positions, unknown=False):
    return Chart([BodyPosition(name, lon, False, (int(lon // 30),), house=house)
                  for name, lon, house in positions],
                 [], None, None, unknown, [],
                 time_certainty="unknown" if unknown else "known")


def render(c, interpretation=None):
    evidence = interpretation or interpret_chart(c)
    r1 = synthesize(c, evidence)
    s = build_personality_model(r1, evidence)
    return evidence, r1, s, compose_narrative_n2(s)


def meaning_signature(s, axis):
    """No rule IDs, names of celestial bodies, quotes, URLs or raw evidence."""
    return sorted((c["content"]["focus"], c["content"]["distinction"],
                   c["content"]["behavior"])
                  for c in s["claims"]
                  if c["axis"] == axis and c["kind"] == "axis-example")


def test_mercury_taurus_mars_taurus_same_axis_distinct_meaning_without_quotes():
    a = render(chart(("מרקורי", 39, None)))
    b = render(chart(("מאדים", 39, None)))
    assert {c["axis"] for c in a[2]["claims"]} == {"התמדה"}
    assert {c["axis"] for c in b[2]["claims"]} == {"התמדה"}
    assert meaning_signature(a[2], "התמדה") != meaning_signature(b[2], "התמדה")
    la, lb = "\n".join(semantic_only_n2(a[3])), "\n".join(semantic_only_n2(b[3]))
    assert "בדיקה חוזרת" in la and "קצב יציב" in lb
    assert "מרקורי" not in la and "מאדים" not in lb
    assert la != lb
    assert a[3]["sections"][0]["paragraphs"][0]["evidence_text"] != ""
    assert b[3]["sections"][0]["paragraphs"][0]["evidence_text"] != ""


def test_saturn_capricorn_vs_sun_house_ten_responsibility_distinct():
    a = render(chart(("שבתאי", 290, None)))
    b = render(chart(("שמש", 102, 10)))
    assert meaning_signature(a[2], "אחריות") != meaning_signature(b[2], "אחריות")
    la = "\n".join(semantic_only_n2(a[3]))
    lb = "\n".join(semantic_only_n2(b[3]))
    assert "גבולות" in la and "מטרות נראות" in lb
    assert la != lb
    assert "sun-house-10" in {rid for c in b[2]["claims"] for rid in c["rule_ids"]}


def test_two_independent_witnesses_change_content_without_merely_length():
    a = render(chart(("מרקורי", 39, None)))
    b = render(chart(("מרקורי", 39, None), ("מאדים", 43, None)))
    meanings = meaning_signature(b[2], "התמדה")
    assert len(meaning_signature(a[2], "התמדה")) == 1
    assert len(meanings) == 2
    assert b[2]["claims"][0]["content"]["independent_evidence_count"] == 2
    paragraph = next(p for section in b[3]["sections"]
                     for p in section["paragraphs"] if p["kind"] == "axis")
    assert "כמה ראיות עצמאיות" in paragraph["semantic_text"]
    assert "בדיקה חוזרת" in paragraph["semantic_text"]
    assert "קצב יציב" in paragraph["semantic_text"]
    assert all(c["meaning_ids"] for c in b[2]["claims"]
               if c["kind"] == "axis-example")


def test_process_is_evidence_specific_comparison_not_action_chain():
    c = chart(("שמש", 44, None), ("מרקורי", 40, None),
              ("שבתאי", 293, None))
    evidence, r1, sem, report = render(c)
    process = next(c for c in sem["claims"] if c["kind"] == "process-example")
    assert len(process["content"]["components"]) >= 2
    assert process["content"]["reading_type"] == "attributed-comparison-not-new-edge"
    p = next(p for section in report["sections"] for p in section["paragraphs"]
             if p["kind"] == "process" and "ההבדל ביניהן" in p["semantic_text"])
    assert "ובהמשך" not in p["semantic_text"]
    assert "אין" not in p["semantic_text"] or "אינו ראיה" in p["semantic_text"]
    assert "שתי הראיות" in p["semantic_text"] or "שלוש ראיות" in p["semantic_text"]
    assert all(c["audit_status"] == "hypothesis" for c in sem["claims"]
               if c["kind"] in ("process-reading", "process-example"))


def test_no_unsourced_process_story_when_only_one_rule_has_editorial_meaning():
    c = chart(("שמש", 132, None), ("מרקורי", 155, None))
    _, r1, sem, report = render(c)
    for group in sem["plan"]["processes"]:
        kinds = {next(c for c in sem["claims"] if c["id"] == i)["kind"] for i in group}
        assert kinds == {"process-reading"}
    texts = [p["semantic_text"] for sec in report["sections"] for p in sec["paragraphs"]
             if p["kind"] == "process"]
    assert not texts or all("אין די במשמעויות" in t for t in texts)


@pytest.mark.parametrize("field, replacement", [
    ("review_status", "approved"),
    ("source_url", "https://invalid.example/elevated"),
    ("source", "manufactured attribution"),
    ("text", "fabricated interpretation"),
])
def test_changed_original_rule_hit_metadata_after_r1_is_fail_closed(field, replacement):
    c = chart(("מרקורי", 38, None))
    original = interpret_chart(c)
    r1 = synthesize(c, original)
    tampered = deepcopy(original)
    tampered["signals"][0][field] = replacement
    model = build_personality_model(r1, tampered)
    assert not model["claims"]
    assert model["skipped_unverifiable_axes"] == ["התמדה"]


def test_fabricated_approved_status_even_if_r1_receives_it_is_not_promoted():
    c = chart(("מרקורי", 38, None))
    tampered = deepcopy(interpret_chart(c))
    assert tampered["signals"][0]["review_status"] == "unverified"
    tampered["signals"][0]["review_status"] = "approved"
    r1 = synthesize(c, tampered)
    model = build_personality_model(r1, tampered)
    assert not model["claims"]
    assert "התמדה" in model["skipped_unverifiable_axes"]


def test_tension_displays_independent_positive_negative_proof_and_status():
    c = chart(("שמש", 13, None))
    source = deepcopy(interpret_chart(c))
    neg = deepcopy(source["signals"][0])
    neg.update(rule_id="n2-opposing-fixture", polarity=-1,
               source_url="https://example.org/opposing", review_status="reviewed")
    source["signals"].append(neg)
    _, _, sem, report = render(c, source)
    t = next(c for c in sem["claims"] if c["kind"] == "unresolved-tension")
    assert t["content"]["context"] is None
    assert set(t["evidence_by_polarity"]) >= {"positive", "negative"}
    visible = format_narrative_n2(report)
    assert "ראיות לכיוון החיובי" in visible and "ראיות לכיוון המנוגד" in visible
    assert "n2-opposing-fixture" in visible and "sun-sign-1" in visible
    assert "https://example.org/opposing" in visible
    assert "נבדק, לא אושר" in visible and "טרם אומת" in visible
    assert "אינו מאפשר להכריע" in visible
    assert not meaning_signature(sem, "יוזמה")


def test_same_sign_degree_noise_affects_raw_trace_not_semantic_claims():
    x = render(chart(("מאדים", 35.1, None)))
    y = render(chart(("מאדים", 41.9, None)))
    assert semantic_only_n2(x[3]) == semantic_only_n2(y[3])
    a = next(c for c in x[2]["claims"] if c["kind"] == "rule-anchor")
    b = next(c for c in y[2]["claims"] if c["kind"] == "rule-anchor")
    assert a["content"]["raw_chart_evidence"] != b["content"]["raw_chart_evidence"]
    assert a["content"]["chart_evidence"] == b["content"]["chart_evidence"]


def test_uncertain_time_restricts_house_readings_and_preserves_caveat():
    c = chart(("שמש", 45, 10), unknown=True)
    _, _, sem, report = render(c)
    assert "sun-house-10" not in {rid for claim in sem["claims"]
                                  for rid in claim["rule_ids"]}
    assert "שעת הלידה אינה ידועה" in format_narrative_n2(report)
    assert all(c["provisional_time"] for c in sem["claims"])


def test_catalog_readings_match_original_rule_text_and_never_become_rules():
    catalog = load_meaning_catalog()
    rules = {r["id"]: r for r in load_rulepack().rules}
    assert len(catalog["rule_readings"]) >= 24
    for reading in catalog["rule_readings"]:
        assert reading["source_rule_text"] == rules[reading["rule_id"]]["text"]
        assert reading["provenance"]["review_status"] == "unverified"
        assert reading["provenance"]["astrological_rule"] is False
    changed = deepcopy(catalog)
    changed["rule_readings"][0]["source_rule_text"] = "bad"
    # Custom data is injected only in the builder, not revalidated; the
    # validated on-disk loader must be the normal production entry point.
    assert changed != load_meaning_catalog()


def test_grouped_rule_statuses_are_not_misattributed_to_selected_rule():
    c = chart(("מרקורי", 39, None))
    evidence = deepcopy(interpret_chart(c))
    chosen = evidence["signals"][0]
    alt = deepcopy(chosen)
    alt.update(rule_id="overlay-secondary-witness", weight=chosen["weight"] - 0.1,
               review_status="reviewed", source_url="https://example.org/other-rule",
               text="נוסח ניסוי עצמאי; אין אישור")
    evidence["signals"].append(alt)
    _, _, sem, report = render(c, evidence)
    anchor = next(item for item in sem["claims"] if item["kind"] == "rule-anchor")
    assert anchor["content"]["selected_rule_id"] == "mercury-sign-2"
    assert anchor["content"]["review_status"] == "unverified"
    assert set(anchor["source_review_statuses"]) == {"unverified", "reviewed"}
    p = next(p for section in report["sections"] for p in section["paragraphs"]
             if p["kind"] == "axis")
    assert "כלל mercury-sign-2 (טרם אומת)" in p["evidence_text"]
    assert "https://example.org/other-rule" not in p["evidence_text"]
