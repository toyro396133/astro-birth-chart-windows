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

VERSION = "0.1.0-experimental"
MAX_CASES = 512
MAX_CANDIDATES = 4096
MAX_PROOF_STATES = 20000
MAX_AXES = 32


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


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
            if not all(isinstance(x, str) for x in fact["source_refs"] + fact["review_statuses"]):
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
    return {
        "id": entry["id"], "digest": _digest(r1), "axes": axes,
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
    seen = set()
    eligible, excluded, duplicates = [], [], []
    for case in sorted(parsed, key=lambda c: c["id"]):
        current = (case["profile_id"], case["rule_pack"])
        if profile is None:
            profile = current
        if current != profile:
            raise ValueError("mixed R1 profiles or rule packs are not comparable")
        if case["digest"] in seen:
            duplicates.append({"case_id": case["id"], "reason": "identical-R1-payload"})
            continue
        seen.add(case["digest"])
        if case["time_mode"] != "known" or case["blocked"]:
            excluded.append({
                "case_id": case["id"], "reason": (
                    "uncertain-birth-time" if case["time_mode"] != "known"
                    else "unresolved-tension-or-incomplete-proof"),
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
    return {
        "case_id": case["id"], "r1_digest": case["digest"],
        "time_mode": case["time_mode"],
        "node_ids": [fact["node_id"] for fact in witnesses],
        "selected_witnesses": witnesses,
        "rule_ids": sorted({x for w in witnesses for x in w["rule_ids"]}),
        "source_refs": sorted({x for w in witnesses for x in w["source_refs"]}),
        "source_review_statuses": sorted({
            x for w in witnesses for x in w["review_statuses"]}),
        "evidence_roots": sorted({x for w in witnesses for x in w["roots"]}),
    }


def _measure(members: tuple[str, ...], cases: list[dict],
             proof_cache: dict[tuple[str, tuple[str, ...]], tuple]) -> dict:
    support = []
    dependent = []
    partial = []
    incomplete = []
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
    return {
        "supports": support, "dependent_case_ids": dependent,
        "counterexamples": partial, "incomplete_proof_case_ids": incomplete,
    }


def _metrics(members: tuple[str, ...], cases: list[dict], measurement: dict) -> dict:
    n = len(cases)
    counts = [sum(axis in c["axes"] for c in cases) for axis in members]
    expected = math.prod(x / n for x in counts) if n else 0
    support = len(measurement["supports"])
    partial = len(measurement["counterexamples"])
    return {
        "independent_support_count": support,
        "partial_counterexample_count": partial,
        "dependent_cooccurrence_count": len(measurement["dependent_case_ids"]),
        "incomplete_proof_count": len(measurement["incomplete_proof_case_ids"]),
        "eligible_case_count": n,
        "member_observation_counts": dict(zip(members, counts)),
        "lift_over_independent_presence": round(
            support / n / expected, 6) if expected else 0.0,
        "coactivation_precision": round(
            support / (support + partial), 6) if support + partial else None,
    }


def _validation(members: tuple[str, ...], cases: list[dict],
                cache: dict) -> dict:
    measurement = _measure(members, cases, cache)
    metrics = _metrics(members, cases, measurement)
    count = metrics["independent_support_count"]
    counter = metrics["partial_counterexample_count"]
    return {
        "status": ("not-observed" if not (count or counter)
                   else "counterexamples-observed" if counter
                   else "no-counterexamples-observed"),
        "metrics": metrics,
        "support_cases": measurement["supports"],
        "counterexamples": measurement["counterexamples"],
        "dependent_case_ids": measurement["dependent_case_ids"],
        "incomplete_proof_case_ids": measurement["incomplete_proof_case_ids"],
    }


def discover(cases: list[dict], validation_cases: list[dict] | None = None, *,
             min_support: int = 3, min_lift: float = 1.25,
             min_precision: float = 0.65) -> dict:
    """Discover unsupported-by-R1 recurrent relationships with held-out checks.

    Each case is {"id": non-identifying identifier, "synthesis": R1 dict}.
    Training and validation cases must be disjoint. Does not change R1 results.
    Reported lift/precision describe *symbolic recurrence*, never person truth.
    """
    if (not isinstance(min_support, int) or isinstance(min_support, bool)
            or min_support < 2 or not 1 <= min_lift <= 100
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
    if {c["digest"] for c in train} & {c["digest"] for c in val}:
        raise ValueError("identical R1 report leaked into validation")

    known = {pattern for case in train + val for pattern in case["known"]}
    axes = sorted({axis for case in train for axis in case["axes"]})
    cache: dict[tuple[str, tuple[str, ...]], tuple] = {}
    vcache: dict[tuple[str, tuple[str, ...]], tuple] = {}
    accepted: dict[tuple[str, ...], dict] = {}
    frequent: set[tuple[str, ...]] = set()
    pending = [tuple(p) for p in combinations(axes, 2)]
    evaluated = 0
    truncated = False
    while pending:
        survivors = set()
        for members in sorted(pending):
            if evaluated >= MAX_CANDIDATES:
                truncated = True
                break
            evaluated += 1
            measurement = _measure(members, train, cache)
            metrics = _metrics(members, train, measurement)
            if metrics["independent_support_count"] < min_support:
                continue
            survivors.add(members)
            if members in known:
                continue
            if (metrics["lift_over_independent_presence"] < min_lift
                    or (metrics["coactivation_precision"] or 0) < min_precision
                    or metrics["incomplete_proof_count"]):
                continue
            candidate_id = "r2-" + _digest(
                [profile, list(members), VERSION])[:16]
            accepted[members] = {
                "id": candidate_id, "status": "hypothesis",
                "relation_type": (
                    "unreviewed-coactivation" if len(members) == 2
                    else "unreviewed-recurrent-conjunction"),
                "members": list(members), "level": len(members) - 2,
                "parent_hypothesis_ids": [],
                "novelty": "not-present-as-contiguous-R1-composition",
                "novelty_scope": "compared-to-observed-R1-results-only",
                "metrics": metrics,
                "support_cases": measurement["supports"],
                "counterexamples": measurement["counterexamples"],
                "dependent_case_ids": measurement["dependent_case_ids"],
                "source_refs": sorted({
                    src for p in measurement["supports"] for src in p["source_refs"]}),
                "rule_ids": sorted({
                    rid for p in measurement["supports"] for rid in p["rule_ids"]}),
                "source_review_statuses": sorted({
                    st for p in measurement["supports"]
                    for st in p["source_review_statuses"]}),
                "validation": (
                    _validation(members, val, vcache)
                    if validation_cases is not None else {"status": "not-run"}),
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
                if (len(candidate) == size + 1 and
                        all(tuple(s) in frequent for s in combinations(candidate, size))):
                    next_set.add(candidate)
        pending = sorted(next_set)

    for members, item in accepted.items():
        parents = [accepted[sub]["id"] for sub in combinations(members, len(members) - 1)
                   if sub in accepted]
        item["parent_hypothesis_ids"] = sorted(parents)

    hypotheses = sorted(accepted.values(), key=lambda h: (
        -len(h["members"]), -h["metrics"]["independent_support_count"], h["id"]))
    warnings = [
        "R2 hypotheses are symbolic corpus associations, not causal or scientific personality claims.",
        "Absent R1 axis means no matching symbolic witness, not absence of a trait.",
        "A new relation is novel only relative to the observed R1 output paths.",
        "Hypotheses never modify R1, the 96 source rules, or N1.",
    ]
    if excluded or val_excluded:
        warnings.append("Time uncertainty, conflicts and incomplete proof searches are excluded.")
    if duplicates or val_duplicates:
        warnings.append("Identical R1 payloads are deduplicated within each cohort.")
    if truncated:
        warnings.append("Candidate budget exhausted: hypothesis search was not exhaustive.")

    return {
        "schema_version": 1, "engine_version": VERSION,
        "profile_id": profile[0] if profile else None,
        "source_rule_pack": profile[1] if profile else None,
        "status": "experimental-hypotheses-only",
        "r1_unchanged": True, "learning_enabled_in_product": False,
        "hypotheses": hypotheses,
        "excluded_cases": excluded,
        "duplicate_cases": duplicates,
        "validation_excluded_cases": val_excluded,
        "validation_duplicate_cases": val_duplicates,
        "summary": {
            "train_input_cases": len(cases), "train_eligible_cases": len(train),
            "validation_input_cases": len(validation_cases or []),
            "validation_eligible_cases": len(val),
            "observed_r1_compositions": len(known),
            "candidate_patterns_tested": evaluated,
            "novel_hypotheses": len(hypotheses),
            "novel_pair_relations": sum(len(h["members"]) == 2 for h in hypotheses),
            "novel_higher_structures": sum(len(h["members"]) > 2 for h in hypotheses),
            "search_complete": not truncated,
        },
        "warnings": warnings,
    }
