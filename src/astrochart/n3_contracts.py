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

# Separate immutable approval root. P1 has ZERO source reviews approved for relations.
# Caller-controlled hashes, status and reviewer text can never extend this allowlist.
PINNED_APPROVED_SOURCE_REGISTRY_HASHES: frozenset[str] = frozenset()


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
    _assert(all(k in catalog and isinstance(catalog[k], list) for k in N2_CATEGORIES),
            "N2 mandatory category absent")
    categories = {k: digest(catalog[k]) for k in N2_CATEGORIES}
    policies = {
        "rule_reading_policy": catalog.get("rule_reading_policy"),
        "symbolic": [(v.get("id"), v.get("display_policy"), v.get("source_support"))
                     for v in catalog["symbolic_explanations"]],
        "withheld": [(v.get("id"), v.get("status"), v.get("reason"))
                     for v in catalog["withheld_editorial_readings"]],
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
    from .n3_n2 import verify_n2_catalog
    verify_n2_catalog(n2_catalog, rulepack)


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
                       require_coverage: bool = False,
                       allowed_by_role: dict[str, set[str]] | None = None,
                       facts_by_role: dict[str, set[str]] | None = None) -> None:
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
            def guard_only(subtree: dict) -> bool:
                operation = subtree["op"]
                if operation in ("all", "any"):
                    return all(guard_only(child) for child in subtree["args"])
                # Prevent not(all/any(...positive fact...)) and double negation.
                return operation in ("no_blocking_tension", "atom_term_equals")
            _assert(guard_only(node["arg"]), "not may only negate a guard, not role evidence")
            visit(node["arg"], depth + 1, positive=False, outside_any=False)
        else:
            leaf_roles = node["roles"] if op == "no_blocking_tension" else [node["role"]]
            _assert(set(leaf_roles).issubset(roles), "AST unknown role")
            if op == "rule_hit_exact":
                _assert(rule_ids is None or node["rule_id"] in rule_ids, "AST unknown rule")
                _assert(allowed_by_role is None or
                        node["rule_id"] in allowed_by_role[node["role"]],
                        "AST rule not allowed for role")
                if positive and outside_any:
                    role_hits.add(node["role"])
            if op in ("placement_exact", "aspect_exact", "house_exact"):
                if op == "placement_exact":
                    fact = "placement:" + node["body"] + ":" + node["sign"]
                elif op == "aspect_exact":
                    fact = "aspect:" + ":".join(sorted((node["body_a"], node["body_b"]))) + ":" + node["aspect_kind"]
                else:
                    fact = "house:" + node["body"] + ":" + str(node["house"])
                _assert(facts_by_role is None or fact in facts_by_role[node["role"]],
                        "AST fact incompatible with allowed role RulePack.when")
                if positive and outside_any:
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
                      sources: dict, rule_ids: set[str], *,
                      raw_rulepack: dict | None = None) -> None:
    validate_schema("RelationDefinition", definition)
    _assert(definition["definition_hash"] == digest(_without(definition, "definition_hash")),
            "SNAPSHOT_MISMATCH: definition hash")
    _assert(definition["compatible_upstream_hash"] == manifest["compatible_upstream_hash"],
            "SNAPSHOT_MISMATCH: definition upstream")
    _assert(definition["term_registry_hash"] == terms["registry_hash"], "term registry mismatch")
    _ordered_unique(definition["participant_specs"], "role")
    roles = {x["role"] for x in definition["participant_specs"]}
    _assert("A" in roles and "B" in roles, "roles A and B required")
    allowed = {s["role"]: set(s["allowed_rule_ids"]) for s in definition["participant_specs"]}
    facts_by_role = None
    if raw_rulepack is not None:
        from .n3_evidence import _fact_keys
        rules = {r["id"]: r for r in raw_rulepack["rules"] if r.get("enabled")}
        _assert(set.union(set(), *allowed.values()).issubset(rules),
                "allowed role rules not active in verified RulePack")
        facts_by_role = {role: {fact for rid in ids for fact in _fact_keys(rules[rid])}
                         for role, ids in allowed.items()}
    for spec in definition["participant_specs"]:
        _assert(set(spec["allowed_rule_ids"]).issubset(rule_ids), "unknown permitted rule")
        validate_predicate(spec["atom_constraints"], roles, rule_ids, terms,
                           allowed_by_role=allowed, facts_by_role=facts_by_role)
    validate_predicate(definition["predicate_ast"], roles, rule_ids, terms,
                       require_coverage=True, allowed_by_role=allowed,
                       facts_by_role=facts_by_role)
    anchor_map = {a["anchor_id"]: a for a in sources["anchors"]}
    _ordered_unique(definition["source_anchors"], "anchor_id")
    for a in definition["source_anchors"]:
        _assert(a["anchor_id"] in anchor_map and a == anchor_map[a["anchor_id"]],
                "source anchor not present or differs from signed registry")
        _require_term(a["scope_id"], "scope", terms)
        validate_predicate(a["matching_conditions"], roles, rule_ids, terms,
                           allowed_by_role=allowed, facts_by_role=facts_by_role)
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
            _assert(anchor["scope_id"] == effect["scope_id"], "SOURCE_SCOPE_EXCEEDED")
    _assert(definition["relation_review"]["status"] != "approved_for_symbolic_wording" or
            bool(definition["relation_review"]["reviewer_id"] and definition["relation_review"]["reviewed_at"]),
            "relation approval must have human reviewer")


