"""N3-contract-2 admission, content-addressing and cross-document validators.

P1 ONLY: no connection to the display/UI and no positive claim issuance.
Schema is extracted unchanged from the frozen PR #30 N3-contract-2 document.
"""
from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).with_name("n3_contracts.schema.json")
CONTRACT_VERSION = "N3-contract-2"
ENABLED = False
ROUTES = ("r1_path", "original_composite")
OPERATORS = {
    "qualifies": "qualified_in_context",
    "restricts": "restricted_by",
    "contrasts": "symbolic_contrast",
    "coordinates": "symbolic_coordination",
    "complements": "symbolic_complement",
}
TRUTH = ("TRUE", "FALSE", "UNKNOWN")
N2_CATEGORIES = ("rule_readings", "symbolic_explanations", "withheld_editorial_readings", "entries")


class N3ValidationError(ValueError):
    """Explicit fail-closed admission failure; never silently recover."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise N3ValidationError(message)


def _normalise(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        _assert(all(isinstance(k, str) for k in value), "canonical: object keys must be strings")
        keys = [_normalise(k) for k in value]
        _assert(len(set(keys)) == len(keys), "canonical: Unicode key collision")
        return {_normalise(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, float):
        _assert(math.isfinite(value), "canonical: non-finite number")
    _assert(value is None or isinstance(value, (bool, int, float)), "canonical: unsupported value")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_normalise(value), sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _without(value: dict, *excluded: str) -> dict:
    return {k: v for k, v in value.items() if k not in excluded}


_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_SCHEMA_VALIDATORS: dict[str, Draft202012Validator] = {}


def validate_schema(kind: str, obj: dict) -> None:
    _assert(kind in _SCHEMA["$defs"], "schema: unknown contract " + kind)
    if kind not in _SCHEMA_VALIDATORS:
        schema = {"$schema": _SCHEMA["$schema"], "$defs": _SCHEMA["$defs"],
                  "$ref": "#/$defs/" + kind}
        _SCHEMA_VALIDATORS[kind] = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(_SCHEMA_VALIDATORS[kind].iter_errors(obj),
                    key=lambda e: (str(list(e.path)), e.message))
    if errors:
        err = errors[0]
        raise N3ValidationError("schema:" + kind + "/" + "/".join(map(str, err.path)) +
                                ": " + err.message)


def seal(value: dict, field: str) -> dict:
    """Used for *creating* test inputs; validators always recompute independently."""
    return {**value, field: digest(_without(value, field))}


def _unique(items: list, key: str) -> None:
    keys = [v[key] for v in items]
    _assert(len(keys) == len(set(keys)), "duplicate " + key)


def _ordered_unique(items: list, key: str) -> None:
    _unique(items, key)
    _assert(items == sorted(items, key=lambda v: v[key]), "noncanonical " + key + " order")


def n2_content_digests(catalog: dict) -> tuple[dict[str, str], str]:
    categories = {k: digest(catalog.get(k, [])) for k in N2_CATEGORIES}
    policies = {
        "rule_reading_policy": catalog.get("rule_reading_policy"),
        "symbolic": [(v.get("id"), v.get("display_policy"), v.get("source_support"))
                     for v in catalog.get("symbolic_explanations", [])],
        "withheld": [(v.get("id"), v.get("status"), v.get("reason"))
                     for v in catalog.get("withheld_editorial_readings", [])],
    }
    return categories, digest(policies)


def make_manifest(rulepack: dict, n2_catalog: dict, ontology: dict,
                  *, r1_version: str, n2_version: str,
                  adapter_version: str = "EvidenceAdapterV1",
                  predicate_version: str = "N3-typed-predicate-1") -> dict:
    cats, policies = n2_content_digests(n2_catalog)
    value = {
        "kind": "UpstreamManifest", "schema_version": CONTRACT_VERSION,
        "rulepack_digest": digest(rulepack),
        "rulepack_version": rulepack["pack_version"],
        "rulepack_schema_version": rulepack["schema_version"],
        "n2_catalog_digest": digest(n2_catalog),
        "n2_catalog_version": n2_catalog["catalog_version"],
        "n2_catalog_schema_version": n2_catalog["schema_version"],
        "n2_category_digests": cats, "n2_category_policies_digest": policies,
        "ontology_digest": digest(ontology), "r1_contract_version": r1_version,
        "n2_contract_version": n2_version,
        "adapter_contract_version": adapter_version,
        "predicate_contract_version": predicate_version,
    }
    return seal(value, "compatible_upstream_hash")


def verify_manifest(manifest: dict, *, rulepack: dict, n2_catalog: dict,
                    ontology: dict) -> None:
    validate_schema("UpstreamManifest", manifest)
    expected = make_manifest(
        rulepack, n2_catalog, ontology,
        r1_version=manifest["r1_contract_version"],
        n2_version=manifest["n2_contract_version"],
        adapter_version=manifest["adapter_contract_version"],
        predicate_version=manifest["predicate_contract_version"],
    )
    _assert(expected == manifest, "SNAPSHOT_MISMATCH: upstream content or signature changed")
    _assert(manifest["compatible_upstream_hash"] == digest(_without(manifest, "compatible_upstream_hash")),
            "SNAPSHOT_MISMATCH: upstream rehash failed")


def verify_registry(registry: dict) -> None:
    kind = registry.get("kind")
    _assert(kind in ("TermRegistry", "SourceReviewRegistry"), "unknown registry kind")
    validate_schema(kind, registry)
    field = "entries" if kind == "TermRegistry" else "anchors"
    id_field = "term_id" if kind == "TermRegistry" else "anchor_id"
    _ordered_unique(registry[field], id_field)
    _assert(digest(_without(registry, "registry_hash")) == registry["registry_hash"],
            "SNAPSHOT_MISMATCH: registry signature")
    if kind == "TermRegistry":
        known = {v["term_id"] for v in registry["entries"]}
        for entry in registry["entries"]:
            _assert(entry["term_id"].split(".")[1] == entry["term_kind"],
                    "term namespace/kind mismatch")
            _assert(set(entry["synonym_ids"]).issubset(known), "unregistered synonym")
            if entry["review_status"] == "approved":
                _assert(bool(entry["reviewer_id"] and entry["reviewed_at"]),
                        "term approval lacks human signature")
    else:
        for anchor in registry["anchors"]:
            _assert(anchor["anchor_hash"] == digest(_without(anchor, "anchor_hash")),
                    "SNAPSHOT_MISMATCH: anchor content changed")
            if anchor["review_status"] == "approved":
                _assert(bool(anchor["reviewer_id"] and anchor["reviewed_at"]) and
                        anchor["visual_verification"] in ("verified", "not_applicable") and
                        anchor["source_text_verification"] == "primary_text_checked",
                        "source approval missing verification")


def make_snapshot_id(manifest: dict, catalog: dict, execution_contract_version: str) -> str:
    return digest({
        "compatible_upstream_hash": manifest["compatible_upstream_hash"],
        "catalog_digest": catalog["catalog_digest"],
        "execution_contract_version": execution_contract_version,
    })


def _terms(registry: dict) -> dict:
    return {x["term_id"]: x for x in registry["entries"]}


def _require_term(term_id: str, term_type: str, registry: dict, approved: bool = True) -> None:
    entry = _terms(registry).get(term_id)
    _assert(entry is not None and entry["term_kind"] == term_type,
            "unregistered or wrong-kind term " + term_id)
    if approved:
        _assert(entry["review_status"] == "approved", "HUMAN_REVIEW_REQUIRED: " + term_id)


def validate_predicate(ast: dict, roles: set[str], rule_ids: set[str] | None = None,
                       terms: dict | None = None, max_nodes: int = 192, max_depth: int = 24,
                       require_coverage: bool = False) -> None:
    nodes = [0]
    role_hits: set[str] = set()
    positive_facts: set[str] = set()

    def visit(node: dict, depth: int, *, positive: bool, outside_any: bool) -> None:
        nodes[0] += 1
        _assert(nodes[0] <= max_nodes and depth <= max_depth, "AST resource cap")
        validate_schema("Predicate", node)
        op = node["op"]
        if op in ("all", "any"):
            for child in node["args"]:
                visit(child, depth + 1, positive=positive,
                      outside_any=outside_any and op == "all")
        elif op == "not":
            _assert(node["arg"]["op"] not in ("rule_hit_exact", "placement_exact",
                     "aspect_exact", "house_exact", "polarity_exact", "time_stable"),
                    "not cannot negate positive role proof")
            visit(node["arg"], depth + 1, positive=False, outside_any=False)
        else:
            leaf_roles = node["roles"] if op == "no_blocking_tension" else [node["role"]]
            _assert(set(leaf_roles).issubset(roles), "AST unknown role")
            if op == "rule_hit_exact":
                _assert(rule_ids is None or node["rule_id"] in rule_ids, "AST unknown rule")
                if positive and outside_any:
                    role_hits.add(node["role"])
            if op in ("placement_exact", "aspect_exact", "house_exact") and positive and outside_any:
                positive_facts.add(node["role"])
            if op == "aspect_exact":
                _assert(node["body_a"] < node["body_b"], "noncanonical aspect pair")
            if op == "atom_term_equals":
                _assert(node["term_id"].split(".")[1] == node["field"], "wrong AST term namespace")
                if terms is not None:
                    _require_term(node["term_id"], node["field"], terms)

    visit(ast, 0, positive=True, outside_any=True)
    if require_coverage:
        _assert(ast["op"] == "all", "role proof root must be all")
        _assert(roles.issubset(role_hits) and roles.issubset(positive_facts),
                "incomplete positive participant coverage")


def evaluate_predicate(ast: dict, resolver: Callable[[dict], str],
                       *, complete: bool = False) -> Literal["TRUE", "FALSE", "UNKNOWN"]:
    """Strong Kleene logic. No false-from-absence under incomplete search."""
    op = ast["op"]
    if op == "all":
        values = [evaluate_predicate(a, resolver, complete=complete) for a in ast["args"]]
        return "FALSE" if "FALSE" in values else "UNKNOWN" if "UNKNOWN" in values else "TRUE"
    if op == "any":
        values = [evaluate_predicate(a, resolver, complete=complete) for a in ast["args"]]
        return "TRUE" if "TRUE" in values else (
            "FALSE" if complete and all(x == "FALSE" for x in values) else "UNKNOWN")
    if op == "not":
        value = evaluate_predicate(ast["arg"], resolver, complete=complete)
        return "UNKNOWN" if value == "UNKNOWN" or (value == "FALSE" and not complete) else (
            "FALSE" if value == "TRUE" else "TRUE")
    value = resolver(ast)
    _assert(value in TRUTH, "resolver: invalid ternary result")
    return value if value != "FALSE" or complete else "UNKNOWN"


def verify_definition(definition: dict, manifest: dict, terms: dict,
                      sources: dict, rule_ids: set[str]) -> None:
    validate_schema("RelationDefinition", definition)
    _assert(definition["definition_hash"] == digest(_without(definition, "definition_hash")),
            "SNAPSHOT_MISMATCH: definition hash")
    _assert(definition["compatible_upstream_hash"] == manifest["compatible_upstream_hash"],
            "SNAPSHOT_MISMATCH: definition upstream")
    _assert(definition["term_registry_hash"] == terms["registry_hash"], "term registry mismatch")
    _ordered_unique(definition["participant_specs"], "role")
    roles = {x["role"] for x in definition["participant_specs"]}
    _assert("A" in roles and "B" in roles, "roles A and B required")
    for spec in definition["participant_specs"]:
        _assert(set(spec["allowed_rule_ids"]).issubset(rule_ids), "unknown permitted rule")
        validate_predicate(spec["atom_constraints"], roles, rule_ids, terms)
    validate_predicate(definition["predicate_ast"], roles, rule_ids, terms, require_coverage=True)
    anchor_map = {a["anchor_id"]: a for a in sources["anchors"]}
    _ordered_unique(definition["source_anchors"], "anchor_id")
    for a in definition["source_anchors"]:
        _assert(a["anchor_id"] in anchor_map and a == anchor_map[a["anchor_id"]],
                "source anchor not present or differs from signed registry")
    _unique(definition["licensed_effects"], "effect_id")
    for effect in definition["licensed_effects"]:
        _assert(effect["predicate"] == OPERATORS[definition["operator"]], "OPERATOR_EFFECT_MISMATCH")
        subj, obj = effect["subject_role"], effect["object_role"]
        _assert(subj in roles and obj in roles and subj != obj, "invalid effect roles")
        if definition["direction"] == "A_to_B":
            _assert((subj, obj) == ("A", "B"), "inverted directed effect")
        elif definition["direction"] == "B_to_A":
            _assert((subj, obj) == ("B", "A"), "inverted directed effect")
        _require_term(effect["context_id"], "context", terms)
        _require_term(effect["scope_id"], "scope", terms)
        for t in effect["boundary_ids"]:
            _require_term(t, "boundary", terms)
        for aid in effect["source_anchor_ids"]:
            _assert(aid in anchor_map, "effect references absent anchor")
            anchor = anchor_map[aid]
            _assert(effect["effect_id"] in anchor["supported_effect_ids"], "effect not in source scope")
    _assert(definition["relation_review"]["status"] != "approved_for_symbolic_wording" or
            bool(definition["relation_review"]["reviewer_id"] and definition["relation_review"]["reviewed_at"]),
            "relation approval must have human reviewer")


def verify_catalog(catalog: dict, manifest: dict, terms: dict, sources: dict,
                   rule_ids: set[str]) -> None:
    validate_schema("RelationCatalog", catalog)
    verify_registry(terms)
    verify_registry(sources)
    _assert(catalog["compatible_upstream_hash"] == manifest["compatible_upstream_hash"],
            "SNAPSHOT_MISMATCH: catalog upstream")
    _assert(catalog["term_registry_hash"] == terms["registry_hash"], "catalog terms mismatch")
    _assert(catalog["source_registry_hash"] == sources["registry_hash"], "catalog sources mismatch")
    _ordered_unique(catalog["definitions"], "definition_id")
    for definition in catalog["definitions"]:
        verify_definition(definition, manifest, terms, sources, rule_ids)
    _assert(catalog["catalog_digest"] == digest(_without(catalog, "catalog_digest")),
            "SNAPSHOT_MISMATCH: catalog digest")


def verify_snapshot(snapshot_id: str, manifest: dict, catalog: dict,
                    execution_contract_version: str) -> None:
    _assert(snapshot_id == make_snapshot_id(manifest, catalog, execution_contract_version),
            "SNAPSHOT_MISMATCH: derived snapshot id")


def evaluation_id(evaluation: dict) -> str:
    bindings = evaluation["bindings"]
    _assert(bindings == sorted(bindings, key=lambda x: (x["role"], x["rule_hit_id"])),
            "noncanonical evaluation binding order")
    return digest({
        "snapshot_id": evaluation["snapshot_id"],
        "chart_fingerprint": evaluation["chart_fingerprint"],
        "run_id": evaluation["run_id"],
        "definition_hash": evaluation["definition_hash"],
        "ordered_bindings_hash": digest(bindings),
        "candidate_id": evaluation["candidate_id"],
    })


def claim_id(claim: dict) -> str:
    return digest({"evaluation_id": claim["evaluation_id"],
                   "licensed_effect_id": claim["licensed_effect_id"],
                   "derived_effect_key": digest(claim["derived_predicate"]),
                   "source_anchor_refs": sorted(claim["source_anchor_refs"])})


def plan_id(plan: dict) -> str:
    return digest({"evaluation_id": plan["evaluation_id"],
                   "decision": plan["decision"],
                   "primary_reason": plan["primary_reason"],
                   "route_proof_hashes": [digest(x) for x in sorted(
                       plan["route_proofs"], key=lambda x: ROUTES.index(x["route"]))],
                   "reason_records": plan["reasons"],
                   "claim_ids": sorted(plan["relation_claim_ids"])})


def verify_route_proofs(proofs: list[dict]) -> dict[str, dict]:
    _assert(len(proofs) == 2, "exactly two route proofs required")
    for proof in proofs:
        validate_schema("RouteProof", proof)
    _assert([x["route"] for x in proofs] == list(ROUTES), "routes missing, repeated or unordered")
    for p in proofs:
        _assert(p["visited"] <= p["cap"], "resource cap invalid")
        _assert(len(p["selected_binding_ids"]) == len(set(p["selected_binding_ids"])),
                "duplicate proof binding")
        if p["candidate_state"] == "not_candidate":
            _assert(p["search_state"] == "not_applicable" and p["search_complete"] is None
                    and p["proof_result"] == "not_candidate" and p["visited"] == 0,
                    "not_candidate mismatch")
        elif p["candidate_state"] == "candidate":
            _assert(p["search_complete"] is (p["search_state"] == "complete"),
                    "search state/completeness mismatch")
            if not p["search_complete"]:
                _assert(p["proof_result"] == "unknown" and
                        "INCOMPLETE_SEARCH" in p["failure_reasons"] and
                        not p["selected_binding_ids"], "incomplete route cannot prove")
            if p["proof_result"] == "proven":
                _assert(p["search_complete"] is True and p["selected_binding_ids"]
                        and not p["failure_reasons"], "truncated or empty proof marked proven")
        else:
            _assert(p["search_state"] == "not_applicable" and p["search_complete"] is None,
                    "not_executed inconsistent")
    return {p["route"]: p for p in proofs}


def verify_evaluation(evaluation: dict, definition: dict, snapshot_id: str,
                      *, adapter_trace: dict | None = None) -> None:
    validate_schema("RelationEvaluation", evaluation)
    _assert(evaluation["snapshot_id"] == snapshot_id, "SNAPSHOT_MISMATCH: evaluation")
    _assert(evaluation["definition_id"] == definition["definition_id"] and
            evaluation["definition_hash"] == definition["definition_hash"], "definition mismatch")
    _assert(evaluation_id(evaluation) == evaluation["evaluation_id"], "BAD_ID: evaluation")
    proofs = verify_route_proofs(evaluation["route_proofs"])
    _assert(set(evaluation["discovery_routes"]).issubset(proofs), "unknown discovery route")
    _unique(evaluation["bindings"], "rule_hit_id")
    ids = {b["rule_hit_id"] for b in evaluation["bindings"]}
    _assert(all(b["rule_hit_id"] in ids for b in evaluation["selected_witnesses"]),
            "invented selected witness")
    _assert(set(evaluation["matched_rule_hits"]) == ids, "matched hits/bindings mismatch")
    for proof in proofs.values():
        _assert(set(proof["selected_binding_ids"]).issubset(ids), "invented proof binding")
    if adapter_trace is not None:
        _assert(evaluation["trace_digest"] == digest(adapter_trace), "provenance trace mismatch")
    else:
        raise N3ValidationError("PROVENANCE_MISMATCH: original adapter trace required")


def source_eligible(definition: dict, sources: dict) -> bool:
    by_id = {x["anchor_id"]: x for x in sources["anchors"]}
    return (definition["relation_review"]["status"] == "approved_for_symbolic_wording"
            and all(a["review_status"] == "approved"
                    and a["support_kind"] == "explicit_attestation"
                    and a["source_text_verification"] == "primary_text_checked"
                    and a["visual_verification"] in ("verified", "not_applicable")
                    for a in definition["source_anchors"])
            and all(aid in by_id and by_id[aid] == a
                    for a in definition["source_anchors"]
                    for aid in [a["anchor_id"]]))


def verify_plan(plan: dict, evaluation: dict, definition: dict, sources: dict,
                *, claims: list[dict] = (), allow_user: bool = False) -> None:
    validate_schema("N3Plan", plan)
    proofs = verify_route_proofs(plan["route_proofs"])
    _assert(plan["route_proofs"] == evaluation["route_proofs"], "route proof differs from evaluation")
    _assert(plan["snapshot_id"] == evaluation["snapshot_id"] and
            plan["evaluation_id"] == evaluation["evaluation_id"] and
            plan["definition_id"] == definition["definition_id"], "plan reference mismatch")
    _assert(plan["plan_id"] == plan_id(plan), "BAD_ID: plan signature")
    _assert(plan["reasons"] == sorted(plan["reasons"], key=lambda x: (
        ROUTES.index(x["route"]) if x["route"] in ROUTES else 2, not x["blocking"], x["code"])),
        "reason order inconsistent")
    _assert(len({(r["route"], r["code"]) for r in plan["reasons"]}) ==
            len(plan["reasons"]), "duplicate reason")
    route = plan["trace"]["selected_decisive_route"]
    decision = plan["decision"]
    reasons = plan["reasons"]
    blocking = [r for r in reasons if r["blocking"]]
    if route != "none":
        _assert(proofs[route]["candidate_state"] == "candidate", "decisive route not candidate")
        _assert(all(r["route"] in (route, "global") for r in blocking),
                "nondecisive route must not block")
    if plan["primary_reason"] == "NONE":
        _assert(not blocking, "NONE with blocking reasons")
    else:
        _assert(any(r["code"] == plan["primary_reason"] and r["blocking"] and
                    (r["route"] == route or r["route"] == "global") for r in reasons),
                "primary_reason does not match decisive route")
    _assert(len(plan["retained_atomic_rule_ids"]) ==
            len(set(plan["retained_atomic_rule_ids"])), "duplicate atomic rule")
    if decision == "RELATION_LICENSED":
        _assert(source_eligible(definition, sources), "NO_RELATION_SOURCE")
        _assert(not blocking and plan["primary_reason"] == "NONE", "licensed with blocked reason")
        _assert(route != "none" and proofs[route]["proof_result"] == "proven"
                and proofs[route]["search_complete"] is True, "licensed without complete proof")
        _assert(evaluation["source_license_check"]["status"] == "pass" and
                evaluation["novelty_check"]["status"] == "pass", "unverified licensing/novelty")
        _assert(plan["relation_claim_state"] == "licensed_shadow" and
                plan["relation_claim_ids"], "licensed state missing claims")
        _assert({c["claim_id"] for c in claims} == set(plan["relation_claim_ids"]),
                "claim references invented")
        _assert(not allow_user, "P1 cannot issue user claims")
    else:
        _assert(not plan["relation_claim_ids"], "unlicensed decision includes claims")
        _assert(plan["relation_claim_state"] != "licensed_shadow", "unlicensed claim state")
    if decision == "COMPARISON_ONLY":
        _assert(plan["comparison_state"] == "available" and
                plan["relation_claim_state"] == "blocked", "comparison states inconsistent")
        _assert(route != "none" and proofs[route]["proof_result"] == "proven" and
                proofs[route]["search_complete"] is True, "comparison must have proven decisive route")
        _assert(blocking, "comparison without blocking reason")
    if decision == "INDETERMINATE":
        _assert(plan["relation_claim_state"] == "indeterminate", "indeterminate state")
        _assert(any(p["candidate_state"] == "candidate" and not p["search_complete"]
                    for p in proofs.values()), "no incomplete search")
        _assert(not any(p["proof_result"] == "proven" and p["search_complete"]
                        for p in proofs.values()), "complete route overrides indeterminate")
    if decision == "NOT_APPLICABLE":
        _assert(all(p["candidate_state"] == "not_candidate" for p in proofs.values()),
                "not_applicable must exhaust both routes")
        _assert(plan["relation_claim_state"] == "not_applicable", "not_applicable state")
    if decision in ("ABSTAIN", "QUARANTINE", "INVALID_INPUT"):
        _assert(bool(blocking), "blocked decision without reason")


def verify_claim(claim: dict, evaluation: dict, definition: dict, sources: dict,
                 *, plan: dict, allow_user: bool = False) -> None:
    validate_schema("NarrativeClaim", claim)
    _assert(claim["claim_id"] == claim_id(claim), "BAD_ID: claim")
    _assert(claim["evaluation_id"] == evaluation["evaluation_id"], "claim evaluation mismatch")
    _assert(claim["licensed_effect_id"] in
            {x["effect_id"] for x in definition["licensed_effects"]}, "unknown effect")
    _assert(plan["decision"] == "RELATION_LICENSED" and
            claim["claim_id"] in plan["relation_claim_ids"], "claim missing licensed plan")
    _assert(evaluation["source_license_check"]["status"] == "pass" and
            evaluation["novelty_check"]["status"] == "pass" and
            source_eligible(definition, sources), "unlicensed source or novelty")
    _assert(claim["audience"] != "user" and not allow_user, "P1 user output always forbidden")
