"""Fail-closed N3 P1 acceptance tests; synthetic fixtures are not licensed claims."""
import copy
import json
from pathlib import Path
import pytest
from astrochart.domain import Chart, BodyPosition, SIGNS
from astrochart.interpretation import interpret_chart, load_rulepack
from astrochart.n3_contracts import (
    N3ValidationError, canonical_bytes, digest, seal, validate_schema,
    make_manifest, verify_manifest, verify_registry, verify_definition, verify_catalog,
    make_snapshot_id, verify_snapshot, validate_predicate, evaluate_predicate,
    plan_id, evaluation_id, verify_plan, verify_route_proofs, ENABLED)
from astrochart.n3_evidence import adapt_hits, match_composite, alternative_set_id
from astrochart.n3_n2 import verify_n2_catalog, classify_rule

ROOT = Path(__file__).resolve().parents[1] / "src" / "astrochart"
RULES = json.loads((ROOT / "interpretation_rules.json").read_text(encoding="utf-8"))
N2 = json.loads((ROOT / "meaning_catalog_n2.json").read_text(encoding="utf-8"))
PACK = load_rulepack()
COMPOSITES = [r for r in RULES["rules"] if r["type"] == "composite"]

def ontology():
    from astrochart.synthesis import FUNCTIONS, TRANSITIONS, SYNTHESIS_VERSION
    return {"functions": FUNCTIONS, "transitions": TRANSITIONS, "version": SYNTHESIS_VERSION}

def manifest():
    return make_manifest(RULES, N2, ontology(), r1_version="0.1.0", n2_version="0.2.0")

def term_registry():
    entries = [{"term_id": "n3." + k + ".test", "term_kind": k,
                "canonical_definition": "synthetic fixture", "synonym_ids": [],
                "equivalence_cluster_id": None, "review_status": "approved",
                "reviewer_id": "fixture-only", "reviewed_at": "2026-11-08T00:00:00Z",
                "revision": 1} for k in ("boundary", "context", "focus", "scope")]
    return seal({"kind":"TermRegistry","schema_version":"N3-contract-2",
                 "registry_version":"fixture","entries":entries},"registry_hash")

def source_registry():
    anchor = seal({"anchor_id":"fixture-anchor","source_id":"fixture",
        "source_origin":"external_primary","source_version":"fixture","title":"Unverified synthetic",
        "edition":"fixture","url":None,"location":{"chapter":None,"printed_page":None,
        "section":None,"line_start":None,"line_end":None,"scan_page_index":None},
        "language":"he","accessed_at":"2026-11-08T00:00:00Z",
        "excerpt":"test only","scope_id":"n3.scope.test",
        "matching_conditions":{"op":"time_stable","role":"A"},
        "support_kind":"explicit_attestation_candidate","review_status":"under_review",
        "source_text_verification":"not_checked","visual_verification":"pending",
        "reviewer_id":None,"reviewed_at":None,"review_revision":0,
        "supported_effect_ids":["effect-fixture"]}, "anchor_hash")
    return seal({"kind":"SourceReviewRegistry","schema_version":"N3-contract-2",
                 "registry_version":"fixture","anchors":[anchor]},"registry_hash")

def definition(m,t,s):
    roles = [("A","sun-sign-1","שמש","טלה"),("B","moon-sign-2","ירח","שור")]
    ast = [{"op":op,"role":role,**extra}
           for role,rid,body,sign in roles
           for op,extra in [("rule_hit_exact",{"rule_id":rid}),
                            ("placement_exact",{"body":body,"sign":sign})]]
    participants = [{"role":role,"allowed_rule_ids":[rid],
                    "reading_policy":"original_atomic_allowed",
                    "atom_constraints":{"op":"time_stable","role":role}}
                    for role,rid,_,_ in roles]
    effect = {"effect_id":"effect-fixture","predicate":"symbolic_complement",
              "subject_role":"A","object_role":"B","context_id":"n3.context.test",
              "scope_id":"n3.scope.test","boundary_ids":["n3.boundary.test"],
              "source_anchor_ids":["fixture-anchor"],
              "modal_strength":"source_attributed_symbolic_possible"}
    return seal({"kind":"RelationDefinition","schema_version":"N3-contract-2",
        "definition_id":"fixture-relation","definition_revision":1,
        "compatible_upstream_hash":m["compatible_upstream_hash"],
        "term_registry_hash":t["registry_hash"],"operator":"complements",
        "direction":"A_to_B","participant_specs":participants,
        "predicate_ast":{"op":"all","args":ast},
        "evidence_policy":{"independent_roots_required":True,
            "time_policy":"stable_placements_allowed",
            "conflict_policy":"fail_on_material_conflict","proof_complete_required":True},
        "licensed_effects":[effect],"prohibited_effects":[],
        "source_anchors":s["anchors"],"provenance":"experimental",
        "relation_review":{"status":"under_review","reviewer_id":None,
                           "reviewed_at":None,"review_revision":0}}, "definition_hash")