def verify_catalog(catalog: dict, manifest: dict, terms: dict, sources: dict,
                   rule_ids: set[str], *, raw_rulepack: dict | None = None) -> None:
    validate_schema("RelationCatalog", catalog)
    verify_registry(terms)
    verify_registry(sources)
    _assert(catalog["compatible_upstream_hash"] == manifest["compatible_upstream_hash"],
            "SNAPSHOT_MISMATCH: catalog upstream")
    _assert(catalog["term_registry_hash"] == terms["registry_hash"], "catalog terms mismatch")
    _assert(catalog["source_registry_hash"] == sources["registry_hash"], "catalog sources mismatch")
    _ordered_unique(catalog["definitions"], "definition_id")
    for definition in catalog["definitions"]:
        verify_definition(definition, manifest, terms, sources, rule_ids,
                          raw_rulepack=raw_rulepack)
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
    """P1 amendment: full-content SHA256, not merely the identity projection.

    With schema additionalProperties=false there is no field for a separate seal;
    use the public ID as the content seal until a versioned schema revision.
    """
    return digest(_without(claim, "claim_id"))


def plan_id(plan: dict) -> str:
    """P1 amendment: seal *all* trace, reason, retained atom and claim-state fields."""
    return digest(_without(plan, "plan_id"))


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
                    and p["proof_result"] == "not_candidate" and p["visited"] == 0
                    and not p["selected_binding_ids"] and not p["source_fact_refs"]
                    and not p["failure_reasons"], "not_candidate mismatch")
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


def source_eligible(definition: dict, sources: dict, *,
                    trusted_source_registry_hash: str | None = None) -> bool:
    """Review status in caller-controlled JSON is not itself authorization."""
    # No caller-supplied value can change this separately reviewed allowlist.
    if (sources.get("registry_hash") not in PINNED_APPROVED_SOURCE_REGISTRY_HASHES
            or trusted_source_registry_hash not in (None, sources.get("registry_hash"))):
        return False
    try:
        verify_registry(sources)
    except (N3ValidationError, KeyError, TypeError):
        return False
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



