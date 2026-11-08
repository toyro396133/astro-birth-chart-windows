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
    assert val["status"] == "counterexamples-observed"
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
    result = discover(corpus)
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