def chart_for(rule,mode="known",unstable=False):
    bodies=[]
    for i,c in enumerate(rule["when"]["all"]):
        j=SIGNS.index(c["sign"])
        poss = (j, (j+1)%12) if unstable and i==0 else (j,) if mode=="unknown" else ()
        bodies.append(BodyPosition(c["body"],j*30+15,False,signs_possible=poss))
    return Chart(bodies,[],None,None,mode=="unknown",[],time_certainty=mode)

def route(name,ok):
    return {"route":name,"candidate_state":"candidate",
        "search_state":"complete" if ok else "incomplete",
        "search_complete":ok,"visited":2,"cap":2,
        "proof_result":"proven" if ok else "unknown",
        "selected_binding_ids":[digest("a"),digest("b")] if ok else [],
        "alternative_set_ids":[],"source_fact_refs":["placement:שמש:טלה","placement:ירח:שור"] if ok else [],
        "failure_reasons":[] if ok else ["INCOMPLETE_SEARCH"],
        "trace_hash":digest(name)}

def a_incomplete_b_proven():
    # Build a genuinely complete schema-compliant Evaluation from original facts.
    from test_n3_p1_integrity import composite_evaluation
    m,t,s=manifest(),term_registry(),source_registry()
    d=definition(m,t,s)
    ev,adapter=composite_evaluation()
    ev["definition_hash"]=d["definition_hash"]
    ev["route_proofs"][0]=route("r1_path",False)
    ev["evaluation_id"]=evaluation_id(ev)
    plan={"kind":"N3Plan","schema_version":"N3-contract-2",
        "snapshot_id":ev["snapshot_id"],"definition_id":d["definition_id"],
        "evaluation_id":ev["evaluation_id"],"decision":"COMPARISON_ONLY",
        "primary_reason":"NO_RELATION_SOURCE","reasons":[
            {"code":"INCOMPLETE_SEARCH","route":"r1_path","blocking":False,"evidence_refs":[]},
            {"code":"NO_RELATION_SOURCE","route":"original_composite","blocking":True,"evidence_refs":[]}],
        "retained_atomic_rule_ids":["moon-sign-2","sun-sign-1"],
        "comparison_state":"available","relation_claim_state":"blocked","relation_claim_ids":[],
        "route_proofs":ev["route_proofs"],"trace":{"source_snapshot_hash":s["registry_hash"],
        "adapter_trace_hash":adapter["trace_digest"],"evaluation_trace_hash":ev["trace_digest"],
        "selected_decisive_route":"original_composite",
        "atomic_evidence_refs":ev["route_proofs"][1]["source_fact_refs"]}}
    plan["plan_id"]=plan_id(plan)
    return plan,ev,d,s,adapter

def test_schema_rejects_missing_extra_and_bad_hash():
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema(json.loads(
        (ROOT/"n3_contracts.schema.json").read_text(encoding="utf-8")))
    m=manifest()
    validate_schema("UpstreamManifest",m)
    for bad in ({**m,"compatible_snapshot":digest("s")},
                {**m,"rulepack_digest":"a"*63},
                {k:v for k,v in m.items() if k!="ontology_digest"}):
        with pytest.raises(N3ValidationError): validate_schema("UpstreamManifest",bad)
    assert ENABLED is False

def test_unicode_canonicalization_and_fake_hash():
    assert canonical_bytes({"x":"e\u0301"})==canonical_bytes({"x":"é"})
    assert digest({"z":1,"a":2})==digest({"a":2,"z":1})
    m=manifest()
    with pytest.raises(N3ValidationError):
        verify_manifest({**m,"compatible_upstream_hash":"f"*64},
                        rulepack=RULES,n2_catalog=N2,ontology=ontology())

