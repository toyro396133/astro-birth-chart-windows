"""Focused R1 composition gates using real 0.2.0 rules and synthetic charts."""
from copy import deepcopy

from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.synthesis import MAX_NODES, format_synthesis, synthesize


def chart_for_path(*, mercury=35, unknown=False):
    # Sun in Aries -> initiative; Mercury in Taurus -> persistence;
    # Saturn in Capricorn -> responsibility. These are three distinct
    # chart observations; none of the individual rules states the path.
    signs = [(0,), (int(mercury // 30),), (9,)]
    bodies = [
        BodyPosition("שמש", 12.4, False, signs[0], house=None if unknown else 1),
        BodyPosition("מרקורי", mercury, False, signs[1], house=None if unknown else 2),
        BodyPosition("שבתאי", 286.0, False, signs[2], house=None if unknown else 10),
    ]
    return Chart(bodies, [], None if unknown else 12, None, unknown, [])


def run(chart):
    base = interpret_chart(chart)
    return base, synthesize(chart, base)


def generated(result):
    return [node for node in result["nodes"] if node["type"] == "synthesis"]


def test_three_observations_create_new_two_step_inference():
    base, result = run(chart_for_path())
    assert load_rulepack().version == "0.2.0"
    assert all("הנעה" not in hit["text"] or hit["axis"] != "אחריות"
               for hit in base["signals"])
    paths = {tuple(node["path"]) for node in generated(result)}
    assert ("יוזמה", "התמדה") in paths
    assert ("יוזמה", "התמדה", "אחריות") in paths
    deep = next(n for n in generated(result)
                if n["path"] == ["יוזמה", "התמדה", "אחריות"])
    assert deep["level"] == 2
    assert deep["strength"] > 0
    assert deep["audit_status"] == "hypothesis"
    assert len(deep["parents"]) == 2
    assert len(deep["independent_facts"]) == 3
    assert {"sun-sign-1", "mercury-sign-2", "saturn-sign-10"} <= set(deep["rule_ids"])
    assert deep["id"] in result["top_feature_ids"]
    assert "השערות" in format_synthesis(result)


def test_counterfactual_removes_only_affected_paths():
    _, first = run(chart_for_path())
    _, changed = run(chart_for_path(mercury=75))
    paths_a = {tuple(n["path"]) for n in generated(first)}
    paths_b = {tuple(n["path"]) for n in generated(changed)}
    assert ("יוזמה", "התמדה", "אחריות") in paths_a
    assert ("יוזמה", "התמדה", "אחריות") not in paths_b
    assert any(n["axis"] == "יוזמה" for n in changed["nodes"] if n["type"] == "axis")
    assert any(n["axis"] == "אחריות" for n in changed["nodes"] if n["type"] == "axis")


def test_duplicates_of_same_fact_are_one_supporting_witness():
    chart = chart_for_path()
    old = interpret_chart(chart)
    first = synthesize(chart, old)
    duplicated = deepcopy(old)
    hit = next(h for h in duplicated["signals"] if h["rule_id"] == "sun-sign-1")
    other = deepcopy(hit)
    other["rule_id"] = "test-equivalent-aries"
    duplicated["signals"].append(other)
    changed = synthesize(chart, duplicated)
    def get_path(report):
        return next(n for n in generated(report)
                    if n["path"] == ["יוזמה", "התמדה", "אחריות"])
    a, b = get_path(first), get_path(changed)
    assert a["strength"] == b["strength"]
    assert len(a["independent_facts"]) == len(b["independent_facts"]) == 3
    assert "test-equivalent-aries" in b["rule_ids"]
    assert a["evidence_roots"] == b["evidence_roots"]


def test_different_axes_same_underlying_observation_cannot_compose():
    chart = chart_for_path()
    base = interpret_chart(chart)
    report = deepcopy(base)
    other = deepcopy(next(h for h in report["signals"] if h["rule_id"] == "sun-sign-1"))
    other["rule_id"] = "test-duplicate-root-cross-axis"
    other["axis"] = "התמדה"
    report["signals"].append(other)
    # Remove the true persistence witness: any remaining persistence depends
    # on precisely the same Sun longitude as the initiative witness.
    report["signals"] = [h for h in report["signals"]
                         if h["rule_id"] != "mercury-sign-2"]
    result = synthesize(chart, report)
    assert ("יוזמה", "התמדה") not in {tuple(n["path"]) for n in generated(result)}


def test_unresolved_conflict_blocks_hypothesis_and_does_not_invent_context():
    chart = chart_for_path()
    report = deepcopy(interpret_chart(chart))
    conflict = deepcopy(next(h for h in report["signals"] if h["rule_id"] == "sun-sign-1"))
    conflict["rule_id"] = "test-opposite-on-same-sun"
    conflict["polarity"] = -1
    report["signals"].append(conflict)
    result = synthesize(chart, report)
    tension = next(t for t in result["tensions"] if t["axis"] == "יוזמה")
    assert tension["status"] == "unresolved"
    assert tension["context"] is None
    assert "body:שמש" in tension["shared_roots"]
    assert not any(n["path"][0] == "יוזמה" for n in generated(result))


def test_derived_nodes_form_acyclic_provenance_and_never_self_support():
    chart = chart_for_path()
    _, report = run(chart)
    ids = {n["id"] for n in report["nodes"]}
    rule_ids = {hit["rule_id"] for hit in interpret_chart(chart)["signals"]}
    for node in report["nodes"]:
        assert set(node["parents"]) <= ids
        assert node["id"] not in node["parents"]
        assert set(node["rule_ids"]) <= rule_ids
        if node["type"] == "synthesis":
            assert node["audit_status"] == "hypothesis"
            assert all(parent != node["id"] for parent in node["parents"])
            assert not any(r.startswith("synth-") for r in node["rule_ids"])
    assert len(report["nodes"]) <= MAX_NODES


def test_unknown_time_never_uses_house_or_aspect_as_proof():
    chart = chart_for_path(unknown=True)
    base, result = run(chart)
    assert base["time_mode"] == "unknown"
    assert not any("-house-" in id or "-square" in id or "-trine" in id
                   for id in (h["rule_id"] for h in base["signals"]))
    assert result["time_mode"] == "unknown"
    assert result["warnings"][-1].startswith("שעת הלידה")
    assert all(n["provisional_time"] for n in result["nodes"])
    for node in generated(result):
        assert all(all(not root.startswith("angle:") for root in w["roots"])
                   for w in node["independent_facts"])


def test_computed_dignity_is_separate_from_trait_score_and_limited_to_sign():
    chart = chart_for_path()
    _, result = run(chart)
    by_body = {s["body"]: s for s in result["factor_conditions"]}
    assert by_body["שמש"]["sign_only_points"] == 4  # exaltation in Aries
    assert by_body["שבתאי"]["sign_only_points"] == 5  # domicile in Capricorn
    assert all(s["scope"] == "partial-essential-dignity-not-trait-score"
               for s in by_body.values())
    assert all("source_refs" in n and "source_review_statuses" in n
               for n in result["nodes"])


def test_identity_deterministic_and_no_unfounded_abstraction():
    chart = chart_for_path()
    base, first = run(chart)
    assert first == synthesize(chart, base)
    no_path = Chart([BodyPosition("שמש", 12.4, False, (0,))],
                    [], None, None, True, [])
    _, result = run(no_path)
    assert not generated(result)
    assert not result["top_feature_ids"]
    assert "לא נמצאה שרשרת" in format_synthesis(result)


def test_extra_function_stage_extends_depth_without_fixed_level_count():
    chart = Chart([
        BodyPosition("שמש", 12.4, False, (0,)),
        BodyPosition("מרקורי", 255.0, False, (8,)),  # flexibility
        BodyPosition("מאדים", 45.0, False, (1,)),    # persistence
        BodyPosition("שבתאי", 285.0, False, (9,)),   # responsibility
    ], [], None, None, False, [])
    base, result = run(chart)
    assert {"יוזמה", "גמישות", "התמדה", "אחריות"} <= {
        a["axis"] for a in base["axes"]
    }
    paths = {tuple(n["path"]) for n in generated(result)}
    assert ("יוזמה", "גמישות", "התמדה", "אחריות") in paths
    assert max(n["level"] for n in generated(result)) >= 3


def test_synthetic_before_after_compares_hierarchic_results_without_pack_edits():
    chart = chart_for_path()
    base, inferred = run(chart)
    assert base["schema_version"] == inferred["schema_version"] == 1
    assert base["pack_version"] == "0.2.0"
    assert all("path" not in axis for axis in base["axes"])
    assert any(len(n["path"]) > 1 for n in generated(inferred))
    assert inferred["feedback_contract"]["automatic_learning_enabled"] is False
