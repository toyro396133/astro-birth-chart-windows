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
from . import synthesis as r1_engine

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


def limited_r1_trace(adapter: dict, path: tuple[str, ...], visited: int, cap: int) -> str:
    """Commit a missing-node R1 search to exact source chart and bounded path."""
    return digest({"route": "r1_path", "chart_fingerprint": adapter["chart_fingerprint"],
                   "path": list(path), "search_state": "incomplete",
                   "visited": visited, "cap": cap})


def verify_r1_route(chart, report: dict, definition: dict, raw_rulepack: dict,
                    adapted: dict, proof: dict, *,
                    r1_node: dict | None = None,
                    limited_path: tuple[str, ...] | None = None) -> bool:
    """Replay original R1 and authenticate a capped path even without a node.

    All path and budget claims are compared with a freshly computed synthesis.
    No caller-provided status, path, trace or self-hash can create a limit.
    """
    synthesis = r1_engine.synthesize(chart, report)
    nodes = [n for n in synthesis["nodes"] if n["type"] == "synthesis"]
    limited_paths = {tuple(path) for path in
                     synthesis["summary"]["proof_search_limited_paths"]}
    permitted_axes = {
        spec["role"]: {rule["axis"] for rule in raw_rulepack["rules"]
                       if rule["id"] in spec["allowed_rule_ids"]}
        for spec in definition["participant_specs"]
    }

    def relevant(path: tuple[str, ...]) -> bool:
        return all(bool(axes & set(path)) for axes in permitted_axes.values())

    relevant_limits = {path for path in limited_paths if relevant(path)}
    if proof["candidate_state"] == "not_candidate":
        _assert(r1_node is None and limited_path is None,
                "PROVENANCE_MISMATCH: unexpected R1 candidate metadata")
        _assert(not relevant_limits, "PROVENANCE_MISMATCH: R1 not_candidate despite limited search")
        return False
    if proof["candidate_state"] != "candidate":
        _assert(r1_node is None and limited_path is None,
                "PROVENANCE_MISMATCH: R1 route not executed")
        return False
    _assert((r1_node is None) != (limited_path is None),
            "UNVERIFIED_R1: exactly one of R1 node or capped path required")
    if r1_node is not None:
        checked = map_r1_witnesses(r1_node, adapted, chart=chart, report=report)
        _assert(relevant(tuple(r1_node["path"])),
                "PROVENANCE_MISMATCH: R1 node unrelated to relation roles")
        _assert(proof["search_complete"] == checked["search_complete"] and
                proof["visited"] == checked["visited"] and
                proof["cap"] == checked["cap"],
                "PROVENANCE_MISMATCH: R1 node search metadata")
        if proof["proof_result"] == "proven":
            selected = {rid for group in checked["selected"].values()
                        for rid in group["rule_hit_ids"]}
            _assert(set(proof["selected_binding_ids"]) == selected,
                    "PROVENANCE_MISMATCH: R1 route proof IDs")
        return proof["search_complete"] is False
    path = tuple(limited_path)
    _assert(path in relevant_limits,
            "UNVERIFIED_R1: no matching genuine capped search path")
    _assert(not any(tuple(n["path"]) == path for n in nodes),
            "PROVENANCE_MISMATCH: capped search already emitted an R1 node")
    _assert(proof["search_complete"] is False and
            proof["proof_result"] == "unknown" and not proof["selected_binding_ids"],
            "PROVENANCE_MISMATCH: missing-node R1 cannot prove")
    # Re-run the same original bounded search, rather than trusting visited/cap.
    base, _ = r1_engine._base_features(report)
    by_axis = {n["axis"]: n for n in base}
    _assert(set(path).issubset(by_axis),
            "PROVENANCE_MISMATCH: R1 path uses absent base axis")
    chosen, _, capped, visited = r1_engine._choose_path_proof(path, by_axis)
    cap = r1_engine.MAX_PROOF_STATES
    _assert(chosen is None and capped and
            proof["visited"] == visited and proof["cap"] == cap and
            proof["trace_hash"] == limited_r1_trace(adapted, path, visited, cap),
            "PROVENANCE_MISMATCH: R1 truncated-search trace not genuine")
    return True


def admit_n3_bundle(*, manifest: dict, relation_catalog: dict,
                    terms: dict, sources: dict, definition_id: str,
                    snapshot_id: str, execution_contract_version: str,
                    chart, report: dict, pack, raw_rulepack: dict,
                    n2_catalog: dict, evaluation: dict, plan: dict,
                    claims: tuple[dict, ...] = (), r1_node: dict | None = None,
                    r1_limited_path: tuple[str, ...] | None = None,
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
    verified_r1_incomplete = verify_r1_route(
        chart, report, definition, pinned_pack, adapter, r1,
        r1_node=r1_node, limited_path=r1_limited_path)
    decisive_route = plan["trace"]["selected_decisive_route"]
    _assert(decisive_route == "none" or decisive_route in proofs,
            "PROVENANCE_MISMATCH: unknown decisive route")
    decisive_ids = (set(proofs[decisive_route]["selected_binding_ids"])
                    if decisive_route != "none" else set())
    selected_ids = {x["rule_hit_id"] for x in evaluation["selected_witnesses"]}
    _assert(selected_ids == decisive_ids,
            "PROVENANCE_MISMATCH: semantic witnesses are not decisive-route proof witnesses")
    # Semantics are evaluated against the authenticated selected witness set,
    # never JSON wording, unfamiliar term IDs or synthetic meaning mappings.
    relation_state = evaluate_bound_predicate(definition["predicate_ast"],
                                               definition, evaluation, adapter, complete=True,
                                               selected_binding_ids=decisive_ids)
    source_state = source_conditions_state(
        definition, evaluation, adapter, selected_binding_ids=decisive_ids)
    if relation_state != "TRUE" or source_state != "TRUE" or not source_eligible(definition, sources):
        _assert(evaluation["source_license_check"]["status"] != "pass",
                "NOT_LICENSED: source/role predicate unreviewed or false")
    _assert(evaluation["novelty_check"]["status"] != "pass",
            "HUMAN_REVIEW_REQUIRED: P1 has no independently approved novelty")
    verify_plan(plan, evaluation, definition, sources, claims=list(claims),
                adapted=adapter, n2_catalog=pinned_n2,
                chart=chart, report=report, raw_rulepack=pinned_pack,
                r1_node=r1_node, r1_limited_path=r1_limited_path,
                relation_state=relation_state, source_state=source_state)
    return AdmissionResult(status=plan["decision"], plan_id=plan["plan_id"],
                           snapshot_id=snapshot_id, source_condition_state=source_state,
                           relation_predicate_state=relation_state)