def _verify_decision_reasons(plan: dict, evaluation: dict, definition: dict,
                             sources: dict, adapted: dict, proofs: dict,
                             *, relation_state: str, source_state: str,
                             verified_r1_incomplete: bool) -> None:
    """Derive reasons from verified facts, not from self-signed assertions.

    A re-sealed reason is still rejected when its independently recomputed
    predicate is false. In P1 unsupported reason codes are fail-closed, rather
    than trusted merely because a JSON enum and SHA256 permit them.
    """
    route = plan["trace"]["selected_decisive_route"]
    by_id = {h["rule_hit_id"]: h for h in adapted["hits"]}
    chosen = (proofs[route]["selected_binding_ids"] if route != "none" else [])
    chosen_hits = [by_id[rid] for rid in chosen]
    selected_axes = {h["axis"] for h in chosen_hits}
    from .synthesis import synthesize
    # Source signals were already re-matched from the original chart by adapter.
    native_report = {"signals": adapted["original_signals"],
                     "time_mode": adapted["time_mode"]}
    original_tensions = synthesize(None, native_report)["tensions"]
    real_tension = any(t["status"] == "unresolved" and t["axis"] in selected_axes
                       and t["positive_rule_ids"] and t["negative_rule_ids"]
                       for t in original_tensions)
    conflict_failed = evaluation["conflict_proof"]["status"] in ("fail", "unknown")
    time_failed = evaluation["time_proof"]["status"] in ("fail", "unknown")
    dependency_failed = evaluation["dependency_proof"]["status"] in ("fail", "unknown")
    uncertain_relevant = (adapted["time_mode"] != "known" and
                          any(h["raw_fields"]["provisional"] for h in chosen_hits))
    independent = definition["evidence_policy"]["independent_roots_required"]
    # Only *authenticated* candidate bindings (not caller text) count as
    # observed overlap. Never treat shared roots as two independent proofs.
    dependent_routes = set()
    if independent and dependency_failed:
        for route_name in ROUTES:
            origin = ("r1_witness" if route_name == "r1_path"
                      else "direct_composite_component")
            entries = [b for b in evaluation["bindings"] if b["origin"] == origin]
            for i, first in enumerate(entries):
                for second in entries[i + 1:]:
                    if (first["role"] != second["role"] and
                            set(first["dependency_roots"]) & set(second["dependency_roots"])):
                        dependent_routes.add(route_name)
    source_missing = not source_eligible(definition, sources)
    status = evaluation["source_license_check"]["status"]
    _assert(not (source_missing or source_state != "TRUE") or status != "pass",
            "REASON_MISMATCH: source check claims pass without a source")
    observed = {
        "NO_RELATION_SOURCE": lambda rr: (
            source_missing and rr in (route, "global") and route != "none"),
        "INCOMPLETE_SEARCH": lambda rr: (
            rr == "r1_path" and verified_r1_incomplete
            and proofs["r1_path"]["candidate_state"] == "candidate"
            and proofs["r1_path"]["search_complete"] is False
            and proofs["r1_path"]["proof_result"] == "unknown"),
        "MATERIAL_TENSION": lambda rr: (
            rr == route and real_tension and conflict_failed),
        "UNCERTAIN_TIME": lambda rr: (
            rr == route and uncertain_relevant and time_failed),
        "DEPENDENT_ROOTS": lambda rr: rr in dependent_routes,
        "UNMATCHED_CONDITIONS": lambda rr: (
            rr == route and route != "none" and
            (source_state != "TRUE" or relation_state != "TRUE")),
        "UNVERIFIED_RELATION": lambda rr: (
            rr == route and route != "none" and
            definition["relation_review"]["status"] != "approved_for_symbolic_wording"),
        "CANDIDATE_NOT_FOUND": lambda rr: (
            rr == "global" and route == "none" and
            all(p["candidate_state"] == "not_candidate" for p in proofs.values())
            and not verified_r1_incomplete),
        "PROOF_UNKNOWN": lambda rr: (
            rr == "r1_path" and verified_r1_incomplete),
        "RESOURCE_CAP": lambda rr: (
            rr == "r1_path" and verified_r1_incomplete),
    }
    for reason in plan["reasons"]:
        code, rr = reason["code"], reason["route"]
        _assert(code in observed and observed[code](rr),
                "REASON_MISMATCH: unsupported or unproved " + code)
        expected_blocking = (rr == route or rr == "global")
        _assert(reason["blocking"] is expected_blocking,
                "REASON_MISMATCH: blocking attribution for " + code)
        _assert(not reason["evidence_refs"] or
                set(reason["evidence_refs"]).issubset(by_id),
                "REASON_MISMATCH: invented reason evidence")
    if plan["decision"] == "COMPARISON_ONLY" and source_missing:
        _assert(any(r["code"] == "NO_RELATION_SOURCE" and r["blocking"]
                    and r["route"] == route for r in plan["reasons"]),
                "REASON_MISMATCH: comparison missing independently derived source gate")
    if verified_r1_incomplete and route != "r1_path":
        _assert(any(r["code"] == "INCOMPLETE_SEARCH" and
                    r["route"] == "r1_path" and not r["blocking"]
                    for r in plan["reasons"]),
                "REASON_MISMATCH: capped nondecisive R1 search omitted")


