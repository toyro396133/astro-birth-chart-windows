"""Experimental R2: mine *symbolic* coactivation, never modify R1 or N1.

Input is a set of versioned, structured R1 synthesize() results (no birth data).
R2 discovers recurrence *across independent reports*, not a new astrological
law, causal link, psychological fact, or approved interpretation rule.

The training/holdout boundary and evidence-root independence are explicit.
No dependencies, network, persistent learning, or mutation of R1 results.
"""
from __future__ import annotations

from hashlib import sha256
from itertools import combinations
import json
import math
from typing import Any

from .synthesis import FUNCTIONS, TRANSITIONS, MAX_NODES

REVIEW_STATUSES = frozenset({"unverified", "reviewed", "approved", "conflicting", "rejected"})

VERSION = "0.1.0-experimental"
MAX_CASES = 512
MAX_CANDIDATES = 4096
MAX_PROOF_STATES = 20000
MAX_AXES = 32


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _ontology() -> dict:
    """Enumerate every legal directed R1 path, even if absent from all charts."""
    paths = set()
    def extend(path: tuple[str, ...]) -> None:
        for next_axis in TRANSITIONS.get(path[-1], ()):
            if (next_axis not in FUNCTIONS or next_axis in path
                    or FUNCTIONS[next_axis][1] != FUNCTIONS[path[-1]][1]):
                continue
            target = path + (next_axis,)
            paths.add(target)
            extend(target)
    for axis in sorted(FUNCTIONS):
        extend((axis,))
    identity = _digest({
        "functions": FUNCTIONS, "transitions": TRANSITIONS,
        "domain_constraint": "same-domain-directed-no-repetition",
    })
    return {"identity": identity, "directed_paths": sorted(paths),
            "member_sets": {tuple(sorted(path)) for path in paths}}


def _fact_signature(f: dict) -> list:
    """Evidence identity, without editable captions, weights or case-local IDs."""
    return [f["axis"], f["evidence_key"], f["roots"], f["rule_ids"]]


def _support_signature(witnesses: list[dict]) -> str:
    return _digest(sorted((_fact_signature(w) for w in witnesses), key=lambda x: x[0]))


def _support_template(witnesses: list[dict]) -> str:
    """Broader observational template: rule identities and evidence kinds."""
    return _digest(sorted(
        ([w["axis"], w["rule_ids"], w["evidence_key"].split(":")[0]]
         for w in witnesses), key=lambda x: x[0]))


def _wilson(successes: int, total: int) -> list[float] | None:
    """Case-based descriptive 95% Wilson interval, not a chart-truth CI."""
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total))/den
    half = z * math.sqrt((p*(1-p) + z*z/(4*total))/total)/den
    return [round(max(0.0, center-half), 6),
            round(min(1.0, center+half), 6)]


def _nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item) for item in value)