@pytest.mark.parametrize("change",["rule","version","policy","reading","ontology"])
def test_upstream_mutation_invalidates_snapshot(change):
    rules,n2,ont=copy.deepcopy(RULES),copy.deepcopy(N2),ontology()
    if change=="rule": rules["rules"][0]["text"]="tampered"
    if change=="version": n2["catalog_version"]="9.0.0"
    if change=="policy": n2["rule_reading_policy"]="tampered"
    if change=="reading": n2["rule_readings"][0]["behavior"]="tampered"
    if change=="ontology": ont["version"]="9.0.0"
    with pytest.raises(N3ValidationError,match="SNAPSHOT_MISMATCH"):
        verify_manifest(manifest(),rulepack=rules,n2_catalog=n2,ontology=ont)

def test_registry_definition_catalog_dag_and_invalidation():
    m,t,s=manifest(),term_registry(),source_registry()
    verify_registry(t);verify_registry(s)
    d=definition(m,t,s)
    ids={r["id"] for r in RULES["rules"]}
    verify_definition(d,m,t,s,ids)
    cat=seal({"kind":"RelationCatalog","schema_version":"N3-contract-2",
        "catalog_version":"fixture","compatible_upstream_hash":m["compatible_upstream_hash"],
        "term_registry_hash":t["registry_hash"],"source_registry_hash":s["registry_hash"],
        "definitions":[d]},"catalog_digest")
    verify_catalog(cat,m,t,s,ids)
    snap=make_snapshot_id(m,cat,"P1-execution")
    verify_snapshot(snap,m,cat,"P1-execution")
    for bad in ({**d,"snapshot_id":snap},{**d,"definition_hash":"f"*64}):
        with pytest.raises(N3ValidationError):
            verify_definition(bad,m,t,s,ids)
    bad=copy.deepcopy(s);bad["anchors"][0]["review_status"]="approved"
    with pytest.raises(N3ValidationError):verify_registry(bad)
    with pytest.raises(N3ValidationError):verify_snapshot("a"*64,m,cat,"P1-execution")

def test_ast_required_roles_and_operator_effect_mismatch():
    m,t,s=manifest(),term_registry(),source_registry()
    d=definition(m,t,s)
    ids={r["id"] for r in RULES["rules"]}
    validate_predicate(d["predicate_ast"],{"A","B"},ids,t,require_coverage=True)
    bads=[{"op":"any","args":[{"op":"time_stable","role":"A"}]},
          {"op":"not","arg":{"op":"rule_hit_exact","role":"A","rule_id":"sun-sign-1"}},
          {"op":"all","args":[{"op":"rule_hit_exact","role":"A","rule_id":"sun-sign-1"},
                              {"op":"time_stable","role":"B"}]}]
    for bad in bads:
        with pytest.raises(N3ValidationError):
            validate_predicate(bad,{"A","B"},ids,t,require_coverage=True)
    for key,value in [("predicate","symbolic_coordination"),
                      ("subject_role","B"),("scope_id","n3.scope.unregistered")]:
        bad=copy.deepcopy(d);bad["licensed_effects"][0][key]=value
        bad=seal(bad,"definition_hash")
        with pytest.raises(N3ValidationError):verify_definition(bad,m,t,s,ids)

def test_unknown_kleene_logic():
    a={"op":"time_stable","role":"A"};b={"op":"time_stable","role":"B"}
    resolver=lambda n:"TRUE" if n["role"]=="A" else "FALSE"
    assert evaluate_predicate({"op":"any","args":[b,b]},resolver,complete=False)=="UNKNOWN"
    assert evaluate_predicate({"op":"not","arg":b},resolver,complete=False)=="UNKNOWN"
    assert evaluate_predicate({"op":"not","arg":b},resolver,complete=True)=="TRUE"
    assert evaluate_predicate({"op":"all","args":[a,b]},resolver,complete=False)=="UNKNOWN"