def verify_plan(plan: dict, evaluation: dict, definition: dict, sources: dict,
                *, claims: list[dict] = (), allow_user: bool = False,
                trusted_source_registry_hash: str | None = None,
                adapted: dict | None = None, n2_catalog: dict | None = None,
                verified_r1_incomplete: bool = False,
                relation_state: str | None = None,
                source_state: str | None = None) -> None:
    # Schema-first even for lower-level validation: no raw KeyError on missing fields.
    validate_schema("N3Plan", plan)
    validate_schema("RelationEvaluation", evaluation)
    _assert(adapted is not None and n2_catalog is not None,
            "UNVERIFIED_EVALUATION: source adapter and N2 catalog required")
    verify_evaluation(evaluation, definition, evaluation["snapshot_id"],
                      adapter_trace=adapted)
    verify_evidence_bindings(evaluation, adapted, definition=definition,
                             n2_catalog=n2_catalog)
    validate_schema("N3Plan", plan)
    proofs = verify_route_proofs(plan["route_proofs"])
    _assert(plan["route_proofs"] == evaluation["route_proofs"], "route proof differs from evaluation")
    _assert(plan["snapshot_id"] == evaluation["snapshot_id"] and
            plan["evaluation_id"] == evaluation["evaluation_id"] and
            plan["definition_id"] == definition["definition_id"], "plan reference mismatch")
    _assert(plan["plan_id"] == plan_id(plan), "BAD_ID: plan signature")
    verify_registry(sources)
    _assert(plan["trace"]["source_snapshot_hash"] == sources["registry_hash"],
            "PROVENANCE_MISMATCH: source trace hash")
    _assert(plan["trace"]["adapter_trace_hash"] == adapted["trace_digest"],
            "PROVENANCE_MISMATCH: adapter trace hash")
    selected_routes = [p for p in plan["route_proofs"] if p["proof_result"] == "proven"]
    actual_facts = {f for p in selected_routes for f in p["source_fact_refs"]}
    _assert(set(plan["trace"]["atomic_evidence_refs"]) == actual_facts,
            "PROVENANCE_MISMATCH: Plan atomic facts must equal proven route facts")
    _assert(plan["trace"]["evaluation_trace_hash"] == evaluation["trace_digest"],
            "PROVENANCE_MISMATCH: evaluation trace hash")
    matched_atoms = {b["rule_id"] for b in evaluation["bindings"]}
    _assert(set(plan["retained_atomic_rule_ids"]).issubset(matched_atoms),
            "invented retained atomic rule ID")
    _assert(not claims, "P1 has no approved relation claims")
    _assert(plan["reasons"] == sorted(plan["reasons"], key=lambda x: (
        ROUTES.index(x["route"]) if x["route"] in ROUTES else 2, not x["blocking"], x["code"])),
        "reason order inconsistent")
    _assert(len({(r["route"], r["code"]) for r in plan["reasons"]}) ==
            len(plan["reasons"]), "duplicate reason")
    route = plan["trace"]["selected_decisive_route"]
    decision = plan["decision"]
    reasons = plan["reasons"]
    blocking = [r for r in reasons if r["blocking"]]
    # Never evaluate meaning using an authenticated but *unselected* witness.
    expected_ids = (set(proofs[route]["selected_binding_ids"])
                    if route != "none" else set())
    _assert({b["rule_hit_id"] for b in evaluation["selected_witnesses"]} == expected_ids,
            "PROVENANCE_MISMATCH: semantic witnesses not in decisive proof")
    _assert(len(evaluation["selected_witnesses"]) == len(expected_ids),
            "PROVENANCE_MISMATCH: duplicated selected witness")
    if relation_state is None:
        relation_state = evaluate_bound_predicate(
            definition["predicate_ast"], definition, evaluation, adapted,
            complete=True, selected_binding_ids=expected_ids)
    if source_state is None:
        source_state = source_conditions_state(
            definition, evaluation, adapted, selected_binding_ids=expected_ids)
    _assert(relation_state in TRUTH and source_state in TRUTH,
            "invalid derived semantic status")
    _verify_decision_reasons(
        plan, evaluation, definition, sources, adapted, proofs,
        relation_state=relation_state, source_state=source_state,
        verified_r1_incomplete=verified_r1_incomplete)
    if route != "none":
        _assert(proofs[route]["candidate_state"] == "candidate", "decisive route not candidate")
        _assert(all(r["route"] in (route, "global") for r in blocking),
                "nondecisive route must not block")
    if blocking:
        decisive = [r for r in blocking if r["route"] in (route, "global")]
        _assert(decisive, "missing decisive blocking reason")
        ranked = ("INVALID_SCHEMA", "SNAPSHOT_MISMATCH", "PROVENANCE_MISMATCH",
                  "BAD_ID", "CONFLICTING_SOURCES", "REJECTED_SOURCE",
                  "UNCERTAIN_TIME", "INCOMPLETE_SEARCH", "PROOF_UNKNOWN",
                  "UNMATCHED_CONDITIONS", "MATERIAL_TENSION", "DEPENDENT_ROOTS",
                  "MISSING_READING", "MISSING_ATOM_MAPPING", "NO_RELATION_SOURCE",
                  "FRAMEWORK_ONLY", "EDITORIAL_ONLY", "UNVERIFIED_RELATION",
                  "SOURCE_SCOPE_EXCEEDED", "OPERATOR_EFFECT_MISMATCH",
                  "UNLICENSED_DELTA", "PARAPHRASE_ONLY", "RESOURCE_CAP", "CANDIDATE_NOT_FOUND")
        expected_primary = min(decisive, key=lambda r: ranked.index(r["code"]))["code"]
        _assert(plan["primary_reason"] == expected_primary,
                "primary_reason violates reason priority")
    if plan["primary_reason"] == "NONE":
        _assert(not blocking, "NONE with blocking reasons")
    else:
        _assert(any(r["code"] == plan["primary_reason"] and r["blocking"] and
                    (r["route"] == route or r["route"] == "global") for r in reasons),
                "primary_reason does not match decisive route")
    _assert(len(plan["retained_atomic_rule_ids"]) ==
            len(set(plan["retained_atomic_rule_ids"])), "duplicate atomic rule")
    if decision == "RELATION_LICENSED":
        _assert(source_eligible(definition, sources,
                trusted_source_registry_hash=trusted_source_registry_hash), "NO_RELATION_SOURCE")
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
                 *, plan: dict, allow_user: bool = False,
                 trusted_source_registry_hash: str | None = None) -> None:
    validate_schema("NarrativeClaim", claim)
    _assert(claim["claim_id"] == claim_id(claim), "BAD_ID: claim")
    _assert(claim["evaluation_id"] == evaluation["evaluation_id"], "claim evaluation mismatch")
    effects = {x["effect_id"]: x for x in definition["licensed_effects"]}
    _assert(claim["licensed_effect_id"] in effects, "unknown effect")
    chosen = effects[claim["licensed_effect_id"]]
    _assert(claim["derived_predicate"] == chosen, "invented or modified licensed effect")
    _assert(set(claim["source_anchor_refs"]) == set(chosen["source_anchor_ids"]),
            "claim source provenance differs from signed effect")
    _assert(plan["decision"] == "RELATION_LICENSED" and
            claim["claim_id"] in plan["relation_claim_ids"], "claim missing licensed plan")
    _assert(evaluation["source_license_check"]["status"] == "pass" and
            evaluation["novelty_check"]["status"] == "pass" and
            source_eligible(definition, sources,
                trusted_source_registry_hash=trusted_source_registry_hash),
            "unlicensed source or novelty")
    _assert(False, "P1_NO_LICENSED_CLAIM: zero externally approved positive gold")


