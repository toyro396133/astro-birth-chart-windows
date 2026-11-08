"""R32-08/09/10 independent, re-sealed adversarial admission tests.

Only original RulePack, actual interpretation and a genuinely replayable
bounded R1 proof are inputs. The search budget is reduced *within the test*
without editing or mocking the R1 result or the production algorithm.
"""
from __future__ import annotations

import copy
import pytest

from astrochart.domain import Chart, BodyPosition
from astrochart.interpretation import interpret_chart
from astrochart.n3_admission import admit_n3_bundle, limited_r1_trace
from astrochart.n3_contracts import (
    N3ValidationError, digest, seal, evaluation_id, plan_id, make_snapshot_id,
)
from astrochart.n3_evidence import adapt_hits, match_composite, alternative_set_id
from astrochart import synthesis
from test_n3_p1 import PACK, RULES, N2
from test_n3_p1_r32 import _bundle


def resign(bundle):
    """Simulate an adversary who knows all non-keyed SHA-256 derivations."""
    e, p = bundle["evaluation"], bundle["plan"]
    e["evaluation_id"] = evaluation_id(e)
    p["evaluation_id"] = e["evaluation_id"]
    p["route_proofs"] = copy.deepcopy(e["route_proofs"])
    p["plan_id"] = plan_id(p)


@pytest.mark.parametrize("code,route", [
    ("MATERIAL_TENSION", "original_composite"),
    ("UNCERTAIN_TIME", "original_composite"),
    ("DEPENDENT_ROOTS", "original_composite"),
    ("INCOMPLETE_SEARCH", "r1_path"),
])
def test_r32_08_forged_reason_and_primary_and_plan_id_are_rejected(code, route):
    b = _bundle()
    # Structurally well-formed and *freshly signed*, but false in original facts.
    p = b["plan"]
    p["reasons"] = [{
        "code": code, "route": route,
        "blocking": route == "original_composite", "evidence_refs": [],
    }]
    p["primary_reason"] = code if route == "original_composite" else "NONE"
    p["plan_id"] = plan_id(p)
    with pytest.raises(N3ValidationError, match="REASON_MISMATCH"):
        admit_n3_bundle(**b)


def test_r32_08_resealed_missing_source_reason_is_rejected():
    b = _bundle()
    p = b["plan"]
    # Under-review relation *is* real, but the actual unlicensed source check
    # cannot be hidden by substituting this weaker reason.
    p["reasons"] = [{"code": "UNVERIFIED_RELATION", "route": "original_composite",
                     "blocking": True, "evidence_refs": []}]
    p["primary_reason"] = "UNVERIFIED_RELATION"
    p["plan_id"] = plan_id(p)
    with pytest.raises(N3ValidationError, match="REASON_MISMATCH"):
        admit_n3_bundle(**b)


def test_r32_08_source_check_cannot_claim_pass_and_resign():
    b = _bundle()
    b["evaluation"]["source_license_check"]["status"] = "pass"
    resign(b)
    with pytest.raises(N3ValidationError, match="NOT_LICENSED|REASON_MISMATCH"):
        admit_n3_bundle(**b)


def _chart_with_both_routes() -> Chart:
    return Chart([
        BodyPosition("שמש", 15, False, (0,)),
        BodyPosition("ירח", 45, False, (1,)),
        BodyPosition("מרקורי", 45, False, (1,)),
        BodyPosition("שבתאי", 285, False, (9,)),
    ], [], None, None, False, [])


def _with_extra_authentic_hits() -> dict:
    b = _bundle()
    chart = _chart_with_both_routes()
    report = interpret_chart(chart, PACK)
    adapted = adapt_hits(chart, report, PACK, RULES)
    direct = match_composite("sun-aries-moon-taurus", adapted, RULES)
    by_rule = {hit["rule_id"]: hit for hit in adapted["hits"]}
    assert {"sun-sign-1", "moon-sign-2", "mercury-sign-2"} <= by_rule.keys()
    ev = b["evaluation"]
    for binding in ev["bindings"]:
        hit = by_rule[binding["rule_id"]]
        binding.update(rule_hit_id=hit["rule_hit_id"],
                       evidence_key=hit["evidence_key"],
                       fact_keys=hit["fact_keys"],
                       dependency_roots=hit["dependency_roots"],
                       witness_group_id=hit["witness_group_id"],
                       source_refs=hit["source_refs"],
                       rule_review_status=hit["review_status"])
        binding["alternative_set_id"] = alternative_set_id(
            snapshot_id=ev["snapshot_id"], route="original_composite",
            definition_id=ev["definition_id"], role=binding["role"],
            witness_group_ids=[hit["witness_group_id"]])
    ev["bindings"].sort(key=lambda x: (x["role"], x["rule_hit_id"]))
    ev["selected_witnesses"] = copy.deepcopy(ev["bindings"])
    ev["matched_rule_hits"] = [x["rule_hit_id"] for x in ev["bindings"]]
    ev["original_composite_match"] = direct
    proof = ev["route_proofs"][1]
    proof["selected_binding_ids"] = [x["rule_hit_id"] for x in ev["bindings"]]
    proof["alternative_set_ids"] = [x["alternative_set_id"] for x in ev["bindings"]]
    proof["source_fact_refs"] = sorted({f for x in ev["bindings"] for f in x["fact_keys"]})
    ev["chart_fingerprint"] = adapted["chart_fingerprint"]
    ev["trace_digest"] = digest(adapted)
    b["chart"] = chart
    b["report"] = report
    b["plan"]["trace"]["adapter_trace_hash"] = adapted["trace_digest"]
    b["plan"]["trace"]["evaluation_trace_hash"] = ev["trace_digest"]
    b["plan"]["trace"]["atomic_evidence_refs"] = proof["source_fact_refs"]
    resign(b)
    return b


