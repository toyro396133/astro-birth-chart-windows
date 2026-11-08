"""R2 falsification, novelty, provenance, determinism and R1 isolation tests."""
from copy import deepcopy
import json

import pytest

from astrochart.discovery_r2 import discover
from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart
from astrochart.synthesis import synthesize


A, B, C, D, E = "יוזמה", "רגישות", "חשיבה", "הרמוניה", "עצמאות"


def case(cid, axes=(A, B, C), *, uncertain=False, conflict=False,
         shared_roots=False, known=(), alternatives=False):
    """A minimal *R1-shaped* structured fixture; not claimed to be a chart."""
    nodes = []
    for j, axis in enumerate(axes):
        root = "body:shared" if shared_roots else f"body:planet-{cid}-{j}"
        choices = [{
            "evidence_key": f"placement:planet-{cid}-{j}:sign",
            "weight": 2.0 + j / 10,
            "roots": [root],
            "rule_ids": [f"rule-{cid}-{j}"],
            "source_refs": [f"https://example.org/{axis}"],
            "review_statuses": ["reviewed"],
        }]
        if alternatives and j == 1:
            choices.insert(0, {
                "evidence_key": f"placement:overlap-{cid}-j1",
                "weight": 5.0, "roots": [f"body:planet-{cid}-0"],
                "rule_ids": [f"alternate-{cid}"],
                "source_refs": ["https://example.org/alternate"],
                "review_statuses": ["unverified"],
            })
        nodes.append({
            "id": f"r1-axis-{cid}-{j}", "axis": axis, "type": "axis",
            "path": [axis], "available_facts": choices, "counter_facts": [],
            "selection_search_limited": False,
            "has_unresolved_tension": conflict and axis == B,
        })
    if known:
        nodes.append({
            "id": f"r1-previous-path-{cid}", "type": "synthesis",
            "path": list(known), "audit_status": "hypothesis",
        })
    tensions = ([{
        "axis": B, "status": "unresolved",
        "positive_rule_ids": ["source-pos"],
        "negative_rule_ids": ["source-neg"],
        "context": None,
    }] if conflict else [])
    return {"id": cid, "synthesis": {
        "schema_version": 1, "engine_version": "0.1.0",
        "profile_id": "western-tropical-whole-sign-r1",
        "source_rule_pack": "0.2.0",
        "time_mode": "unknown" if uncertain else "known",
        "summary": {"proof_search_limited_paths": []},
        "nodes": nodes, "tensions": tensions,
    }}


def training():
    return [case(f"positive-{i}", (A, B, C)) for i in range(5)] + [
        case(f"control-{i}", (D, E)) for i in range(5)
    ]


class MemberLookup(dict):
    """Tests query unordered combinations by their logical member set."""
    @staticmethod
    def normalize(key):
        return tuple(sorted(key))

    def __contains__(self, key):
        return super().__contains__(self.normalize(key))

    def __getitem__(self, key):
        return super().__getitem__(self.normalize(key))

    def get(self, key, default=None):
        return super().get(self.normalize(key), default)


def by_members(result):
    return MemberLookup({tuple(h["members"]): h for h in result["hypotheses"]})


def test_discovers_unprogrammed_pairs_and_higher_abstraction():
    result = discover(training())
    pairs = by_members(result)
    assert (A, B) in pairs and (A, B, C) in pairs
    deep = pairs[(A, B, C)]
    assert deep["status"] == "hypothesis"
    assert deep["relation_type"] == "unreviewed-recurrent-conjunction"
    assert deep["level"] == 1
    assert len(deep["parent_hypothesis_ids"]) >= 2
    assert deep["metrics"]["independent_support_count"] == 5
    assert deep["metrics"]["lift_over_independent_presence"] > 1
    assert len(deep["support_cases"]) == 5
    assert all(len(p["selected_witnesses"]) == 3 for p in deep["support_cases"])
    assert all(len(p["evidence_roots"]) == 3 for p in deep["support_cases"])
    assert set(deep["source_refs"])
    assert not deep["approved_for_r1"]
    assert result["r1_unchanged"] and not result["learning_enabled_in_product"]
    assert result["summary"]["novel_higher_structures"] >= 1


