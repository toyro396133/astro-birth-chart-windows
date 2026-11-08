"""Integration identity/provenance negative tests for P1 (no N3 UI wiring)."""
import copy
import json
from pathlib import Path
import pytest
from astrochart.domain import Chart, BodyPosition
from astrochart.interpretation import load_rulepack, interpret_chart
from astrochart.synthesis import synthesize
from astrochart.n3_contracts import (
    N3ValidationError, digest, verify_hash_dag, verify_evaluation,
    evaluation_id, verify_evidence_bindings, validate_schema)
from astrochart.n3_evidence import (
    adapt_hits, match_composite, alternative_set_id, map_r1_witnesses)
from astrochart.n3_n2 import classify_rule

DATA=Path(__file__).resolve().parents[1]/"src"/"astrochart"
RULES=json.loads((DATA/"interpretation_rules.json").read_text(encoding="utf-8"))
N2=json.loads((DATA/"meaning_catalog_n2.json").read_text(encoding="utf-8"))
PACK=load_rulepack()

def check(name,status):
    return {"name":name,"status":status,"reason":"synthetic test only","evidence_refs":[]}

def composite_evaluation():
    chart=Chart([BodyPosition("שמש",15,False,(0,)),
                 BodyPosition("ירח",45,False,(1,))],[],None,None,False,[])
    raw=interpret_chart(chart,PACK)
    adapter=adapt_hits(chart,raw,PACK,RULES)
    comp=match_composite("sun-aries-moon-taurus",adapter,RULES)
    matching=[h for h in adapter["hits"] if h["rule_hit_id"] in comp["component_rule_hit_ids"]]
    matching.sort(key=lambda x: (0 if x["rule_id"]=="sun-sign-1" else 1))
    bindings=[]
    snapshot=digest("synthetic snapshot")
    for role,h in zip(("A","B"),matching):
        bindings.append({
            "role":role,"rule_id":h["rule_id"],"rule_hit_id":h["rule_hit_id"],
            "evidence_key":h["evidence_key"],"fact_keys":h["fact_keys"],
            "witness_group_id":h["witness_group_id"],
            "alternative_set_id":alternative_set_id(
                snapshot_id=snapshot,route="original_composite",
                definition_id="fixture-relation",role=role,
                witness_group_ids=[h["witness_group_id"]]),
            "dependency_roots":h["dependency_roots"],"source_refs":h["source_refs"],
            "rule_review_status":h["review_status"],"meaning_ref":None,
            "content_category":classify_rule(h["rule_id"],N2),
            "origin":"direct_composite_component",
        })
    selected=[b["rule_hit_id"] for b in bindings]
    proofA={
        "route":"r1_path","candidate_state":"not_candidate",
        "search_state":"not_applicable","search_complete":None,
        "visited":0,"cap":100,"proof_result":"not_candidate",
        "selected_binding_ids":[],"alternative_set_ids":[],
        "source_fact_refs":[],"failure_reasons":[],"trace_hash":digest("A")}
    proofB={
        "route":"original_composite","candidate_state":"candidate",
        "search_state":"complete","search_complete":True,
        "visited":2,"cap":100,"proof_result":"proven",
        "selected_binding_ids":selected,
        "alternative_set_ids":[b["alternative_set_id"] for b in bindings],
        "source_fact_refs":sorted({fact for h in matching for fact in h["fact_keys"]}),
        "failure_reasons":[],"trace_hash":digest("B")}
    ev={"kind":"RelationEvaluation","schema_version":"N3-contract-2",
        "definition_id":"fixture-relation","definition_hash":digest("definition"),
        "snapshot_id":snapshot,"chart_fingerprint":adapter["chart_fingerprint"],
        "run_id":"synthetic-run","candidate_id":digest("candidate"),
        "discovery_routes":["original_composite"],
        "matched_rule_hits":selected,"bindings":bindings,"alternatives":[],
        "selected_witnesses":bindings,"original_composite_match":comp,
        "dependency_proof":check("dependency","pass"),"time_proof":check("time","pass"),
        "conflict_proof":check("conflict","pass"),
        "route_proofs":[proofA,proofB],"source_license_check":check("source","fail"),
        "novelty_check":check("novelty","unknown"),"checks":[check("safety","pass")],
        "trace_digest":digest(adapter)}
    ev["evaluation_id"]=evaluation_id(ev)
    return ev,adapter