def _add_real_nondecisive_witness(b: dict):
    """Append a real hit as a permitted alternate binding, without selecting it."""
    adapted = adapt_hits(b["chart"], b["report"], PACK, RULES)
    hit = next(h for h in adapted["hits"] if h["rule_id"] == "mercury-sign-2")
    definition = b["relation_catalog"]["definitions"][0]
    spec = definition["participant_specs"][0]
    spec["allowed_rule_ids"].append("mercury-sign-2")
    definition = seal(definition, "definition_hash")
    b["relation_catalog"]["definitions"][0] = definition
    b["relation_catalog"] = seal(b["relation_catalog"], "catalog_digest")
    snap = make_snapshot_id(b["manifest"], b["relation_catalog"],
                            b["execution_contract_version"])
    b["snapshot_id"] = snap
    e = b["evaluation"]
    e["definition_hash"] = definition["definition_hash"]
    e["snapshot_id"] = snap
    current = e["bindings"][0]
    alt_id = alternative_set_id(
        snapshot_id=snap, route="original_composite",
        definition_id=e["definition_id"], role="A",
        witness_group_ids=sorted([current["witness_group_id"], hit["witness_group_id"]]))
    current["alternative_set_id"] = alt_id
    for other in e["bindings"][1:]:
        other["alternative_set_id"] = alternative_set_id(
            snapshot_id=snap, route="original_composite",
            definition_id=e["definition_id"], role=other["role"],
            witness_group_ids=[other["witness_group_id"]])
    extra = {
        "role": "A", "rule_id": hit["rule_id"],
        "rule_hit_id": hit["rule_hit_id"], "evidence_key": hit["evidence_key"],
        "fact_keys": hit["fact_keys"], "dependency_roots": hit["dependency_roots"],
        "witness_group_id": hit["witness_group_id"],
        "alternative_set_id": alt_id,
        "source_refs": hit["source_refs"], "rule_review_status": hit["review_status"],
        "meaning_ref": None, "content_category": "behavioral_rule_reading",
        "origin": "direct_composite_component",
    }
    e["bindings"].append(extra)
    e["bindings"].sort(key=lambda x: (x["role"], x["rule_hit_id"]))
    e["matched_rule_hits"] = [x["rule_hit_id"] for x in e["bindings"]]
    proof = e["route_proofs"][1]
    proof["alternative_set_ids"] = [x["alternative_set_id"] for x in
                                    e["bindings"] if x["rule_id"] != hit["rule_id"]]
    b["plan"]["snapshot_id"] = snap
    b["plan"]["retained_atomic_rule_ids"] = ["mercury-sign-2","moon-sign-2","sun-sign-1"]
    return extra


@pytest.mark.parametrize("tamper", ["extra_selected", "replace_selected", "foreign_route"])
def test_r32_10_real_nondecisive_witness_cannot_supply_truth(tamper):
    b = _with_extra_authentic_hits()
    extra = _add_real_nondecisive_witness(b)
    e = b["evaluation"]
    by_rule = {x["rule_id"]: x for x in e["bindings"]}
    if tamper == "extra_selected":
        e["selected_witnesses"] = copy.deepcopy(
            [by_rule["sun-sign-1"], by_rule["mercury-sign-2"], by_rule["moon-sign-2"]])
    elif tamper == "replace_selected":
        e["selected_witnesses"] = copy.deepcopy(
            [by_rule["mercury-sign-2"], by_rule["moon-sign-2"]])
    else:
        other = copy.deepcopy(extra)
        other["origin"] = "r1_witness"
        e["selected_witnesses"] = [by_rule["sun-sign-1"], by_rule["moon-sign-2"], other]
    resign(b)
    with pytest.raises(N3ValidationError, match="PROVENANCE_MISMATCH|duplicate evidence binding"):
        admit_n3_bundle(**b)


