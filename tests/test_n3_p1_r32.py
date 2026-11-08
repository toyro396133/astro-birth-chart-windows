"""Independent repair regression for R32-01 through R32-07.

Synthetic, offline only. No positive licensed N3 source or user output.
"""
import copy
import json
from pathlib import Path
import pytest

from astrochart.domain import Chart, BodyPosition
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.synthesis import synthesize, SYNTHESIS_VERSION
from astrochart.n3_contracts import (
    N3ValidationError, digest, seal, claim_id, plan_id, evaluation_id,
    make_manifest, make_snapshot_id, verify_definition, verify_registry,
    verify_plan, verify_evidence_bindings, source_eligible, verify_claim,
    validate_predicate, evaluate_bound_predicate, source_conditions_state,
)
from astrochart.n3_evidence import adapt_hits, map_r1_witnesses, alternative_set_id
from astrochart.n3_n2 import verify_n2_catalog
from astrochart.n3_admission import admit_n3_bundle
from test_n3_p1 import (
    RULES, N2, PACK, term_registry, source_registry, definition, ontology,
    a_incomplete_b_proven,
)
from test_n3_p1_integrity import composite_evaluation, check

def _bundle():
    # Build from pinned main artifacts, then independently derive N3 fixtures.
    m = make_manifest(RULES, N2, ontology(),
                      r1_version=SYNTHESIS_VERSION, n2_version=N2["catalog_version"])
    t, s = term_registry(), source_registry()
    d = definition(m,t,s)
    catalog = seal({"kind":"RelationCatalog","schema_version":"N3-contract-2",
                    "catalog_version":"fixture-v1",
                    "compatible_upstream_hash":m["compatible_upstream_hash"],
                    "term_registry_hash":t["registry_hash"],
                    "source_registry_hash":s["registry_hash"],
                    "definitions":[d]}, "catalog_digest")
    snap = make_snapshot_id(m,catalog,"N3-P1-synthetic")
    ev, adapter = composite_evaluation()
    # Rebind the *same immutable original* witness facts to the new snapshot.
    ev["snapshot_id"] = snap
    ev["definition_hash"] = d["definition_hash"]
    for binding in ev["bindings"]:
        binding["alternative_set_id"] = alternative_set_id(
            snapshot_id=snap, route="original_composite",
            definition_id=d["definition_id"], role=binding["role"],
            witness_group_ids=[binding["witness_group_id"]])
    ev["selected_witnesses"] = copy.deepcopy(ev["bindings"])
    ev["route_proofs"][1]["alternative_set_ids"] = [
        x["alternative_set_id"] for x in ev["bindings"]]
    ev["evaluation_id"] = evaluation_id(ev)
    reasons = [
        {"code":"NO_RELATION_SOURCE","route":"original_composite",
         "blocking":True,"evidence_refs":[]}]
    plan={"kind":"N3Plan","schema_version":"N3-contract-2",
          "snapshot_id":snap,"definition_id":d["definition_id"],
          "evaluation_id":ev["evaluation_id"],"decision":"COMPARISON_ONLY",
          "primary_reason":"NO_RELATION_SOURCE","reasons":reasons,
          "retained_atomic_rule_ids":["moon-sign-2","sun-sign-1"],
          "comparison_state":"available","relation_claim_state":"blocked",
          "relation_claim_ids":[],"route_proofs":copy.deepcopy(ev["route_proofs"]),
          "trace":{"source_snapshot_hash":s["registry_hash"],
                   "adapter_trace_hash":adapter["trace_digest"],
                   "evaluation_trace_hash":ev["trace_digest"],
                   "selected_decisive_route":"original_composite",
                   "atomic_evidence_refs":ev["route_proofs"][1]["source_fact_refs"]}}
    plan["plan_id"]=plan_id(plan)
    chart=Chart([BodyPosition("שמש",15,False,(0,)),
                 BodyPosition("ירח",45,False,(1,))],[],None,None,False,[])
    return dict(manifest=m,relation_catalog=catalog,terms=t,sources=s,
                definition_id=d["definition_id"],snapshot_id=snap,
                execution_contract_version="N3-P1-synthetic",
                chart=chart,report=interpret_chart(chart,PACK),pack=PACK,
                raw_rulepack=RULES,n2_catalog=N2,evaluation=ev,plan=plan)


