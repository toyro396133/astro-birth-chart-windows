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
    assert "השערה" in text and "אינה אבחון" in text
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


def test_n1_tension_has_exact_positive_and_negative_provenance():
    chart = sample()
    evidence = deepcopy(interpret_chart(chart))
    original_hit = deepcopy(next(h for h in evidence["signals"]
                                 if h["rule_id"] == "sun-sign-1"))
    original_hit.update(rule_id="test-n1-negative", polarity=-1,
                        review_status="reviewed",
                        source_url="https://example.org/test-opposition")
    evidence["signals"].append(original_hit)
    r1 = synthesize(chart, evidence)
    n1 = compose_narrative(r1)
    t = next(p for p in all_paragraphs(n1) if p["kind"] == "tension"
             and "יוזמה" in p["text"])
    axis = next(n for n in r1["nodes"]
                if n["type"] == "axis" and n["axis"] == "יוזמה")
    from astrochart.narrative import _collect_provenance
    positive = _collect_provenance(axis["independent_facts"])
    negative = _collect_provenance(axis["counter_facts"])
    assert t["node_ids"] == [axis["id"]]
    assert t["audit_status"] == "unresolved"
    assert t["evidence_by_polarity"]["positive"] == positive
    assert t["evidence_by_polarity"]["negative"] == negative
    assert set(t["rule_ids"]) == set(positive["rule_ids"] + negative["rule_ids"])
    assert set(t["source_refs"]) == set(
        positive["source_refs"] + negative["source_refs"])
    assert set(t["source_review_statuses"]) == set(
        positive["source_review_statuses"] + negative["source_review_statuses"])
    assert "test-n1-negative" not in positive["rule_ids"]
    assert "test-n1-negative" in negative["rule_ids"]
    assert "https://example.org/test-opposition" in negative["source_refs"]
    assert "https://example.org/test-opposition" not in positive["source_refs"]
    assert t["provisional_time"] == axis["provisional_time"]


def test_n1_discloses_mixed_source_review_states_without_approving_paths():
    chart = sample()
    evidence = deepcopy(interpret_chart(chart))
    statuses = {
        "sun-sign-1": "unverified",
        "mercury-sign-2": "reviewed",
        "saturn-sign-10": "approved",
    }
    for hit in evidence["signals"]:
        if hit["rule_id"] in statuses:
            hit["review_status"] = statuses[hit["rule_id"]]
    n1 = compose_narrative(synthesize(chart, evidence))
    claim = next(p for p in all_paragraphs(n1) if p["kind"] == "process")
    assert {"unverified", "reviewed", "approved"} <= set(
        claim["source_review_statuses"])
    provenance = next(p for p in all_paragraphs(n1)
                      if p["kind"] == "source-disclosure")
    assert {"unverified", "reviewed", "approved"} <= set(
        provenance["source_review_statuses"])
    readable = format_narrative(n1)
    assert "טרם אומתו" in readable
    assert "נבדקו אך לא קיבלו" in readable
    assert "מסומנים 'מאושר'" in readable
    assert "אינו מאשר את המעברים" in readable
    assert claim["audit_status"] == "hypothesis"
    ordinary = format_narrative(run(sample())[1])
    assert "אף כלל המוצג כאן אינו מסומן 'מאושר'" in ordinary


def test_n1_fills_four_axis_slots_from_r1_nodes_after_top_five_conflict():
    from astrochart.synthesis import FUNCTIONS
    template = deepcopy(interpret_chart(sample())["signals"][0])
    report = {"signals": [], "time_mode": "known",
              "time_uncertain": False, "pack_version": "fixture"}
    for index, axis in enumerate(FUNCTIONS):
        hit = deepcopy(template)
        hit.update(axis=axis, polarity=1, weight=10 - index if index < 5 else 1,
                   rule_id=f"n1-axis-positive-{index}",
                   evidence_key=f"n1-fixture-axis-{index}")
        report["signals"].append(hit)
        if index < 5:
            negative = deepcopy(hit)
            negative.update(rule_id=f"n1-axis-negative-{index}", polarity=-1,
                            evidence_key=f"n1-fixture-negative-{index}")
            report["signals"].append(negative)
    r1 = synthesize(None, report)
    assert len(r1["nodes"]) >= 9
    assert len(r1["summary"]["leading_axes"]) == 5
    assert all(axis in {t["axis"] for t in r1["tensions"]}
               for axis in r1["summary"]["leading_axes"])
    # Isolate the standalone-axis allocator from the path display cap.
    r1["summary"]["top_hypotheses"] = []
    narrative = compose_narrative(r1)
    standalone = [p for p in all_paragraphs(narrative) if p["kind"] == "axis"]
    assert len(standalone) == 4
    assert len(narrative["displayed_axis_ids"]) == 4
    assert all(p["node_ids"][0] in {n["id"] for n in r1["nodes"]}
               for p in standalone)
    assert all(p["source_refs"] or p["rule_ids"] for p in standalone)
    assert not set(narrative["displayed_axis_ids"]) & {
        n["id"] for n in r1["nodes"]
        if n.get("axis") in r1["summary"]["leading_axes"]}


def test_n1_hypothesis_explains_existing_r1_functional_mapping():
    r1, n1 = run(sample())
    text = format_narrative(n1)
    assert "מהנעה" in text and "בקרה" in text
    assert "מעבר" in text and "חיבור סמלי בין" not in text
    assert "לכל אחת מ־3 החוליות" in text
    assert "עוגני הראיות שנבחרו ב־R1" in text
    process = next(p for p in all_paragraphs(n1) if p["kind"] == "process")
    assert process["audit_status"] == "hypothesis"
    overview = next(p for p in all_paragraphs(n1) if p["kind"] == "overview")
    assert overview["node_ids"] == process["node_ids"]
    assert overview["source_refs"] == process["source_refs"]


def test_n1_rejects_supplied_process_with_overlapping_proof_roots():
    r1, _ = run(sample())
    changed = deepcopy(r1)
    target = next(n for n in changed["nodes"] if n["type"] == "synthesis"
                  and len(n["path"]) == 3)
    target["independent_facts"][1]["roots"] = list(
        target["independent_facts"][0]["roots"])
    result = compose_narrative(changed)
    assert target["id"] not in result["displayed_hypothesis_ids"]
