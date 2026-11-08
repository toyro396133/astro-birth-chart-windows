"""Focused N1 checks: readable output may not invent R1 facts or claims."""
from copy import deepcopy

from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart
from astrochart.synthesis import synthesize
from astrochart.narrative import compose_narrative, format_narrative


def sample(*, unknown=False, estimated=False):
    chart = Chart([
        BodyPosition("שמש", 12.4, False, (0,)),
        BodyPosition("מרקורי", 35.0, False, (1,)),
        BodyPosition("שבתאי", 286.0, False, (9,)),
    ], [], None if unknown else 12.0, None, unknown, [],
        time_certainty="estimated" if estimated else "known")
    return chart


def run(chart):
    evidence = interpret_chart(chart)
    synthesis = synthesize(chart, evidence)
    return synthesis, compose_narrative(synthesis)


def all_paragraphs(narrative):
    return [p for section in narrative["sections"] for p in section["paragraphs"]]


def test_n1_combines_supported_chain_with_full_witness_lineage():
    synthesis, narrative = run(sample())
    text = format_narrative(narrative)
    paths = [n for n in synthesis["nodes"] if n["type"] == "synthesis"]
    assert paths
    assert "יוזמה" in text and "התמדה" in text and "אחריות" in text
    assert "השערה" in text and "לא אבחון" in text
    assert "אחוז" not in text

    by_id = {n["id"]: n for n in synthesis["nodes"]}
    process = [p for p in all_paragraphs(narrative) if p["kind"] == "process"]
    assert process
    assert len(process) <= 3
    for paragraph in process:
        node = by_id[paragraph["node_ids"][0]]
        assert node["type"] == "synthesis"
        assert paragraph["audit_status"] == "hypothesis"
        assert paragraph["rule_ids"] == sorted(set(node["rule_ids"]))
        assert paragraph["source_refs"] == sorted(set(node["source_refs"]))
        assert paragraph["source_review_statuses"] == sorted(set(node["source_review_statuses"]))
        assert len(node["independent_facts"]) == len(node["path"])

    # Rendering never edits the R1 report or rulepack.
    original = deepcopy(synthesis)
    assert compose_narrative(synthesis) == narrative
    assert synthesis == original


def test_n1_duplicate_top_id_does_not_add_a_paragraph_or_witness():
    synthesis, original = run(sample())
    changed = deepcopy(synthesis)
    changed["summary"]["top_hypotheses"] = (
        [changed["summary"]["top_hypotheses"][0]] * 5
        + changed["summary"]["top_hypotheses"]
    )
    narrative = compose_narrative(changed)
    assert narrative == original


def test_n1_unknown_and_estimated_time_remain_explicitly_provisional():
    for chart, mode, label in [
        (sample(unknown=True), "unknown", "שעת הלידה אינה ידועה"),
        (sample(estimated=True), "estimated", "שעת הלידה משוערת"),
    ]:
        synthesis, narrative = run(chart)
        assert synthesis["time_mode"] == mode
        assert narrative["time_mode"] == mode
        assert label in format_narrative(narrative)
        assert all(p["provisional_time"] for p in all_paragraphs(narrative))
        assert all(p["node_ids"] or p["kind"] != "process"
                   for p in all_paragraphs(narrative))
        # No original chart position, time, or aspect is added by N1.
        assert "longitude" not in narrative
        assert not any("aspect" in p for p in all_paragraphs(narrative))


def test_n1_unresolved_tension_never_gets_invented_context():
    chart = sample()
    evidence = deepcopy(interpret_chart(chart))
    hit = deepcopy(next(h for h in evidence["signals"]
                        if h["rule_id"] == "sun-sign-1"))
    hit.update(rule_id="test-negative-sun", polarity=-1)
    evidence["signals"].append(hit)
    synthesis = synthesize(chart, evidence)
    narrative = compose_narrative(synthesis)
    tensions = [p for p in all_paragraphs(narrative) if p["kind"] == "tension"]
    assert tensions and "יוזמה" in tensions[0]["text"]
    assert "בלתי מוכרע" in tensions[0]["text"]
    assert "test-negative-sun" in tensions[0]["rule_ids"]
    assert all(t["status"] == "unresolved" and t["context"] is None
               for t in synthesis["tensions"])
    assert all("יוזמה" not in n["path"] for n in synthesis["nodes"]
               if n["type"] == "synthesis")


def test_n1_empty_report_is_honest_and_no_unsupported_hypothesis():
    result = {
        "nodes": [], "summary": {"top_hypotheses": [], "leading_axes": []},
        "time_mode": "known", "warnings": [],
    }
    narrative = compose_narrative(result)
    assert narrative["displayed_hypothesis_ids"] == []
    assert "לא נמצאה שרשרת" in format_narrative(narrative)
    assert all(not p["rule_ids"] for p in all_paragraphs(narrative))