def test_r32_01_status_approved_with_self_pinned_hash_never_licenses():
    m=make_manifest(RULES,N2,ontology(),
                    r1_version=SYNTHESIS_VERSION,n2_version=N2["catalog_version"])
    t, s=term_registry(),source_registry()
    a=s["anchors"][0]
    a.update(review_status="approved",support_kind="explicit_attestation",
             reviewer_id="impostor",reviewed_at="2026-11-08T00:00:00Z",
             source_text_verification="primary_text_checked",
             visual_verification="verified")
    s["anchors"][0]=seal(a,"anchor_hash")
    s=seal(s,"registry_hash")
    verify_registry(s)
    d=definition(m,t,s)
    d["relation_review"].update(status="approved_for_symbolic_wording",
                                reviewer_id="impostor",
                                reviewed_at="2026-11-08T00:00:00Z")
    d=seal(d,"definition_hash")
    assert not source_eligible(d,s,trusted_source_registry_hash=s["registry_hash"])
    assert not source_eligible(d,s)


def test_r32_02_full_bundle_admission_accepts_unlicensed_comparison():
    bundle=_bundle()
    result=admit_n3_bundle(**bundle)
    assert result.status=="COMPARISON_ONLY"
    assert result.claim_ids==()
    assert result.source_condition_state=="TRUE"
    assert result.relation_predicate_state=="TRUE"


@pytest.mark.parametrize("mutator",[
    lambda b:b["evaluation"].pop("time_proof"),
    lambda b:b["evaluation"].update(trace_digest=digest("forged")),
    lambda b:b["evaluation"]["bindings"][0].update(rule_id="unknown-rule"),
    lambda b:b["evaluation"]["bindings"][0].update(source_refs=["https://fake.invalid"]),
    lambda b:b["plan"].update(relation_claim_ids=[digest("forged")]),
    lambda b:b["raw_rulepack"]["rules"][0].update(text="forged, same version"),
    lambda b:b["n2_catalog"]["rule_readings"][0].update(behavior="re-signed by attacker"),
])
def test_r32_02_forged_or_missing_chain_component_rejected(mutator):
    b=copy.deepcopy(_bundle())
    mutator(b)
    with pytest.raises(N3ValidationError):
        admit_n3_bundle(**b)


def test_r32_02_public_plan_cannot_skip_evaluation_chain():
    plan,ev,d,s,adapter=a_incomplete_b_proven()
    with pytest.raises(N3ValidationError,match="UNVERIFIED_EVALUATION"):
        verify_plan(plan,ev,d,s)
    bad=copy.deepcopy(ev)
    bad.pop("bindings")
    with pytest.raises(N3ValidationError):
        verify_plan(plan,bad,d,s,adapted=adapter,n2_catalog=N2)


@pytest.mark.parametrize("key",[
    "adapter_trace_hash","atomic_evidence_refs","source_snapshot_hash",
    "relation_claim_state","retained_atomic_rule_ids",
])
def test_r32_03_plan_full_content_integrity(key):
    b=_bundle()
    old=b["plan"]
    bad=copy.deepcopy(old)
    if key in ("adapter_trace_hash","atomic_evidence_refs","source_snapshot_hash"):
        bad["trace"][key]=[digest("invented")] if key=="atomic_evidence_refs" else digest("invented")
    elif key=="relation_claim_state":
        bad[key]="indeterminate"
    else:
        bad[key]=["invented-rule"]
    assert plan_id(bad)!=old["plan_id"]
    with pytest.raises(N3ValidationError):
        admit_n3_bundle(**{**b,"plan":bad})


@pytest.mark.parametrize("field",["evidence_refs","semantic_delta","limits",
                                  "attribution","audience","realization_plan"])
def test_r32_03_claim_full_content_integrity(field):
    b=_bundle()
    eff=b["relation_catalog"]["definitions"][0]["licensed_effects"][0]
    claim={"kind":"NarrativeClaim","schema_version":"N3-contract-2",
           "evaluation_id":b["evaluation"]["evaluation_id"],
           "licensed_effect_id":eff["effect_id"],"derived_predicate":eff,
           "evidence_refs":b["evaluation"]["route_proofs"][1]["selected_binding_ids"],
           "source_anchor_refs":eff["source_anchor_ids"],
           "semantic_delta":[eff],"novelty_proof":check("novelty","unknown"),
           "limits":["synthetic only"],"attribution":"unverified",
           "status":"shadow_only","audience":"shadow","realization_plan":[]}
    claim["claim_id"]=claim_id(claim)
    bad=copy.deepcopy(claim)
    if field in ("evidence_refs","limits","realization_plan"):
        bad[field]=["invented"]
    elif field=="semantic_delta":
        bad[field]=[]
    elif field=="audience":
        bad[field]="reviewer"
    else:
        bad[field]="tampered"
    assert claim_id(bad)!=claim["claim_id"]
    with pytest.raises(N3ValidationError):
        admit_n3_bundle(**{**b,"claims":(bad,)})