# Explicit DAG check: a signature may never transitively depend on itself.
HASH_DEPENDENCIES = {
    "rulepack_digest": (), "n2_catalog_digest": (), "ontology_digest": (),
    "interface_versions": (), "term_registry_hash": (), "source_registry_hash": (),
    "compatible_upstream_hash": ("rulepack_digest", "n2_catalog_digest",
                                 "ontology_digest", "interface_versions"),
    "definition_hash": ("compatible_upstream_hash", "term_registry_hash",
                        "source_registry_hash"),
    "catalog_digest": ("definition_hash", "term_registry_hash", "source_registry_hash"),
    "snapshot_id": ("compatible_upstream_hash", "catalog_digest"),
    "evaluation_id": ("snapshot_id", "definition_hash"),
    "claim_id": ("evaluation_id",),
    "plan_id": ("evaluation_id", "claim_id"),
}


def verify_hash_dag(extra_dependencies: dict[str, tuple[str, ...]] | None = None) -> tuple[str, ...]:
    graph = {k: tuple(v) for k, v in HASH_DEPENDENCIES.items()}
    if extra_dependencies:
        for node, dependencies in extra_dependencies.items():
            _assert(node in graph, "unknown hash DAG node")
            graph[node] += tuple(dependencies)
    visiting, visited, order = set(), set(), []

    def visit(node):
        _assert(node in graph, "unknown hash DAG dependency")
        _assert(node not in visiting, "CYCLIC_SIGNATURE_GRAPH: " + node)
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)
        order.append(node)

    for node in graph:
        visit(node)
    return tuple(order)


