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
        BodyPosition("שמש", 12.4, False, signs[0], house=None),
        BodyPosition("מרקורי", mercury, False, signs[1], house=None),
        BodyPosition("שבתאי", 286.0, False, signs[2], house=None),
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


# R1 independent-audit acceptance gates, kept deliberately small.
def _axis_path(result, wanted):
    return next(n for n in generated(result) if n["path"] == list(wanted))


def test_a01_path_proof_chooses_disjoint_alternatives_not_entire_axis_unions():
    chart = Chart([
        BodyPosition("שמש", 12.4, False, (0,)),
        BodyPosition("צדק", 13.0, False, (0,)),
        BodyPosition("מרקורי", 35.0, False, (1,)),
    ], [], None, None, False, [])
    report = deepcopy(interpret_chart(chart))
    sun = next(h for h in report["signals"] if h["rule_id"] == "sun-sign-1")
    persistence_on_sun = deepcopy(sun)
    persistence_on_sun.update(
        rule_id="test-sun-persistence", axis="התמדה", weight=3.0,
    )
    report["signals"].append(persistence_on_sun)
    result = synthesize(chart, report)
    node = _axis_path(result, ("יוזמה", "התמדה"))
    # A01: both axes offer Sun, yet there is a valid independent assignment.
    assert {"body:שמש", "body:צדק", "body:מרקורי"} >= set(node["evidence_roots"])
    assert len(node["independent_facts"]) == 2
    assert len(node["evidence_roots"]) == 2
    assert len({root for w in node["independent_facts"] for root in w["roots"]}) == 2
    assert node["proof_search"]["complete"]
    assert node["alternative_facts_by_axis"]
    assert any(node["alternative_facts_by_axis"].values())
    assert node["audit_status"] == "hypothesis"

    # Without Mercury, both persistence and initiative depend on Sun
    # or Jupiter; removing Jupiter too leaves no root-disjoint pair.
    no_alternative = deepcopy(report)
    no_alternative["signals"] = [
        h for h in no_alternative["signals"]
        if h["rule_id"] not in ("mercury-sign-2", "jupiter-sign-1")
    ]
    blocked = synthesize(chart, no_alternative)
    assert ("יוזמה", "התמדה") not in {
        tuple(n["path"]) for n in generated(blocked)
    }


def test_a02_bound_search_picks_two_independent_placements_over_one_aspect():
    from astrochart.synthesis import _independent, _choose_path_proof, _base_features

    def mock(axis, key, weight, rule_id):
        return {
            "rule_id": rule_id, "axis": axis, "polarity": 1,
            "weight": float(weight), "modifier_only": False,
            "evidence_key": key, "review_status": "unverified",
            "source_url": None, "evidence": key,
        }

    aspect = mock("יוזמה", "aspect:מרקורי:שמש:צמידות", 5, "aspect5")
    sun = mock("יוזמה", "placement:שמש:טלה", 4, "sun4")
    mercury = mock("יוזמה", "placement:מרקורי:טלה", 4, "mercury4")
    selected, dropped, limited = _independent([aspect, sun, mercury])
    assert not limited
    assert {g["evidence_key"] for g in selected} == {
        "placement:שמש:טלה", "placement:מרקורי:טלה",
    }
    assert [g["evidence_key"] for g in dropped] == ["aspect:מרקורי:שמש:צמידות"]

    # A high-weight overlapping choice must not veto a path if an
    # independent alternative exists for its first axis.
    persistence = mock("התמדה", "placement:מרקורי:טלה", 4, "persistent4")
    jupiter = mock("יוזמה", "placement:צדק:טלה", 2, "jupiter2")
    base, _ = _base_features({"signals": [aspect, sun, mercury, jupiter, persistence]})
    by_axis = {b["axis"]: b for b in base}
    chosen, alternatives, search_limited, states = _choose_path_proof(
        ("יוזמה", "התמדה"), by_axis
    )
    assert chosen is not None and len(chosen) == 2
    assert not search_limited and states > 0
    assert set(chosen[0]["roots"]).isdisjoint(chosen[1]["roots"])
    assert alternatives["יוזמה"]


def test_a03_summary_removes_prefix_suffix_containment_but_retains_ten_proofs():
    chart = Chart([
        BodyPosition("שמש", 12.4, False, (0,)),
        BodyPosition("מרקורי", 255.0, False, (8,)),
        BodyPosition("מאדים", 45.0, False, (1,)),
        BodyPosition("שבתאי", 285.0, False, (9,)),
    ], [], None, None, False, [])
    _, result = run(chart)
    paths = generated(result)
    assert len(paths) == 10
    assert len(result["top_feature_ids"]) < 6
    top = {node["id"]: node for node in paths
           if node["id"] in result["top_feature_ids"]}
    assert len(top) <= 3
    subsumed = result["summary"]["subsumed_by"]
    assert set(subsumed).isdisjoint(top)
    assert len(subsumed) + len(top) == 10
    for short_id, longer_id in subsumed.items():
        short = next(n for n in paths if n["id"] == short_id)
        long = top[longer_id]
        p, q = short["path"], long["path"]
        assert any(q[i:i + len(p)] == p for i in range(len(q) - len(p) + 1))
        assert short["rule_ids"] and short["independent_facts"]
    readable = format_synthesis(result)
    assert readable.count("    שרשרת: ") == len(result["summary"]["top_hypotheses"])
    assert result == synthesize(chart, interpret_chart(chart))


def test_a01_unselected_overlap_is_not_promoted_to_proof_root_or_weight():
    chart = chart_for_path()
    report = deepcopy(interpret_chart(chart))
    sun = next(h for h in report["signals"] if h["rule_id"] == "sun-sign-1")
    overlap = deepcopy(sun)
    overlap.update(rule_id="extra-initiative-on-mercury",
                   evidence_key="placement:מרקורי:שור", weight=5.0)
    report["signals"].append(overlap)
    result = synthesize(chart, report)
    path = _axis_path(result, ("יוזמה", "התמדה", "אחריות"))
    assert len(path["independent_facts"]) == 3
    assert len(path["evidence_roots"]) == 3
    assert len(set(path["evidence_roots"])) == 3
    assert path["strength"] == min(w["weight"] for w in path["independent_facts"])
    assert path["selected_witnesses_by_axis"]["יוזמה"]["evidence_key"] != (
        "placement:מרקורי:שור"
    )
    assert any(f["evidence_key"] == "placement:מרקורי:שור"
               for f in path["alternative_facts_by_axis"]["יוזמה"])