def _real_r1():
    chart=Chart([BodyPosition("שמש",12.4,False,(0,)),
                 BodyPosition("מרקורי",35,False,(1,)),
                 BodyPosition("שבתאי",286,False,(9,))],
                [],12,None,False,[])
    report=interpret_chart(chart,PACK)
    result=synthesize(chart,report)
    node=next(n for n in result["nodes"] if n.get("type")=="synthesis"
              and n["path"]==["יוזמה","התמדה","אחריות"])
    return node,adapt_hits(chart,report,PACK,RULES),chart,report


@pytest.mark.parametrize("field",[
    "source_refs","review_statuses","details","rule_ids",
    "roots","weight",
])
def test_r32_04_forged_r1_selected_metadata_rejected(field):
    node,adapter,chart,report=_real_r1()
    map_r1_witnesses(node,adapter,chart=chart,report=report)
    bad=copy.deepcopy(node)
    witness=bad["selected_witnesses_by_axis"]["יוזמה"]
    witness[field]=["forged"] if isinstance(witness[field],list) else 100
    with pytest.raises(N3ValidationError,match="PROVENANCE_MISMATCH"):
        map_r1_witnesses(bad,adapter,chart=chart,report=report)


def test_r32_04_forged_r1_alternative_rejected():
    node,adapter,chart,report=_real_r1()
    bad=copy.deepcopy(node)
    bad["alternative_facts_by_axis"]["יוזמה"].append({
        "evidence_key":"injected","rule_ids":["invented"],"roots":["body:invented"],
        "weight":5.0,"source_refs":[],"review_statuses":[],"details":[]})
    with pytest.raises(N3ValidationError):
        map_r1_witnesses(bad,adapter,chart=chart,report=report)
    with pytest.raises(N3ValidationError,match="UNVERIFIED_R1"):
        map_r1_witnesses(node,adapter)


@pytest.mark.parametrize("mutation",["wrong_role_rule","wrong_role_fact","nested_not"])
def test_r32_05_bad_semantic_binding_or_nested_negation(mutation):
    b=_bundle()
    d=copy.deepcopy(b["relation_catalog"]["definitions"][0])
    if mutation=="wrong_role_rule":
        d["predicate_ast"]["args"][0]["rule_id"]="moon-sign-2"
    elif mutation=="wrong_role_fact":
        d["predicate_ast"]["args"][1]["sign"]="שור"
    else:
        d["predicate_ast"]["args"].append({"op":"not","arg":{"op":"all","args":[
            {"op":"rule_hit_exact","role":"A","rule_id":"sun-sign-1"},
            {"op":"time_stable","role":"A"}]}})
    d=seal(d,"definition_hash")
    with pytest.raises(N3ValidationError):
        verify_definition(d,b["manifest"],b["terms"],b["sources"],
                          {r["id"] for r in RULES["rules"]},
                          raw_rulepack=RULES)


def test_r32_05_source_false_unknown_do_not_authorize():
    b=_bundle()
    d=copy.deepcopy(b["relation_catalog"]["definitions"][0])
    adapter=adapt_hits(b["chart"],b["report"],PACK,RULES)
    ev=b["evaluation"]
    d["source_anchors"][0]["matching_conditions"]={
        "op":"polarity_exact","role":"A","value":-1}
    assert source_conditions_state(d,ev,adapter)=="FALSE"
    d["source_anchors"][0]["matching_conditions"]={
        "op":"atom_term_equals","role":"A","field":"context",
        "term_id":"n3.context.test"}
    assert source_conditions_state(d,ev,adapter)=="UNKNOWN"
    assert evaluate_bound_predicate(d["predicate_ast"],d,ev,adapter,complete=True)=="TRUE"


@pytest.mark.parametrize("change",["when","source_detail","text","review_status"])
def test_r32_06_same_rulepack_version_different_content_rejected(change):
    chart=_bundle()["chart"]
    report=interpret_chart(chart,PACK)
    bad=copy.deepcopy(RULES)
    rule=next(r for r in bad["rules"] if r["id"]=="sun-sign-1")
    if change=="when":rule["when"]["sign"]="שור"
    elif change=="source_detail":rule["source_detail"]["title"]="FAKE"
    elif change=="text":rule["text"]="Forged interpretation text"
    else:rule["review_status"]="reviewed"
    assert bad["pack_version"]==RULES["pack_version"]
    with pytest.raises(N3ValidationError):
        adapt_hits(chart,report,PACK,bad)


