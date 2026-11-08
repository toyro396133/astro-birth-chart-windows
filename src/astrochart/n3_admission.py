"""Single mandatory, offline N3-P1 admission boundary.

Public admission never issues a licensed relation or a user-visible claim. All
upstream data are re-read from installed, reviewed local files, rather than
accepting a caller-generated "trusted hash". Structural helper validators are
not authorization entrypoints.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .interpretation import load_rulepack
from .synthesis import FUNCTIONS, TRANSITIONS, SYNTHESIS_VERSION
from .n3_contracts import (
    N3ValidationError, _assert, digest, validate_schema, verify_hash_dag,
    verify_manifest, verify_registry, verify_catalog, verify_snapshot,
    verify_definition, verify_evaluation, verify_evidence_bindings,
    verify_plan, source_eligible, evaluate_bound_predicate,
    source_conditions_state,
)
from .n3_evidence import adapt_hits, map_r1_witnesses, match_composite
from .n3_n2 import verify_n2_catalog

_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AdmissionResult:
    status: str
    plan_id: str
    snapshot_id: str
    source_condition_state: str
    relation_predicate_state: str
    claim_ids: tuple[str, ...] = ()  # Always empty until audited P2–P4 gates.


def _installed_assets():
    """Trust root: installed repository contents, not any untrusted JSON."""
    rulepack = json.loads((_ROOT / "interpretation_rules.json").read_text(encoding="utf-8"))
    n2 = json.loads((_ROOT / "meaning_catalog_n2.json").read_text(encoding="utf-8"))
    ontology = {"functions": FUNCTIONS, "transitions": TRANSITIONS,
                "version": SYNTHESIS_VERSION}
    return rulepack, n2, ontology


def admit_n3_bundle(*, manifest: dict, relation_catalog: dict,
                    terms: dict, sources: dict, definition_id: str,
                    snapshot_id: str, execution_contract_version: str,
                    chart, report: dict, pack, raw_rulepack: dict,
                    n2_catalog: dict, evaluation: dict, plan: dict,
                    claims: tuple[dict, ...] = (), r1_node: dict | None = None,
                    calculation_profile: str = "western-tropical-whole-sign-r1") -> AdmissionResult:
    """Atomic admission. Every failed check raises N3ValidationError; no fallback.

    P1 has zero approved source roots, gold references and output permissions.
    A complete B proof can yield a comparison when A is capped, but not a claim.
    """
    verify_hash_dag()
    # Fail on incomplete objects *before* reading their fields.
    for kind, obj in (
        ("UpstreamManifest", manifest), ("TermRegistry", terms),
        ("SourceReviewRegistry", sources), ("RelationCatalog", relation_catalog),
        ("RelationEvaluation", evaluation), ("N3Plan", plan),
    ):
        validate_schema(kind, obj)
    for claim in claims:
        validate_schema("NarrativeClaim", claim)
    _assert(not claims and not plan["relation_claim_ids"] and
            plan["decision"] != "RELATION_LICENSED",
            "NOT_LICENSED: P1 has no positive source approval or claim authorization")
    pinned_pack, pinned_n2, pinned_ontology = _installed_assets()
    _assert(digest(raw_rulepack) == digest(pinned_pack),
            "UNTRUSTED_UPSTREAM: raw RulePack differs from installed source")
    _assert(digest(n2_catalog) == digest(pinned_n2),
            "UNTRUSTED_UPSTREAM: N2 differs from installed source")
    _assert(pack == load_rulepack(), "UNTRUSTED_UPSTREAM: runtime RulePack differs")
    _assert(manifest["r1_contract_version"] == SYNTHESIS_VERSION and
            manifest["n2_contract_version"] == pinned_n2["catalog_version"] and
            manifest["adapter_contract_version"] == "EvidenceAdapterV1" and
            manifest["predicate_contract_version"] == "N3-typed-predicate-1",
            "UNTRUSTED_UPSTREAM: interface version mismatch")
    verify_n2_catalog(n2_catalog, raw_rulepack, locked_digest=digest(pinned_n2))
    verify_manifest(manifest, rulepack=pinned_pack, n2_catalog=pinned_n2,
                    ontology=pinned_ontology)
    verify_registry(terms)
    verify_registry(sources)
    active_ids = {r["id"] for r in pinned_pack["rules"] if r["enabled"]}
    verify_catalog(relation_catalog, manifest, terms, sources, active_ids,
                   raw_rulepack=pinned_pack)
    matches = [d for d in relation_catalog["definitions"] if d["definition_id"] == definition_id]
    _assert(len(matches) == 1, "BAD_ID: definition not found in admitted catalog")
    definition = matches[0]
    verify_definition(definition, manifest, terms, sources, active_ids,
                      raw_rulepack=pinned_pack)
    verify_snapshot(snapshot_id, manifest, relation_catalog, execution_contract_version)
    _assert(evaluation["snapshot_id"] == plan["snapshot_id"] == snapshot_id,
            "SNAPSHOT_MISMATCH: relation evaluation/plan")
    adapter = adapt_hits(chart, report, pack, pinned_pack,
                         calculation_profile=calculation_profile)
    verify_evaluation(evaluation, definition, snapshot_id, adapter_trace=adapter)
    _assert(evaluation["chart_fingerprint"] == adapter["chart_fingerprint"],
            "PROVENANCE_MISMATCH: chart fingerprint")
    verify_evidence_bindings(evaluation, adapter, definition=definition,
                             n2_catalog=pinned_n2)
    proofs = {proof["route"]: proof for proof in evaluation["route_proofs"]}
    direct = proofs["original_composite"]
    if direct["proof_result"] == "proven":
        given = evaluation["original_composite_match"]
        _assert(given is not None, "PROVENANCE_MISMATCH: composite missing")
        expected = match_composite(given["composite_rule_id"], adapter, pinned_pack)
        _assert(given == expected, "PROVENANCE_MISMATCH: composite was fabricated")
    r1 = proofs["r1_path"]
    if r1["candidate_state"] == "candidate":
        _assert(r1_node is not None, "UNVERIFIED_R1: cannot accept caller's search state")
        checked = map_r1_witnesses(r1_node, adapter, chart=chart, report=report)
        _assert(r1["search_complete"] == checked["search_complete"] and
                r1["visited"] == checked["visited"] and r1["cap"] == checked["cap"],
                "PROVENANCE_MISMATCH: R1 proof search metadata")
        if r1["proof_result"] == "proven":
            selected_ids = {rid for group in checked["selected"].values()
                            for rid in group["rule_hit_ids"]}
            _assert(set(r1["selected_binding_ids"]) == selected_ids,
                    "PROVENANCE_MISMATCH: R1 proof IDs")
    elif r1_node is not None:
        raise N3ValidationError("PROVENANCE_MISMATCH: R1 node supplied for noncandidate route")
    # Semantics are evaluated against the authenticated selected witness set,
    # never JSON wording, unfamiliar term IDs or synthetic meaning mappings.
    relation_state = evaluate_bound_predicate(definition["predicate_ast"],
                                               definition, evaluation, adapter, complete=True)
    source_state = source_conditions_state(definition, evaluation, adapter)
    if relation_state != "TRUE" or source_state != "TRUE" or not source_eligible(definition, sources):
        _assert(evaluation["source_license_check"]["status"] != "pass",
                "NOT_LICENSED: source/role predicate unreviewed or false")
    _assert(evaluation["novelty_check"]["status"] != "pass",
            "HUMAN_REVIEW_REQUIRED: P1 has no independently approved novelty")
    verify_plan(plan, evaluation, definition, sources, claims=list(claims),
                adapted=adapter, n2_catalog=pinned_n2)
    return AdmissionResult(status=plan["decision"], plan_id=plan["plan_id"],
                           snapshot_id=snapshot_id, source_condition_state=source_state,
                           relation_predicate_state=relation_state)