@pytest.mark.parametrize("rule",COMPOSITES,ids=lambda r:r["id"])
@pytest.mark.parametrize("mode",["known","estimated","unknown"])
def test_composites_have_two_real_components(rule,mode):
    chart=chart_for(rule,mode)
    report=interpret_chart(chart,PACK)
    a=adapt_hits(chart,report,PACK,RULES)
    cm=match_composite(rule["id"],a,RULES)
    assert len(cm["component_fact_keys"])==2
    assert len(cm["component_rule_hit_ids"])==2
    assert cm["composite_is_independent_evidence"] is False
    assert a==adapt_hits(chart,report,PACK,RULES)

def test_composite_missing_or_time_unstable_fails():
    rule=COMPOSITES[0]
    chart=chart_for(rule,"unknown",unstable=True)
    a=adapt_hits(chart,interpret_chart(chart,PACK),PACK,RULES)
    with pytest.raises(N3ValidationError):match_composite(rule["id"],a,RULES)
    chart=chart_for(rule)
    report=interpret_chart(chart,PACK)
    report["signals"].pop()
    with pytest.raises(N3ValidationError):adapt_hits(chart,report,PACK,RULES)

def test_raw_hit_tamper_and_alternative_duplication():
    chart=chart_for(COMPOSITES[0])
    report=interpret_chart(chart,PACK)
    report["signals"][0]["text"]="forged"
    with pytest.raises(N3ValidationError):adapt_hits(chart,report,PACK,RULES)
    args={"snapshot_id":digest("s"),"route":"r1_path","definition_id":"d","role":"A"}
    assert alternative_set_id(**args,witness_group_ids=[digest("a"),digest("b")])==(
        alternative_set_id(**args,witness_group_ids=[digest("b"),digest("a")]))
    with pytest.raises(N3ValidationError):
        alternative_set_id(**args,witness_group_ids=[digest("a"),digest("a")])

def test_r1_truncated_b_complete_source_under_review_and_invalid_plan():
    plan,ev,d,s,adapter=a_incomplete_b_proven()
    validate_schema("N3Plan",plan)
    verify_plan(plan,ev,d,s,adapted=adapter,n2_catalog=N2)
    for mutate in (
        lambda p:p["trace"].update(source_snapshot_hash=digest("forged source")),
        lambda p:p["trace"].update(evaluation_trace_hash=digest("forged evaluation")),
        lambda p:p.update(decision="RELATION_LICENSED",primary_reason="NONE",
                          relation_claim_state="licensed_shadow",relation_claim_ids=[digest("claim")]),
        lambda p:p["route_proofs"][0].update(proof_result="proven"),
        lambda p:p.update(primary_reason="INCOMPLETE_SEARCH"),
        lambda p:p["route_proofs"][1].update(route="r1_path"),
    ):
        bad=copy.deepcopy(plan)
        mutate(bad)
        bad["plan_id"]=plan_id(bad) if len({x["route"] for x in bad["route_proofs"]})==2 else digest("duplicate")
        with pytest.raises(N3ValidationError):verify_plan(bad,ev,d,s,adapted=adapter,n2_catalog=N2)

def test_dynamic_n2_categories_dont_promote_symbolic():
    result=verify_n2_catalog(N2,RULES,locked_digest=digest(N2))
    assert result["category_counts"]["rule_readings"]==len(N2["rule_readings"])
    used={x.get("rule_id") for k in ("rule_readings","symbolic_explanations","withheld_editorial_readings") for x in N2.get(k,[])}
    rule=next(r for r in RULES["rules"] if r["id"] not in used)
    cat=copy.deepcopy(N2)
    cat["symbolic_explanations"]=[{"id":"synthetic.symbolic","kind":"symbolic-explanation",
        "rule_id":rule["id"],"axis":rule["axis"],"source_rule_text":rule["text"],
        "source_support":"original-unverified-rule-text-only",
        "display_policy":"non-behavioral-metadata-only-not-personality-N2"}]
    verify_n2_catalog(cat,RULES)
    assert classify_rule(rule["id"],cat)=="symbolic_explanation"
    cat["symbolic_explanations"][0]["behavior"]="unlicensed"
    with pytest.raises(N3ValidationError):verify_n2_catalog(cat,RULES)
    with pytest.raises(N3ValidationError):verify_n2_catalog(N2,RULES,locked_digest=digest("stale"))