def test_r32_06_overlap_policy_tracks_no_independence():
    chart=Chart([BodyPosition("שמש",15,False,(0,),house=1)],
                [],12,None,False,[])
    report=interpret_chart(chart,PACK)
    adapted=adapt_hits(chart,report,PACK,RULES)
    observed={h["rule_id"]:h for h in adapted["hits"]}
    assert {"sun-sign-1","sun-house-1"}.issubset(observed)
    t,s=term_registry(),source_registry()
    m=make_manifest(RULES,N2,ontology(),
                    r1_version=SYNTHESIS_VERSION,n2_version=N2["catalog_version"])
    d=definition(m,t,s)
    d["participant_specs"][1]["allowed_rule_ids"]=["sun-house-1"]
    bindings=[]
    snap=digest("overlap snapshot")
    for role,rid in (("A","sun-sign-1"),("B","sun-house-1")):
        h=observed[rid]
        bindings.append({"role":role,"rule_id":rid,
            "rule_hit_id":h["rule_hit_id"],"evidence_key":h["evidence_key"],
            "fact_keys":h["fact_keys"],"witness_group_id":h["witness_group_id"],
            "alternative_set_id":alternative_set_id(
                snapshot_id=snap,route="r1_path",definition_id=d["definition_id"],
                role=role,witness_group_ids=[h["witness_group_id"]]),
            "dependency_roots":h["dependency_roots"],"source_refs":h["source_refs"],
            "rule_review_status":h["review_status"],"meaning_ref":None,
            "content_category":"behavioral_rule_reading","origin":"r1_witness"})
    from test_n3_p1_integrity import composite_evaluation
    ev, _=composite_evaluation()
    ev["definition_id"]=d["definition_id"]
    ev["snapshot_id"]=snap
    ev["bindings"]=bindings
    ev["selected_witnesses"]=copy.deepcopy(bindings)
    ev["alternatives"]=[]
    ev["route_proofs"][0]={"route":"r1_path","candidate_state":"candidate",
        "search_state":"complete","search_complete":True,"visited":2,
        "cap":100,"proof_result":"proven",
        "selected_binding_ids":[b["rule_hit_id"] for b in bindings],
        "alternative_set_ids":[b["alternative_set_id"] for b in bindings],
        "source_fact_refs":sorted({f for b in bindings for f in b["fact_keys"]}),
        "failure_reasons":[],"trace_hash":digest("real overlap")}
    ev["route_proofs"][1]={"route":"original_composite","candidate_state":"not_candidate",
        "search_state":"not_applicable","search_complete":None,
        "visited":0,"cap":100,"proof_result":"not_candidate",
        "selected_binding_ids":[],"alternative_set_ids":[],
        "source_fact_refs":[],"failure_reasons":[],"trace_hash":digest("no B")}
    from astrochart.n3_contracts import verify_evidence_bindings
    d["evidence_policy"]["independent_roots_required"]=True
    with pytest.raises(N3ValidationError,match="DEPENDENT_ROOTS"):
        verify_evidence_bindings(ev,adapted,definition=d,n2_catalog=N2)
    d["evidence_policy"]["independent_roots_required"]=False
    verify_evidence_bindings(ev,adapted,definition=d,n2_catalog=N2)
    roots=[set(b["dependency_roots"]) for b in bindings]
    assert roots[0] & roots[1]   # Shared Sun; never two independent observations.


def test_r32_07_missing_category_and_re_signed_catalog_rejected():
    bad=copy.deepcopy(N2)
    del bad["withheld_editorial_readings"]
    with pytest.raises(N3ValidationError,match="mandatory"):
        verify_n2_catalog(bad,RULES)
    changed=copy.deepcopy(N2)
    changed["rule_reading_policy"]+=" modified"
    with pytest.raises(N3ValidationError):
        verify_n2_catalog(changed,RULES,locked_digest=digest(N2))
    b=_bundle()
    b["n2_catalog"]=changed
    b["manifest"]["n2_catalog_digest"]=digest(changed)
    with pytest.raises(N3ValidationError):
        admit_n3_bundle(**b)


def test_r32_07_cli_rejects_caller_claimed_git_head():
    from scripts.n3_p1_admit_locked_pr29 import verified_committed_catalog
    with pytest.raises(N3ValidationError,match="UNTRUSTED_N2_HEAD"):
        verified_committed_catalog(b"{}", "f"*40)