def _parse(entry: dict) -> dict:
    """Validate the relevant R1 contract; fail closed on unreliable evidence."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
        raise ValueError("R2 requires a nonempty case id")
    r1 = entry.get("synthesis")
    if (not isinstance(r1, dict) or r1.get("schema_version") != 1
            or not isinstance(r1.get("profile_id"), str)
            or not r1["profile_id"] or not isinstance(r1.get("nodes"), list)):
        raise ValueError("R2 requires R1 synthesis schema 1")
    if r1.get("time_mode") not in ("known", "estimated", "unknown"):
        raise ValueError("R1 time_mode is required")
    if not isinstance(r1.get("source_rule_pack"), str):
        raise ValueError("R1 source_rule_pack is required")

    axes: dict[str, dict] = {}
    blocked = set()
    known = set()
    node_ids = set()
    for node in r1["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise ValueError("malformed R1 node")
        if node["id"] in node_ids:
            raise ValueError("duplicate R1 node ID")
        node_ids.add(node["id"])
        if node.get("type") == "synthesis":
            path = node.get("path")
            if not _nonempty_strings(path):
                raise ValueError("invalid R1 synthesis path")
            for size in range(2, len(path) + 1):
                for i in range(len(path) - size + 1):
                    known.add(tuple(sorted(path[i:i + size])))
        if node.get("type") != "axis":
            continue
        axis = node.get("axis")
        if not isinstance(axis, str) or not axis or axis in axes:
            raise ValueError("invalid or repeated R1 axis")
        if node.get("has_unresolved_tension") or node.get("counter_facts"):
            blocked.add(axis)
        if node.get("selection_search_limited"):
            blocked.add(axis)
            blocked.add("incomplete-R1-axis-selection")
        options = []
        seen_keys: dict[str, tuple[str, ...]] = {}
        facts = node.get("available_facts")
        if not isinstance(facts, list):
            raise ValueError("R1 axis must carry available_facts (R1-A01)")
        for fact in facts:
            if (not isinstance(fact, dict)
                    or not isinstance(fact.get("evidence_key"), str)
                    or not fact["evidence_key"]
                    or not _nonempty_strings(fact.get("roots"))
                    or not _nonempty_strings(fact.get("rule_ids"))
                    or not isinstance(fact.get("source_refs"), list)
                    or not isinstance(fact.get("review_statuses"), list)
                    or not isinstance(fact.get("weight"), (int, float))
                    or not math.isfinite(fact["weight"])
                    or fact["weight"] <= 0):
                raise ValueError("malformed R1 witness")
            if (not all(isinstance(x, str) and bool(x) for x in fact["source_refs"])
                    or not all(isinstance(x, str) and x in REVIEW_STATUSES
                               for x in fact["review_statuses"])):
                raise ValueError("malformed R1 witness source/status")
            roots = tuple(sorted(set(fact["roots"])))
            key = fact["evidence_key"]
            if key in seen_keys and roots != seen_keys[key]:
                raise ValueError("same evidence key has inconsistent roots")
            seen_keys[key] = roots
            if r1["time_mode"] == "unknown" and (
                    key.startswith(("house:", "aspect:"))
                    or any(root.startswith("angle:") for root in roots)):
                raise ValueError("unknown-time witness cannot use houses/aspects")
            options.append({
                "axis": axis, "node_id": node["id"], "evidence_key": key,
                "roots": list(roots), "weight": fact["weight"],
                "rule_ids": sorted(set(fact["rule_ids"])),
                "source_refs": sorted(set(fact["source_refs"])),
                "review_statuses": sorted(set(fact["review_statuses"])),
            })
        if not options:
            blocked.add(axis)
        axes[axis] = sorted(options, key=lambda f: (-f["weight"], f["evidence_key"]))

    if len(axes) > MAX_AXES:
        raise ValueError("R2 axis resource limit reached")
    tensions = r1.get("tensions", [])
    if not isinstance(tensions, list):
        raise ValueError("invalid R1 tensions")
    for t in tensions:
        if not isinstance(t, dict) or not isinstance(t.get("axis"), str):
            raise ValueError("invalid R1 tension")
        blocked.add(t["axis"])
    summary = r1.get("summary", {})
    if not isinstance(summary, dict):
        raise ValueError("invalid R1 summary")
    if summary.get("proof_search_limited_paths"):
        blocked.add("incomplete-R1-proof-search")
    if len(r1["nodes"]) >= MAX_NODES or any(
            "גבול משאבים" in w or "לא כל המסלולים נבדקו" in w
            for w in r1.get("warnings", []) if isinstance(w, str)):
        blocked.add("possible-R1-node-cap")
    source_id = entry.get("source_id")
    record_id = entry.get("independent_record_id")
    if source_id is not None and (not isinstance(source_id, str) or not source_id):
        raise ValueError("source_id must be nonempty string")
    if record_id is not None and (not isinstance(record_id, str) or not record_id):
        raise ValueError("independent_record_id must be nonempty string")
    evidence_identity = {
        "time_mode": r1["time_mode"], "axes": [
            [axis, sorted((_fact_signature(fact) for fact in facts),
                          key=lambda item: (item[1], item[2], item[3]))]
            for axis, facts in sorted(axes.items())],
        "blocked": sorted(blocked),
    }
    return {
        "id": entry["id"], "digest": _digest(r1),
        "evidence_digest": _digest(evidence_identity),
        "source_id": source_id, "independent_record_id": record_id,
        "axes": axes,
        "blocked": sorted(blocked), "known": known,
        "time_mode": r1["time_mode"], "tensions": tensions,
        "profile_id": r1["profile_id"], "rule_pack": r1["source_rule_pack"],
    }


def _prepare(items: list[dict], profile: tuple[str, str] | None = None
             ) -> tuple[list[dict], list[dict], list[dict], tuple[str, str] | None]:
    if not isinstance(items, list) or len(items) > MAX_CASES:
        raise ValueError("R2 requires a bounded list of cases")
    parsed = [_parse(item) for item in items]
    ids = [item["id"] for item in parsed]
    if len(ids) != len(set(ids)):
        raise ValueError("case ids must be unique")
    # Distinct documented subjects can have identical symbolic observations:
    # retain them as separate cases, but do NOT call them new evidence patterns.
    # Without an independent identity, identical *evidence* is a possible copy.
    seen_evidence: set[str] = set()
    seen_record_ids: set[tuple[str | None, str]] = set()
    eligible, excluded, duplicates = [], [], []
    for case in sorted(parsed, key=lambda c: c["id"]):
        current = (case["profile_id"], case["rule_pack"])
        if profile is None:
            profile = current
        if current != profile:
            raise ValueError("mixed R1 profiles or rule packs are not comparable")
        record = (case["source_id"], case["independent_record_id"])
        duplicate_record = (case["independent_record_id"] is not None
                            and record in seen_record_ids)
        duplicate_anonymous = (case["independent_record_id"] is None
                               and case["evidence_digest"] in seen_evidence)
        if duplicate_record or duplicate_anonymous:
            duplicates.append({
                "case_id": case["id"], "r1_digest": case["digest"],
                "evidence_digest": case["evidence_digest"],
                "reason": ("identical-declared-record" if duplicate_record
                           else "same-canonical-evidence-without-record-identity"),
            })
            continue
        seen_evidence.add(case["evidence_digest"])
        if case["independent_record_id"] is not None:
            seen_record_ids.add(record)
        if case["time_mode"] != "known" or case["blocked"]:
            excluded.append({
                "case_id": case["id"], "r1_digest": case["digest"],
                "evidence_digest": case["evidence_digest"],
                "reason": (
                    "uncertain-birth-time" if case["time_mode"] != "known"
                    else "unresolved-tension-or-incomplete-R1-proof"),
                "time_mode": case["time_mode"], "blocked_axes": case["blocked"],
                "tensions": case["tensions"],
            })
        else:
            eligible.append(case)
    return eligible, excluded, duplicates, profile


def _joint(case: dict, members: tuple[str, ...]) -> tuple[list[dict] | None, bool]:
    """Bounded, deterministic joint choice of one root-disjoint R1 witness/axis.

    Unlike relying on R1 independent_facts, all axis alternatives are searched.
    The result is valid only when a *complete* proof search was possible.
    """
    if any(axis not in case["axes"] for axis in members):
        return None, True
    ordered = sorted(members, key=lambda a: (len(case["axes"][a]), a))
    selected: dict[str, dict] = {}
    used: set[str] = set()
    best: list[dict] | None = None
    best_score: tuple[float, float] = (-1.0, -1.0)
    best_keys: tuple[str, ...] = ()
    states = 0
    complete = True

    def walk(i: int) -> None:
        nonlocal states, complete, best, best_score, best_keys
        if states >= MAX_PROOF_STATES:
            complete = False
            return
        states += 1
        if i == len(ordered):
            choices = [selected[a] for a in members]
            score = (min(f["weight"] for f in choices),
                     round(sum(f["weight"] for f in choices), 6))
            keys = tuple(f["evidence_key"] for f in choices)
            if score > best_score or score == best_score and keys < best_keys:
                best, best_score, best_keys = list(choices), score, keys
            return
        for fact in case["axes"][ordered[i]]:
            roots = set(fact["roots"])
            if not (used & roots):
                selected[ordered[i]] = fact
                used.update(roots)
                walk(i + 1)
                used.difference_update(roots)
                del selected[ordered[i]]
                if not complete:
                    return

    walk(0)
    return (best if complete else None), complete


def _proof(case: dict, witnesses: list[dict]) -> dict:
    sources = sorted({x for w in witnesses for x in w["source_refs"]})
    statuses = sorted({x for w in witnesses for x in w["review_statuses"]})
    missing = [w["axis"] for w in witnesses
               if not w["source_refs"] or not w["review_statuses"]]
    return {
        "case_id": case["id"], "r1_digest": case["digest"],
        "canonical_evidence_digest": case["evidence_digest"],
        "time_mode": case["time_mode"],
        "source_id": case["source_id"],
        "node_ids": [fact["node_id"] for fact in witnesses],
        "selected_witnesses": witnesses,
        "evidence_signature": _support_signature(witnesses),
        "data_template_signature": _support_template(witnesses),
        "rule_ids": sorted({x for w in witnesses for x in w["rule_ids"]}),
        "source_refs": sources, "source_review_statuses": statuses,
        "missing_provenance_axes": missing,
        "has_missing_or_unverified_source": (
            bool(missing) or "unverified" in statuses or "conflicting" in statuses),
        "evidence_roots": sorted({x for w in witnesses for x in w["roots"]}),
    }


def _measure(members: tuple[str, ...], cases: list[dict],
             proof_cache: dict[tuple[str, tuple[str, ...]], tuple]) -> dict:
    support, dependent, partial, incomplete, absent = [], [], [], [], []
    for case in cases:
        present = [axis for axis in members if axis in case["axes"]]
        if len(present) == len(members):
            key = (case["id"], members)
            if key not in proof_cache:
                proof_cache[key] = _joint(case, members)
            witnesses, complete = proof_cache[key]
            if not complete:
                incomplete.append(case["id"])
            elif witnesses is None:
                dependent.append(case["id"])
            else:
                support.append(_proof(case, witnesses))
        elif present:
            partial.append({
                "case_id": case["id"], "present_axes": present,
                "missing_axes": [x for x in members if x not in case["axes"]],
                "meaning": "missing-R1-coactivation-not-a-negative-personality-label",
            })
        else:
            absent.append(case["id"])
    return {
        "supports": support, "dependent_case_ids": dependent,
        "counterexamples": partial, "absent_case_ids": absent,
        "incomplete_proof_case_ids": incomplete,
    }


def _metrics(members: tuple[str, ...], cases: list[dict], measurement: dict,
             *, excluded_count: int = 0) -> dict:
    n = len(cases)
    counts = [sum(axis in c["axes"] for c in cases) for axis in members]
    expected = math.prod(x / n for x in counts) if n else 0
    proofs = measurement["supports"]
    support = len(proofs)
    partial = len(measurement["counterexamples"])
    denominator = support + partial
    signatures = {p["evidence_signature"] for p in proofs}
    templates = {p["data_template_signature"] for p in proofs}
    declared_sources = {p["source_id"] for p in proofs if p["source_id"]}
    return {
        "independent_support_count": support,
        "supporting_report_count": support,
        "distinct_evidence_signature_count": len(signatures),
        "distinct_data_template_count": len(templates),
        "declared_data_source_count": len(declared_sources),
        "source_independence_verified": False,
        "source_id_missing_report_count": sum(not p["source_id"] for p in proofs),
        "missing_provenance_report_count": sum(
            bool(p["missing_provenance_axes"]) for p in proofs),
        "unverified_provenance_report_count": sum(
            p["has_missing_or_unverified_source"] for p in proofs),
        "partial_counterexample_count": partial,
        "absent_case_count": len(measurement["absent_case_ids"]),
        "dependent_cooccurrence_count": len(measurement["dependent_case_ids"]),
        "incomplete_proof_count": len(measurement["incomplete_proof_case_ids"]),
        "excluded_case_count": excluded_count,
        "eligible_case_count": n,
        "member_observation_counts": dict(zip(members, counts)),
        "lift_over_independent_presence": round(
            support / n / expected, 6) if expected else 0.0,
        "symbolic_coactivation_ratio": (
            round(support / denominator, 6) if denominator else None),
        "symbolic_ratio_numerator": support,
        "symbolic_ratio_denominator": denominator,
        "symbolic_ratio_wilson_95_case_based": _wilson(support, denominator),
        "metric_scope": (
            "symbolic-case-frequencies-only; repeated patterns violate "
            "independent-case statistical assumptions"),
    }


def _validation(members: tuple[str, ...], cases: list[dict], cache: dict,
                training_signatures: set[str], min_ratio: float,
                excluded_count: int) -> dict:
    raw = _measure(members, cases, cache)
    # Identity of positive *selected witnesses* matters; mere different
    # full-chart documents/metadata do not make new support patterns.
    reused = [p for p in raw["supports"]
              if p["evidence_signature"] in training_signatures]
    novel = [p for p in raw["supports"]
             if p["evidence_signature"] not in training_signatures]
    valid = dict(raw, supports=novel)
    metrics = _metrics(members, cases, valid, excluded_count=excluded_count)
    # Reused support is NOT an absent observation, a counterexample, or
    # positive evidence of generalization. It has its own denominator.
    metrics["reused_training_signature_count"] = len(reused)
    ratio = metrics["symbolic_coactivation_ratio"]
    unique = metrics["distinct_evidence_signature_count"]
    if not cases or not novel:
        status = "generalization-unproven-no-novel-positive-signatures"
    elif (unique >= 2 and ratio is not None and ratio >= min_ratio
          and not raw["incomplete_proof_case_ids"]):
        status = "passes-prespecified-symbolic-holdout-gate"
    else:
        status = "fails-prespecified-symbolic-holdout-gate"
    return {
        "status": status, "metrics": metrics,
        "prespecified_gate": {
            "min_novel_holdout_signatures": 2,
            "min_symbolic_coactivation_ratio": min_ratio,
            "require_complete_proof": True,
        },
        "support_cases": novel, "reused_signature_cases": reused,
        "counterexamples": raw["counterexamples"],
        "absent_case_ids": raw["absent_case_ids"],
        "dependent_case_ids": raw["dependent_case_ids"],
        "incomplete_proof_case_ids": raw["incomplete_proof_case_ids"],
        "generalization_demonstrated": status.startswith("passes-"),
    }


def discover(cases: list[dict], validation_cases: list[dict] | None = None, *,
             min_support: int = 3, min_lift: float = 1.25,
             min_precision: float = 0.65, min_unique_signatures: int = 2) -> dict:
    """Induce symbolic coactivations, explicitly not semantic or causal relations.

    Supply *pre-split* cohorts, with fixed thresholds established prior to
    inspecting holdout. Case IDs and optional independent_record_id/source_id
    are metadata, not independently verified identities.
    """
    if (not isinstance(min_support, int) or isinstance(min_support, bool)
            or min_support < 2
            or not isinstance(min_unique_signatures, int)
            or isinstance(min_unique_signatures, bool)
            or min_unique_signatures < 2
            or not all(isinstance(v, (int, float)) and math.isfinite(v)
                       for v in (min_lift, min_precision))
            or not 1 <= min_lift <= 100
            or not 0 <= min_precision <= 1):
        raise ValueError("invalid R2 thresholds")
    train, excluded, duplicates, profile = _prepare(cases)
    val, val_excluded, val_duplicates, val_profile = _prepare(
        validation_cases if validation_cases is not None else [], profile)
    if profile is not None and val_profile is not None and profile != val_profile:
        raise ValueError("validation profile mismatch")
    training_ids = {c["id"] for c in train} | {
        c["case_id"] for c in excluded + duplicates}
    validation_ids = {c["id"] for c in val} | {
        c["case_id"] for c in val_excluded + val_duplicates}
    if training_ids & validation_ids:
        raise ValueError("training and validation case id leakage")
    training_fingerprints = {c["evidence_digest"] for c in train} | {
        x["evidence_digest"] for x in excluded + duplicates}
    validation_fingerprints = {c["evidence_digest"] for c in val} | {
        x["evidence_digest"] for x in val_excluded + val_duplicates}
    if training_fingerprints & validation_fingerprints:
        raise ValueError("identical canonical R1 evidence leaked into validation")
    if {c["digest"] for c in train} & {c["digest"] for c in val}:
        raise ValueError("identical R1 report leaked into validation")

    ontology = _ontology()
    observed = {path for c in train for path in c["known"]}
    known_paths = ontology["member_sets"]
    axes = sorted({axis for c in train for axis in c["axes"]})
    cache: dict[tuple[str, tuple[str, ...]], tuple] = {}
    vcache: dict[tuple[str, tuple[str, ...]], tuple] = {}
    accepted: dict[tuple[str, ...], dict] = {}
    frequent: set[tuple[str, ...]] = set()
    predefined, recurrent_only, affected = [], [], []
    validation_affected = []
    pending_unexamined = 0
    pending = [tuple(p) for p in combinations(axes, 2)]
    evaluated, truncated = 0, False
    while pending:
        survivors = set()
        for index, members in enumerate(sorted(pending)):
            if evaluated >= MAX_CANDIDATES:
                truncated = True
                pending_unexamined = len(pending) - index
                break
            evaluated += 1
            measure = _measure(members, train, cache)
            metrics = _metrics(members, train, measure,
                               excluded_count=len(excluded))
            if measure["incomplete_proof_case_ids"]:
                affected.append({
                    "members": list(members),
                    "case_ids": measure["incomplete_proof_case_ids"],
                    "reason": "R2-witness-search-capped",
                })
            if metrics["independent_support_count"] < min_support:
                continue
            # Frequent-set extension is based on observed support, even when
            # the combination is authored or fails a conservative R2 gate.
            survivors.add(members)
            classification = ("observed-r1-path" if members in observed
                              else "authored-r1-path-not-observed"
                              if members in known_paths
                              else "not-derivable-as-directed-r1-path")
            if classification != "not-derivable-as-directed-r1-path":
                predefined.append({"members": list(members),
                                   "classification": classification,
                                   "metrics": metrics})
                continue
            if (metrics["distinct_evidence_signature_count"] < min_unique_signatures
                    or metrics["distinct_data_template_count"] < 2):
                recurrent_only.append({
                    "members": list(members), "metrics": metrics,
                    "reason": "insufficient-distinct-evidence-patterns",
                    "classification": classification,
                })
                continue
            if (metrics["lift_over_independent_presence"] < min_lift
                    or (metrics["symbolic_coactivation_ratio"] or 0) < min_precision
                    or metrics["incomplete_proof_count"]):
                continue
            candidate_id = "r2-" + _digest([
                profile, ontology["identity"], list(members), VERSION])[:16]
            training_signatures = {
                p["evidence_signature"] for p in measure["supports"]}
            source_statuses = sorted({
                st for p in measure["supports"]
                for st in p["source_review_statuses"]})
            heldout = (_validation(members, val, vcache, training_signatures,
                                   min_precision, len(val_excluded))
                       if validation_cases is not None else {
                           "status": "not-run",
                           "generalization_demonstrated": False})
            if heldout.get("incomplete_proof_case_ids"):
                validation_affected.append({
                    "members": list(members),
                    "case_ids": heldout["incomplete_proof_case_ids"],
                    "reason": "R2-holdout-witness-search-capped",
                })
            accepted[members] = {
                "id": candidate_id, "status": "hypothesis",
                "relation_type": (
                    "unreviewed-coactivation" if len(members) == 2
                    else "unreviewed-recurrent-conjunction"),
                "semantic_relation_discovered": False,
                "conceptual_generalization_demonstrated": False,
                "members": list(members), "level": len(members) - 2,
                "parent_hypothesis_ids": [],
                "novelty": classification,
                "novelty_scope": "all-directed-R1-ontology-paths",
                "metrics": metrics,
                "support_cases": measure["supports"],
                "counterexamples": measure["counterexamples"],
                "absent_case_ids": measure["absent_case_ids"],
                "dependent_case_ids": measure["dependent_case_ids"],
                "source_refs": sorted({
                    src for p in measure["supports"] for src in p["source_refs"]}),
                "rule_ids": sorted({
                    rid for p in measure["supports"] for rid in p["rule_ids"]}),
                "source_review_statuses": source_statuses,
                "provenance_quality": {
                    "missing_sources_or_statuses": (
                        metrics["missing_provenance_report_count"]),
                    "unverified_or_conflicting_reports": (
                        metrics["unverified_provenance_report_count"]),
                    "all_supporting_reports_unverified_or_missing": (
                        metrics["unverified_provenance_report_count"]
                        == metrics["independent_support_count"]),
                    "any_source_approved_automatically": False,
                },
                "validation": heldout,
                "approved_for_r1": False,
            }
        if truncated or not survivors:
            break
        frequent |= survivors
        size = len(next(iter(survivors)))
        next_set = set()
        for base in sorted(survivors):
            for axis in axes:
                if axis in base:
                    continue
                candidate = tuple(sorted((*base, axis)))
                if (len(candidate) == size + 1
                        and all(tuple(s) in frequent
                                for s in combinations(candidate, size))):
                    next_set.add(candidate)
        pending = sorted(next_set)

    for members, item in accepted.items():
        item["parent_hypothesis_ids"] = sorted(
            accepted[sub]["id"]
            for sub in combinations(members, len(members) - 1)
            if sub in accepted)
    hypotheses = sorted(accepted.values(), key=lambda h: (
        -len(h["members"]), -h["metrics"]["independent_support_count"], h["id"]))
    candidate_complete = not truncated
    witness_complete = not affected and not validation_affected
    r1_input_complete = not any(
        any("R1" in str(b) or "cap" in str(b) or "proof" in str(b)
            for b in e["blocked_axes"]) for e in excluded + val_excluded)
    warnings = [
        "Level 1 only: recurring symbolic feature sets, not learned semantic relations.",
        "Novelty is classified against ALL directed R1 paths and domain restrictions.",
        "Case counts, evidence signatures and rule templates must not be confused.",
        "Source status is preserved; no source or hypothesis is promoted automatically.",
        "The case-based Wilson interval assumes independence and is not validated here.",
        "The held-out gate must use genuinely unseen evidence signatures.",
        "Hypotheses never alter R1, its source rules, N1 or the user-facing UI.",
    ]
    if excluded or val_excluded:
        warnings.append("Time uncertainty, tensions or incomplete R1 search excluded cases.")
    if duplicates or val_duplicates:
        warnings.append("Canonical evidence duplicates without record identity were excluded.")
    if any(h["provenance_quality"]["all_supporting_reports_unverified_or_missing"]
           for h in hypotheses):
        warnings.append("Some hypotheses rely entirely on unverified/missing source evidence.")
    if truncated or not witness_complete or not r1_input_complete:
        warnings.append("Search was incomplete: missing evidence is NOT a negative result.")
    return {
        "schema_version": 1, "engine_version": VERSION,
        "profile_id": profile[0] if profile else None,
        "source_rule_pack": profile[1] if profile else None,
        "ontology_identity": ontology["identity"],
        "ontology_directed_path_count": len(ontology["directed_paths"]),
        "status": "experimental-symbolic-patterns-only",
        "r1_unchanged": True, "learning_enabled_in_product": False,
        "hypotheses": hypotheses,
        "predefined_r1_patterns": sorted(
            predefined, key=lambda x: (x["members"], x["classification"])),
        "recurring_but_not_diverse_patterns": sorted(
            recurrent_only, key=lambda x: x["members"]),
        "excluded_cases": excluded, "duplicate_cases": duplicates,
        "validation_excluded_cases": val_excluded,
        "validation_duplicate_cases": val_duplicates,
        "search": {
            "candidate_enumeration_complete": candidate_complete,
            "witness_proof_search_complete": witness_complete,
            "r1_input_search_complete": r1_input_complete,
            "resource_affected_candidates": affected + validation_affected,
            "candidate_enumeration_unexamined_pending": pending_unexamined,
            "r1_resource_excluded_case_ids": [
                e["case_id"] for e in excluded + val_excluded
                if any("R1" in b or "cap" in b or "proof" in b
                       for b in e["blocked_axes"])],
        },
        "frozen_thresholds": {
            "min_support": min_support, "min_lift": min_lift,
            "min_symbolic_ratio": min_precision,
            "min_distinct_evidence_signatures": min_unique_signatures,
            "min_distinct_data_templates": 2,
        },
        "summary": {
            "train_input_cases": len(cases), "train_eligible_cases": len(train),
            "validation_input_cases": len(validation_cases or []),
            "validation_eligible_cases": len(val),
            "train_excluded_count": len(excluded),
            "train_canonical_duplicate_count": len(duplicates),
            "observed_r1_compositions": len(observed),
            "possible_r1_directed_compositions": len(ontology["directed_paths"]),
            "predefined_r1_pattern_count": len(predefined),
            "recurrent_insufficient_diversity_count": len(recurrent_only),
            "candidate_patterns_tested": evaluated,
            "novel_hypotheses": len(hypotheses),
            "novel_pair_relations": sum(len(h["members"]) == 2 for h in hypotheses),
            "novel_higher_structures": sum(len(h["members"]) > 2 for h in hypotheses),
            "candidate_enumeration_complete": candidate_complete,
            "witness_proof_search_complete": witness_complete,
            "r1_input_search_complete": r1_input_complete,
            "search_complete": (candidate_complete and witness_complete
                                and r1_input_complete),
            "level_1_symbolic_patterns_observed": bool(hypotheses or recurrent_only),
            "level_2_semantic_relations_demonstrated": False,
            "level_3_conceptual_generalization_demonstrated": False,
        },
        "warnings": warnings,
    }