def test_signature_dag_rejects_snapshot_back_edge():
    order=verify_hash_dag()
    assert order.index("compatible_upstream_hash")<order.index("snapshot_id")
    assert order.index("definition_hash")<order.index("catalog_digest")
    with pytest.raises(N3ValidationError,match="CYCLIC_SIGNATURE_GRAPH"):
        verify_hash_dag({"compatible_upstream_hash":("snapshot_id",)})
    with pytest.raises(N3ValidationError):
        verify_hash_dag({"definition_hash":("untrusted_signature",)})

def test_evaluation_immutable_ids_and_direct_route_integrity():
    ev,adapter=composite_evaluation()
    validate_schema("RelationEvaluation",ev)
    verify_evaluation(ev,{"definition_id":ev["definition_id"],
                          "definition_hash":ev["definition_hash"]},
                      ev["snapshot_id"],adapter_trace=adapter)
    verify_evidence_bindings(ev,adapter,n2_catalog=N2)
    assert len(ev["bindings"])==len(ev["original_composite_match"]["component_fact_keys"])==2

def test_invented_evidence_root_and_wrong_alternative_are_rejected():
    ev,adapter=composite_evaluation()
    for mutate in (
        lambda e:e["bindings"][0].update(fact_keys=["placement:invented:extra"]),
        lambda e:e["bindings"][0].update(dependency_roots=["body:forged"]),
        lambda e:e["bindings"][0].update(alternative_set_id=digest("forged")),
        lambda e:e["route_proofs"][1].update(source_fact_refs=["placement:invented"]),
        lambda e:e["route_proofs"][1].update(selected_binding_ids=[digest("invented")]),
    ):
        bad=copy.deepcopy(ev);mutate(bad)
        with pytest.raises(N3ValidationError):verify_evidence_bindings(bad,adapter,n2_catalog=N2)

def test_forged_evaluation_hash_and_trace_rejected():
    ev,adapter=composite_evaluation()
    for field in ("evaluation_id","trace_digest"):
        bad=copy.deepcopy(ev)
        bad[field]=digest("tampered")
        with pytest.raises(N3ValidationError):
            verify_evaluation(bad,{"definition_id":ev["definition_id"],
                 "definition_hash":ev["definition_hash"]},
                 ev["snapshot_id"],adapter_trace=adapter)
    with pytest.raises(N3ValidationError):
        verify_evaluation(ev,{"definition_id":ev["definition_id"],
            "definition_hash":ev["definition_hash"]},ev["snapshot_id"])

def test_actual_r1_selected_witnesses_map_exactly_to_original_hits():
    chart=Chart([
        BodyPosition("שמש",12.4,False,(0,),house=None),
        BodyPosition("מרקורי",35,False,(1,),house=None),
        BodyPosition("שבתאי",286,False,(9,),house=None),
    ],[],12,None,False,[])
    report=interpret_chart(chart,PACK)
    r1=synthesize(chart,report)
    node=next(n for n in r1["nodes"] if n["type"]=="synthesis"
              and n["path"]==["יוזמה","התמדה","אחריות"])
    adapter=adapt_hits(chart,report,PACK,RULES)
    mapped=map_r1_witnesses(node,adapter,chart=chart,report=report)
    assert mapped["search_complete"] is True
    assert set(mapped["selected"])==set(node["selected_witnesses_by_axis"])
    forged=copy.deepcopy(node)
    forged["selected_witnesses_by_axis"]["יוזמה"]["roots"]=["body:invented"]
    with pytest.raises(N3ValidationError):
        map_r1_witnesses(forged,adapter,chart=chart,report=report)