def test_existing_r1_path_is_not_claimed_as_novel_relation():
    corpus = training()
    corpus[0] = case("positive-0", (A, B, C), known=(A, B))
    result = discover(corpus)
    assert (A, B) not in by_members(result)
    assert (A, C) in by_members(result)
    assert result["summary"]["observed_r1_compositions"] >= 1


def test_existing_r1_three_axis_path_is_not_rebranded_as_abstraction():
    corpus = training()
    corpus[0] = case("positive-0", (A, B, C), known=(A, B, C))
    assert (A, B, C) not in by_members(discover(corpus))


def test_one_repeated_chart_is_not_a_population():
    first = case("once")
    duplicates = [first] + [
        {"id": f"copy-{i}", "synthesis": deepcopy(first["synthesis"])}
        for i in range(5)
    ]
    output = discover(duplicates, min_support=2)
    assert not output["hypotheses"]
    assert len(output["duplicate_cases"]) == 5
    assert output["summary"]["train_eligible_cases"] == 1


def test_shared_observation_cannot_support_pair_or_triple():
    samples = [case(f"bad-{i}", (A, B, C), shared_roots=True)
               for i in range(5)]
    samples += [case(f"control-{i}", (D, E)) for i in range(5)]
    result = discover(samples)
    assert not any({A, B} <= set(h["members"]) for h in result["hypotheses"])


def test_alternative_witness_used_when_high_weight_would_overlap():
    samples = [case(f"positive-{i}", (A, B, C), alternatives=True)
               for i in range(5)]
    samples += [case(f"control-{i}", (D, E)) for i in range(5)]
    result = discover(samples)
    item = by_members(result)[(A, B)]
    proofs = item["support_cases"]
    assert len(proofs) == 5
    assert all(len(x["evidence_roots"]) == 2 for x in proofs)
    assert all(not any(w["evidence_key"].startswith("placement:overlap-")
                       for w in x["selected_witnesses"]) for x in proofs)


def test_heldout_counterexamples_reported_not_hidden():
    heldout = [
        case("val-full", (A, B, C)), case("val-partial", (A,)),
        case("val-neither", (D, E)),
    ]
    result = discover(training(), heldout)
    h = by_members(result)[(A, B, C)]
    val = h["validation"]
    assert val["status"] == "fails-prespecified-symbolic-holdout-gate"
    assert val["generalization_demonstrated"] is False
    assert val["metrics"]["symbolic_ratio_denominator"] == 2
    assert val["metrics"]["independent_support_count"] == 1
    assert val["metrics"]["partial_counterexample_count"] == 1
    assert val["counterexamples"][0]["case_id"] == "val-partial"
    assert "absence" not in val["counterexamples"][0]["meaning"]
    assert result["summary"]["validation_eligible_cases"] == 3


def test_counterfactual_removing_axis_destroys_local_support_not_other_axes():
    initial = training()
    base = discover(initial)
    mutated = deepcopy(initial)
    mutated[0] = case("positive-0", (A, C))
    later = discover(mutated)
    first = by_members(base)[(A, B, C)]
    second = by_members(later)[(A, B, C)]
    assert second["metrics"]["independent_support_count"] == 4
    assert len(second["counterexamples"]) > len(first["counterexamples"])
    assert A in mutated[0]["synthesis"]["nodes"][0]["axis"]


def test_proof_and_sources_auditable_all_the_way_to_r1():
    h = by_members(discover(training()))[(A, B)]
    for proof in h["support_cases"]:
        assert len(proof["rule_ids"]) == 2
        assert len(proof["node_ids"]) == 2
        assert len(proof["source_refs"]) == 2
        assert proof["source_review_statuses"] == ["reviewed"]
        assert all(w["rule_ids"] and w["source_refs"] and w["roots"]
                   for w in proof["selected_witnesses"])


def test_tension_and_birth_time_uncertainty_are_explicit_exclusions():
    items = training()
    items += [case("uncertain", (A, B, C), uncertain=True),
              case("tension", (A, B, C), conflict=True)]
    result = discover(items)
    assert len(result["excluded_cases"]) == 2
    t = next(x for x in result["excluded_cases"] if x["case_id"] == "tension")
    assert t["tensions"][0]["context"] is None
    assert t["tensions"][0]["positive_rule_ids"] == ["source-pos"]
    assert result["summary"]["train_eligible_cases"] == 10