def _forced_genuine_r1_cap(monkeypatch):
    """Let R1 build true base facts under its normal budget, then cap only path
    proof search. The same original calculation is replayed by admission.
    """
    original_base = synthesis._base_features
    original_cap = synthesis.MAX_PROOF_STATES
    def full_base_then_bounded_paths(report):
        monkeypatch.setattr(synthesis, "MAX_PROOF_STATES", original_cap)
        result = original_base(report)
        monkeypatch.setattr(synthesis, "MAX_PROOF_STATES", 1)
        return result
    monkeypatch.setattr(synthesis, "_base_features", full_base_then_bounded_paths)


def _valid_capped_r1_bundle(monkeypatch):
    _forced_genuine_r1_cap(monkeypatch)
    b = _with_extra_authentic_hits()
    d = b["relation_catalog"]["definitions"][0]
    d["participant_specs"][0]["allowed_rule_ids"].append("mercury-sign-2")
    d = seal(d, "definition_hash")
    b["relation_catalog"]["definitions"][0] = d
    b["relation_catalog"] = seal(b["relation_catalog"], "catalog_digest")
    snap = make_snapshot_id(b["manifest"], b["relation_catalog"],
                            b["execution_contract_version"])
    b["snapshot_id"] = snap
    ev = b["evaluation"]
    ev["snapshot_id"] = snap
    ev["definition_hash"] = d["definition_hash"]
    for binding in ev["bindings"]:
        binding["alternative_set_id"] = alternative_set_id(
            snapshot_id=snap, route="original_composite",
            definition_id=ev["definition_id"], role=binding["role"],
            witness_group_ids=[binding["witness_group_id"]])
    ev["selected_witnesses"] = copy.deepcopy(ev["bindings"])
    ev["route_proofs"][1]["alternative_set_ids"] = [
        binding["alternative_set_id"] for binding in ev["bindings"]]
    r1 = synthesis.synthesize(b["chart"], b["report"])
    path = ("יציבות", "התמדה")
    assert list(path) in r1["summary"]["proof_search_limited_paths"]
    assert not any(n["type"]=="synthesis" and n["path"]==list(path)
                   for n in r1["nodes"])
    base, _ = synthesis._base_features(b["report"])
    chosen, alternatives, limited, states = synthesis._choose_path_proof(
        path, {x["axis"]:x for x in base})
    assert chosen is None and limited
    cap = synthesis.MAX_PROOF_STATES
    proofA = ev["route_proofs"][0]
    proofA.update(candidate_state="candidate",search_state="incomplete",
                  search_complete=False,visited=states,cap=cap,
                  proof_result="unknown",selected_binding_ids=[],
                  alternative_set_ids=[],source_fact_refs=[],
                  failure_reasons=["INCOMPLETE_SEARCH"],
                  trace_hash=limited_r1_trace(
                      adapt_hits(b["chart"],b["report"],PACK,RULES),path,states,cap))
    ev["discovery_routes"] = ["r1_path", "original_composite"]
    p=b["plan"]
    p["reasons"]=[
        {"code":"INCOMPLETE_SEARCH","route":"r1_path",
         "blocking":False,"evidence_refs":[]},
        {"code":"NO_RELATION_SOURCE","route":"original_composite",
         "blocking":True,"evidence_refs":[]},
    ]
    p["snapshot_id"] = snap
    p["trace"]["selected_decisive_route"] = "original_composite"
    b["r1_limited_path"]=path
    resign(b)
    return b


def test_r32_09_real_r1_capped_no_node_does_not_block_verified_composite(monkeypatch):
    b=_valid_capped_r1_bundle(monkeypatch)
    result=admit_n3_bundle(**b)
    assert result.status=="COMPARISON_ONLY"
    assert result.source_condition_state=="TRUE"
    assert result.relation_predicate_state=="TRUE"
    assert result.claim_ids==()
    assert b["plan"]["reasons"][0]["blocking"] is False


@pytest.mark.parametrize("tamper", ["fake_limited_path","fake_r1_states",
                                  "fake_not_candidate","fake_blocking"])
def test_r32_09_resigned_forged_cap_metadata_rejected(monkeypatch,tamper):
    b=_valid_capped_r1_bundle(monkeypatch)
    if tamper=="fake_limited_path":
        b["r1_limited_path"]=("התמדה", "הרמוניה")
    elif tamper=="fake_r1_states":
        b["evaluation"]["route_proofs"][0]["visited"]+=1
    elif tamper=="fake_not_candidate":
        a=b["evaluation"]["route_proofs"][0]
        a.update(candidate_state="not_candidate",search_state="not_applicable",
                 search_complete=None,visited=0,proof_result="not_candidate",
                 failure_reasons=[],trace_hash=digest("fake exhausted"))
        b.pop("r1_limited_path")
        b["plan"]["reasons"].pop(0)
    elif tamper=="fake_blocking":
        b["plan"]["reasons"][0]["blocking"]=True
        b["plan"]["primary_reason"]="INCOMPLETE_SEARCH"
    resign(b)
    with pytest.raises(N3ValidationError):
        admit_n3_bundle(**b)