def verify_evidence_bindings(evaluation: dict, adapted: dict, *,
                             n2_catalog: dict | None = None,
                             definition: dict | None = None) -> None:
    """Never admit invented witnesses, implicit root independence or route leakage.

    R1 may be incomplete while direct composite Route B is proven. Only selected
    witnesses from *that route* are checked for independence. Shared authoring
    groups are not sky facts; raw matching remains the identity authority.
    """
    from .n3_evidence import alternative_set_id
    from .n3_n2 import classify_rule

    original = {h["rule_hit_id"]: h for h in adapted["hits"]}
    role_allowed = ({p["role"]: set(p["allowed_rule_ids"])
                     for p in definition["participant_specs"]} if definition is not None else None)
    if definition is not None:
        _assert(evaluation["definition_id"] == definition["definition_id"],
                "evidence/definition mismatch")
    _assert(len(original) == len(adapted["hits"]), "duplicate adapted evidence")
    bindings = evaluation["bindings"]
    all_entries = bindings + evaluation["alternatives"]
    _assert(len({(b["role"], b["rule_hit_id"], b["origin"]) for b in all_entries})
            == len(all_entries), "duplicate evidence binding")
    groups: dict[tuple[str, str], set[str]] = {}
    for binding in all_entries:
        validate_schema("EvidenceBinding", binding)
        hit = original.get(binding["rule_hit_id"])
        _assert(hit is not None and not hit["modifier_only"], "invented or modifier RuleHit")
        for name in ("rule_id", "evidence_key", "fact_keys",
                     "dependency_roots", "witness_group_id"):
            _assert(binding[name] == hit[name], "PROVENANCE_MISMATCH: binding " + name)
        _assert(binding["rule_review_status"] == hit["review_status"] and
                binding["source_refs"] == hit["source_refs"],
                "PROVENANCE_MISMATCH: source status or URL of witness")
        _assert(role_allowed is None or
                binding["rule_id"] in role_allowed.get(binding["role"], set()),
                "ROLE_RULE_MISMATCH: evidence not permitted for role")
        if n2_catalog is not None:
            category = classify_rule(hit["rule_id"], n2_catalog)
            _assert(binding["content_category"] == category,
                    "N2 content category mismatch")
            _assert(category not in ("symbolic_explanation", "withheld_editorial_reading")
                    or binding["meaning_ref"] is None,
                    "non-behavioral N2 content cannot support semantic binding")
            if binding["meaning_ref"] is not None:
                _assert(category == "behavioral_rule_reading" and any(
                    x["id"] == binding["meaning_ref"] and x["rule_id"] == hit["rule_id"]
                    for x in n2_catalog["rule_readings"]), "invented N2 meaning reference")
        route = ("r1_path" if binding["origin"] == "r1_witness"
                 else "original_composite")
        groups.setdefault((route, binding["role"]), set()).add(hit["witness_group_id"])
    for binding in all_entries:
        route = "r1_path" if binding["origin"] == "r1_witness" else "original_composite"
        expected = alternative_set_id(snapshot_id=evaluation["snapshot_id"], route=route,
                        definition_id=evaluation["definition_id"], role=binding["role"],
                        witness_group_ids=sorted(groups[(route, binding["role"])]))
        _assert(binding["alternative_set_id"] == expected, "invented alternative set ID")
    selected_ids = {b["rule_hit_id"] for b in evaluation["selected_witnesses"]}
    by_id = {b["rule_hit_id"]: b for b in bindings}
    _assert(selected_ids.issubset(by_id), "selected witness outside bindings")
    _assert(all(b == by_id[b["rule_hit_id"]] for b in evaluation["selected_witnesses"]),
            "selected witness details differ from authenticated binding")
    proofs = verify_route_proofs(evaluation["route_proofs"])
    for route_name, proof in proofs.items():
        if proof["proof_result"] != "proven":
            continue
        chosen = [by_id.get(s) for s in proof["selected_binding_ids"]]
        expected_alternatives = {b["alternative_set_id"] for b in chosen if b is not None}
        _assert(set(proof["alternative_set_ids"]) == expected_alternatives,
                "proof alternative set IDs invented or incomplete")
        _assert(all(chosen), "proof contains non-existent binding")
        assert all(x is not None for x in chosen)
        origin = "r1_witness" if route_name == "r1_path" else "direct_composite_component"
        _assert(all(b["origin"] == origin for b in chosen), "cross-route witness leakage")
        roles = [b["role"] for b in chosen]
        _assert(len(roles) == len(set(roles)), "duplicate role as independent proof")
        roots: set[str] = set()
        fact_refs: set[str] = set()
        independent = (definition is None or
                       definition["evidence_policy"]["independent_roots_required"])
        for b in chosen:
            if independent:
                _assert(not roots.intersection(b["dependency_roots"]),
                        "DEPENDENT_ROOTS: overlapping proof observations")
            # When independent_roots_required=False we preserve overlap; it
            # cannot count as multiple independent observations for licensing.
            roots.update(b["dependency_roots"])
            fact_refs.update(b["fact_keys"])
        _assert(len(proof["source_fact_refs"]) == len(set(proof["source_fact_refs"])),
                "duplicate source facts in route proof")
        _assert(set(proof["source_fact_refs"]) == fact_refs,
                "invented, omitted or duplicate sky facts")
        if route_name == "original_composite":
            match = evaluation["original_composite_match"]
            _assert(match is not None and match["composite_is_independent_evidence"] is False,
                    "composite has no independent third fact")
            _assert(sorted(match["component_rule_hit_ids"]) ==
                    sorted(proof["selected_binding_ids"]), "composite component IDs differ")
            _assert(sorted(match["component_fact_keys"]) == sorted(fact_refs),
                    "composite facts differ from source RulePack")