def test_unknown_time_rejects_house_or_aspect_witness():
    entry = case("unknown", (A, B), uncertain=True)
    fact = entry["synthesis"]["nodes"][0]["available_facts"][0]
    fact["evidence_key"] = "house:שמש:1"
    with pytest.raises(ValueError, match="unknown-time"):
        discover([entry])


def test_deterministic_order_independent_of_case_order():
    data = training()
    one = discover(data)
    two = discover(list(reversed(data)))
    assert one == two
    assert json.dumps(one, ensure_ascii=False, sort_keys=True) == json.dumps(
        two, ensure_ascii=False, sort_keys=True)


def test_non_evidence_label_changes_do_not_change_mining_statistics():
    baseline = training()
    edited = deepcopy(baseline)
    for item in edited:
        item["synthesis"]["editorial_title"] = "a harmless rewritten heading"
    a, b = discover(baseline), discover(edited)
    assert by_members(a).keys() == by_members(b).keys()
    for members in by_members(a):
        assert by_members(a)[members]["metrics"] == by_members(b)[members]["metrics"]


def test_no_generalization_from_single_case_or_low_lift():
    assert not discover([case("single")])["hypotheses"]
    equal_counts = [case(f"x-{i}", (A, B)) for i in range(4)] + [
        case(f"y-{i}", (A,)) for i in range(4)] + [
        case(f"z-{i}", (B,)) for i in range(4)]
    assert not by_members(discover(equal_counts, min_lift=1.1)).get((A, B))


def test_abstraction_levels_grow_with_evidence_without_fixed_depth():
    corpus = [case(f"p-{i}", (A, B, C, D, E)) for i in range(5)]
    corpus += [case(f"n-{i}", (D,)) for i in range(5)]
    # Lower the partial-exposure threshold deliberately in this stress case.
    result = discover(corpus, min_precision=0.5)
    high = next(h for h in result["hypotheses"] if len(h["members"]) == 5)
    assert high["level"] == 3
    assert len(high["parent_hypothesis_ids"]) == 5


def test_incomplete_search_or_counter_facts_fail_closed():
    cases = training()
    cases[0]["synthesis"]["summary"]["proof_search_limited_paths"] = [[A, B]]
    cases[1]["synthesis"]["nodes"][0]["counter_facts"] = [{"rule_id": "counter"}]
    output = discover(cases, min_support=3)
    assert {c["case_id"] for c in output["excluded_cases"]} == {
        "positive-0", "positive-1"}


def test_reject_duplicate_ids_overlap_leakage_and_mixed_profiles():
    with pytest.raises(ValueError, match="unique"):
        discover([case("same"), case("same", (D,))])
    with pytest.raises(ValueError, match="leakage"):
        discover(training(), [case("positive-0", (D, E))])
    with pytest.raises(ValueError, match="leaked"):
        discover(training(), [{"id": "holdout-copy",
                             "synthesis": deepcopy(training()[0]["synthesis"])}])
    mixed = training()
    mixed[-1]["synthesis"]["profile_id"] = "other-system"
    with pytest.raises(ValueError, match="mixed"):
        discover(mixed)


@pytest.mark.parametrize("field,value", [
    ("roots", []), ("rule_ids", []), ("weight", float("nan")),
    ("review_statuses", "reviewed"), ("source_refs", None)])
def test_bad_evidence_fails_closed(field, value):
    sample = case("tampered", (A, B))
    sample["synthesis"]["nodes"][0]["available_facts"][0][field] = value
    with pytest.raises(ValueError):
        discover([sample])


def test_original_r1_chart_input_is_consumed_without_modifying_it():
    chart = Chart([
        BodyPosition("שמש", 12.4, False, (0,)),
        BodyPosition("מרקורי", 35.0, False, (1,)),
        BodyPosition("שבתאי", 286.0, False, (9,)),
    ], [], None, None, False, [])
    interpreted = interpret_chart(chart)
    r1 = synthesize(chart, interpreted)
    snapshot = deepcopy(r1)
    result = discover([{"id": "actual-r1-case", "synthesis": r1}])
    assert r1 == snapshot
    assert result["schema_version"] == 1
    assert result["summary"]["novel_hypotheses"] == 0
    assert result["profile_id"] == r1["profile_id"]
    assert result["source_rule_pack"] == "0.2.0"