def evaluate_bound_predicate(ast: dict, definition: dict, evaluation: dict,
                             adapted: dict, *, complete: bool = False,
                             selected_binding_ids: set[str] | None = None) -> str:
    """Interpret only authenticated RulePack facts bound to their approved role.

    Missing observations/term mappings are UNKNOWN, never automatically FALSE.
    Every source guard and relation predicate must independently resolve TRUE
    before a licensed meaning can be contemplated; no semantic equivalence AI.
    """
    allowed = {s["role"]: set(s["allowed_rule_ids"])
               for s in definition["participant_specs"]}
    if selected_binding_ids is None:
        proven = [p for p in evaluation["route_proofs"] if p["proof_result"] == "proven"]
        _assert(len(proven) <= 1,
                "PROVENANCE_MISMATCH: decisive route required for multiple proofs")
        selected_binding_ids = (set(proven[0]["selected_binding_ids"])
                                if proven else set())
    chosen = evaluation["selected_witnesses"]
    _assert({b["rule_hit_id"] for b in chosen} == selected_binding_ids and
            len(chosen) == len(selected_binding_ids),
            "PROVENANCE_MISMATCH: unselected semantic witness")
    by_role: dict[str, list[dict]] = {}
    original = {h["rule_hit_id"]: h for h in adapted["hits"]}
    for binding in chosen:
        _assert(binding["rule_id"] in allowed.get(binding["role"], set()),
                "ROLE_RULE_MISMATCH: selected witness not allowed")
        h = original.get(binding["rule_hit_id"])
        _assert(h is not None and h["rule_id"] == binding["rule_id"],
                "PROVENANCE_MISMATCH: predicate witness absent")
        by_role.setdefault(binding["role"], []).append(h)

    def resolve(node: dict) -> str:
        op = node["op"]
        if op == "no_blocking_tension":
            return "UNKNOWN"  # Requires independently verified material-tension closure.
        role = node["role"]
        matches = by_role.get(role, [])
        if not matches:
            return "UNKNOWN"
        if op == "atom_term_equals":
            return "UNKNOWN"  # No human-reviewed semantic term binding in P1.
        if op == "rule_hit_exact":
            return "TRUE" if any(h["rule_id"] == node["rule_id"] for h in matches) else "FALSE"
        if op == "placement_exact":
            target = "placement:" + node["body"] + ":" + node["sign"]
        elif op == "aspect_exact":
            target = "aspect:" + ":".join(sorted([node["body_a"], node["body_b"]])) + ":" + node["aspect_kind"]
        elif op == "house_exact":
            target = "house:" + node["body"] + ":" + str(node["house"])
        else:
            target = None
        if target is not None:
            return "TRUE" if any(target in h["fact_keys"] for h in matches) else "FALSE"
        if op == "polarity_exact":
            return "TRUE" if any(h["polarity"] == node["value"] for h in matches) else "FALSE"
        if op == "time_stable":
            # Only re-matched and stable facts are emitted by interpret_chart.
            return "TRUE" if matches and all(h["fact_keys"] for h in matches) else "UNKNOWN"
        raise N3ValidationError("unsupported predicate resolver operation " + op)

    return evaluate_predicate(ast, resolve, complete=complete)


def source_conditions_state(definition: dict, evaluation: dict, adapted: dict,
                            *, selected_binding_ids: set[str] | None = None) -> str:
    """Unknown or false source conditions never license an effect."""
    complete = any(p["proof_result"] == "proven" and p["search_complete"] is True
                   for p in evaluation["route_proofs"])
    states = [evaluate_bound_predicate(anchor["matching_conditions"], definition,
                                      evaluation, adapted, complete=complete,
                                      selected_binding_ids=selected_binding_ids)
              for anchor in definition["source_anchors"]]
    return "FALSE" if "FALSE" in states else "UNKNOWN" if "UNKNOWN" in states else "TRUE"