def test_source_evidence_key_cannot_map_to_two_incompatible_roots():
    sample = case("inconsistent", (A,))
    facts = sample["synthesis"]["nodes"][0]["available_facts"]
    alt = deepcopy(facts[0])
    alt["roots"] = ["body:different"]
    facts.append(alt)
    with pytest.raises(ValueError, match="inconsistent roots"):
        discover([sample])


def test_reproducible_experiment_uses_real_r1_and_holdout_counterfactual():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).parents[1] / "scripts" / "run_r2_experiment.py"
    spec = importlib.util.spec_from_file_location("r2_real_experiment", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run_experiment()
    assert result["r1_baseline"]["train_reports"] == 13
    assert result["r2"]["summary"]["train_eligible_cases"] == 12
    assert result["r2"]["summary"]["validation_eligible_cases"] == 3
    assert not result["r1_baseline"]["has_cross_domain_initiative_sensitivity_thinking_path"]
    # The original trial repeated one physical evidence signature six times.
    # R2 must NOT present this as independent learning/generalization.
    assert not result["target_cross_domain_pattern"]["found"]
    assert result["r2"]["summary"]["recurrent_insufficient_diversity_count"] >= 1
    assert result["r2"]["summary"]["level_2_semantic_relations_demonstrated"] is False


def test_a_many_editorial_copies_cannot_mint_independent_evidence():
    original = case("copy-template", (A, B))
    copies = [original]
    for i in range(25):
        changed = deepcopy(original)
        changed["id"] = f"copy-edited-{i}"
        changed["synthesis"]["editorial_title"] = f"headline-{i}"
        changed["synthesis"]["nodes"][0]["label"] = f"caption-{i}"
        copies.append(changed)
    corpus = copies + [case(f"negative-{i}", (D, E)) for i in range(5)]
    out = discover(corpus)
    assert out["summary"]["train_eligible_cases"] == 6
    assert len(out["duplicate_cases"]) == 25
    assert not any({A, B} <= set(h["members"]) for h in out["hypotheses"])


def test_a_distinct_declared_records_kept_but_not_mistaken_for_diversity():
    first = case("same-pattern", (A, B))
    corpus = []
    for i in range(6):
        e = deepcopy(first)
        e["id"] = f"record-{i}"
        e["source_id"] = "source-one"
        e["independent_record_id"] = f"subject-{i}"
        corpus.append(e)
    corpus += [case(f"controlx-{i}", (D, E)) for i in range(6)]
    out = discover(corpus)
    assert out["summary"]["train_eligible_cases"] == 12
    p = next(x for x in out["recurring_but_not_diverse_patterns"]
             if set(x["members"]) == {A, B})
    assert p["metrics"]["supporting_report_count"] == 6
    assert p["metrics"]["distinct_evidence_signature_count"] == 1
    assert p["metrics"]["distinct_data_template_count"] == 1
    assert p["metrics"]["declared_data_source_count"] == 1
    assert not p["metrics"]["source_independence_verified"]
    assert not any(set(h["members"]) == {A, B} for h in out["hypotheses"])


def test_b_authored_but_unobserved_directed_path_is_not_novel():
    from astrochart.discovery_r2 import _ontology
    assert len(_ontology()["directed_paths"]) == 26
    corpus = [case(f"functional-{i}", (A, "גמישות")) for i in range(5)]
    corpus += [case(f"ctrl-{i}", (D, E)) for i in range(5)]
    out = discover(corpus)
    m = next(x for x in out["predefined_r1_patterns"]
             if set(x["members"]) == {A, "גמישות"})
    assert m["classification"] == "authored-r1-path-not-observed"
    assert not any(set(h["members"]) == {A, "גמישות"} for h in out["hypotheses"])
    assert out["summary"]["possible_r1_directed_compositions"] == 26


def test_c_validation_reused_target_proof_is_not_new_generalization():
    train = training()
    holdout = deepcopy(train[0])
    holdout["id"] = "reused-pair-but-full-chart-different"
    holdout["synthesis"]["nodes"].append(
        case("extra", (D,))["synthesis"]["nodes"][0])
    output = discover(train, [holdout])
    h = by_members(output)[(A, B)]
    assert h["validation"]["status"] == "generalization-unproven-no-novel-positive-signatures"
    assert h["validation"]["metrics"]["reused_training_signature_count"] == 1
    assert h["validation"]["metrics"]["distinct_evidence_signature_count"] == 0


def test_d_source_review_vocabulary_and_missing_provenance():
    case_bad = case("badstatus", (A, B))
    case_bad["synthesis"]["nodes"][0]["available_facts"][0][
        "review_statuses"] = ["verified"]  # not a permitted R1 value
    with pytest.raises(ValueError, match="status"):
        discover([case_bad])
    corpus = training()
    for sample in corpus[:5]:
        for node in sample["synthesis"]["nodes"]:
            for fact in node.get("available_facts", []):
                fact["source_refs"] = []
                fact["review_statuses"] = ["unverified"]
    out = discover(corpus)
    h = by_members(out)[(A, B)]
    assert h["provenance_quality"]["all_supporting_reports_unverified_or_missing"]
    assert h["provenance_quality"]["missing_sources_or_statuses"] == 5
    assert not h["provenance_quality"]["any_source_approved_automatically"]


def test_e_canonical_identity_changes_only_on_source_pack_or_ontology():
    original = training()
    first = by_members(discover(original))[(A, B)]["id"]
    edited = deepcopy(original)
    for row in edited:
        row["synthesis"]["editorial_title"] = "changed without new evidence"
    assert by_members(discover(edited))[(A, B)]["id"] == first
    updated = deepcopy(original)
    for row in updated:
        row["synthesis"]["source_rule_pack"] = "0.2.1"
    changed = by_members(discover(updated))[(A, B)]["id"]
    assert changed != first


def test_f_uncertain_r1_search_and_cutoff_are_reported_separately(monkeypatch):
    import astrochart.discovery_r2 as engine
    corpus = training()
    monkeypatch.setattr(engine, "MAX_PROOF_STATES", 1)
    limited = discover(corpus)
    assert limited["summary"]["candidate_enumeration_complete"]
    assert not limited["summary"]["witness_proof_search_complete"]
    assert not limited["summary"]["search_complete"]
    assert limited["search"]["resource_affected_candidates"]
    assert all(x["case_ids"] for x in limited["search"]["resource_affected_candidates"])

    monkeypatch.setattr(engine, "MAX_PROOF_STATES", 20000)
    report = training()
    report[0]["synthesis"]["summary"]["proof_search_limited_paths"] = [[A, B]]
    output = discover(report)
    assert not output["summary"]["r1_input_search_complete"]
    assert "positive-0" in output["search"]["r1_resource_excluded_case_ids"]


def test_g_metrics_include_full_part_absent_dependent_and_exclusion():
    group = [case(f"yes-{i}", (A, B)) for i in range(5)]
    group += [case("partial", (A,))] + [case(f"absent-{i}", (D,)) for i in range(4)]
    group += [case("dependent", (A, B), shared_roots=True)]
    group += [case("uncertainty", (A, B), uncertain=True)]
    out = discover(group)
    h = by_members(out)[(A, B)]
    m = h["metrics"]
    assert m["independent_support_count"] == 5
    assert m["partial_counterexample_count"] == 1
    assert m["absent_case_count"] == 4
    assert m["dependent_cooccurrence_count"] == 1
    assert m["incomplete_proof_count"] == 0
    assert m["excluded_case_count"] == 1
    assert m["symbolic_ratio_numerator"] == 5
    assert m["symbolic_ratio_denominator"] == 6
    assert m["symbolic_ratio_wilson_95_case_based"] is not None
    assert "coactivation_precision" not in m


def test_r1_axis_proof_cap_marks_entire_search_incomplete():
    cases = training()
    cases[0]["synthesis"]["nodes"][0]["selection_search_limited"] = True
    out = discover(cases)
    assert not out["summary"]["r1_input_search_complete"]
    assert "positive-0" in out["search"]["r1_resource_excluded_case_ids"]


def test_heldout_witness_budget_also_marks_global_search_incomplete(monkeypatch):
    import astrochart.discovery_r2 as engine
    actual = engine._joint

    def limited_holdout(record, members):
        if record["id"] == "val-positive" and set(members) == {A, B}:
            return None, False
        return actual(record, members)

    monkeypatch.setattr(engine, "_joint", limited_holdout)
    val = [case("val-positive", (A, B)), case("val-negative", (A,))]
    output = discover(training(), val)
    assert not output["summary"]["witness_proof_search_complete"]
    assert not output["summary"]["search_complete"]
    assert any(record["reason"] == "R2-holdout-witness-search-capped"
               for record in output["search"]["resource_affected_candidates"])


def test_review_protocol_uses_real_r1_inputs_and_freezes_holdout_thresholds():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).parents[1] / "scripts" / "run_r2_review_experiments.py"
    spec = importlib.util.spec_from_file_location("r2_review_experiments", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = module.run_review_experiments()
    assert output["A_adversarial_copies"]["canonical_duplicates"] == 29
    assert output["A_adversarial_copies"]["hypotheses"] == 0
    assert not output["C_new_signature_holdout"]["split"][
        "overlapping_positive_signatures"]
    assert output["C_new_signature_holdout"]["target"]["found"]
    assert output["C_new_signature_holdout"]["target"]["holdout"][
        "status"] == "passes-prespecified-symbolic-holdout-gate"
    assert output["D_controlled_factual_counterfactual"][
        "modified_has_joint_proof"] is False
    assert output["F_resource_bounds"]["witness_proof_search_complete"] is False
    assert output["E_permutation_control"]["seed"] == 20261108
    assert output["E_permutation_control"]["iterations"] == 1200
    assert output["research_conclusion"]["level_2_new_semantic_relation"] is False


def test_original_eight_recurring_patterns_keep_unverified_source_provenance():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).parents[1] / "scripts" / "run_r2_experiment.py"
    spec = importlib.util.spec_from_file_location("r2_original_audit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.run_experiment()
    observed = data["r2"]["recurring_but_not_diverse_patterns"]
    assert len(observed) == 8
    assert all(item["source_review_statuses"] == ["unverified"]
               for item in observed)
    assert all(item["metrics"]["supporting_report_count"] == 6
               for item in observed)
    assert all(item["metrics"]["distinct_evidence_signature_count"] == 1
               for item in observed)
    assert all(item["all_supporting_reports_unverified_or_missing"]
               for item in observed)
    assert all(item["support_cases"] and item["rule_ids"]
               for item in observed)
    core = data["target_cross_domain_pattern"]
    assert core["recurrent_without_diversity"] and not core["found"]
    assert core["recurrence_metrics"]["distinct_data_template_count"] == 1


def test_r2_hypothesis_id_tracks_r1_ontology_and_not_editorial_text(monkeypatch):
    import astrochart.discovery_r2 as engine
    data = training()
    first = by_members(engine.discover(data))[(A, B)]["id"]
    # Test an R1 ontology revision without writing to the production R1 module.
    changed_transitions = dict(engine.TRANSITIONS)
    changed_transitions[A] = ("גמישות",)
    monkeypatch.setattr(engine, "TRANSITIONS", changed_transitions)
    later = by_members(engine.discover(data))[(A, B)]["id"]
    assert first != later
    assert engine.discover(data)["ontology_identity"] != engine._digest({
        "functions": engine.FUNCTIONS,
        "transitions": {**changed_transitions, A: ("גמישות", "התמדה")},
        "domain_constraint": "same-domain-directed-no-repetition",
    })


def test_candidate_enumeration_cap_is_not_misreported_as_complete(monkeypatch):
    import astrochart.discovery_r2 as engine
    monkeypatch.setattr(engine, "MAX_CANDIDATES", 1)
    output = discover(training())
    assert not output["summary"]["candidate_enumeration_complete"]
    assert not output["summary"]["search_complete"]
    assert output["search"]["candidate_enumeration_unexamined_pending"] >= 1
