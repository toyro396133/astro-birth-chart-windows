"""Read-only, provenance-preserving bridge from original RuleHit and R1 to N3.

Runs the *existing* matcher again as a parity oracle; never creates sky facts from
text or treats a composite modifier as a third independent observation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .interpretation import RulePack, _match, interpret_chart
from .n3_contracts import N3ValidationError, _assert, digest
from .synthesis import _roots

ADAPTER_VERSION = "EvidenceAdapterV1"
RAW_FIELDS = frozenset({
    "rule_id", "axis", "polarity", "weight", "text", "evidence",
    "source", "provisional", "review_status", "evidence_key",
    "source_url", "modifier_only",
})


@dataclass(frozen=True)
class AdaptedHit:
    rule_id: str
    rule_hit_id: str
    fact_identity_digest: str
    fact_keys: tuple[str, ...]
    dependency_roots: tuple[str, ...]
    witness_group_id: str
    evidence_key: str
    axis: str
    polarity: int
    modifier_only: bool


def chart_fingerprint(chart, report: dict, calculation_profile: str) -> str:
    """Digest calculated coordinates, mode and uncertainty without birth PII."""
    _assert(report.get("time_mode") in ("known", "estimated", "unknown"), "bad time mode")
    _assert(bool(calculation_profile), "missing calculation profile")
    bodies = [{
        "body": b.name, "sign": b.sign, "house": b.house,
        "longitude": round(b.longitude, 9),
        "signs_possible": sorted(b.signs_possible),
    } for b in sorted(chart.bodies, key=lambda b: b.name)]
    aspects = [{
        "pair": sorted([a.first, a.second]), "kind": a.kind,
        "orb": round(a.orb, 9),
    } for a in chart.aspects]
    return digest({"profile": calculation_profile, "time_mode": report["time_mode"],
                   "bodies": bodies, "aspects": sorted(aspects, key=lambda x: (
                       x["pair"], x["kind"], x["orb"]))})


def _fact_keys(rule: dict) -> tuple[str, ...]:
    when, kind = rule["when"], rule["type"]
    if kind == "placement":
        return ("placement:" + when["body"] + ":" + when["sign"],)
    if kind == "house":
        return ("house:" + when["body"] + ":" + str(when["house"]),)
    if kind == "aspect":
        return ("aspect:" + ":".join(sorted(when["pair"])) + ":" + when["kind"],)
    if kind == "composite":
        return tuple(sorted("placement:" + c["body"] + ":" + c["sign"] for c in when["all"]))
    raise N3ValidationError("unknown rule type")


def _matched_original(rule: dict, chart) -> tuple[str, str]:
    bodies = {body.name: body for body in chart.bodies}
    uncertain = chart.approximate or chart.time_certainty == "estimated"
    match = _match(rule, chart, bodies, uncertain)
    _assert(match is not None, "PROVENANCE_MISMATCH: unmatched rule " + rule["id"])
    return match[0], match[2]


def adapt_hits(chart, report: dict, pack: RulePack, raw_rulepack: dict,
               *, calculation_profile: str = "western-tropical-whole-sign-r1") -> dict:
    """Reject forged/omitted/reordered original signals and unstable evidence."""
    _assert(report.get("pack_version") == pack.version ==
            raw_rulepack.get("pack_version"), "PROVENANCE_MISMATCH: rulepack version")
    fresh = interpret_chart(chart, pack)
    _assert(report.get("signals") == fresh["signals"] and
            report.get("time_mode") == fresh["time_mode"] and
            report.get("time_uncertain") == fresh["time_uncertain"],
            "PROVENANCE_MISMATCH: original matcher differs")
    chart_id = chart_fingerprint(chart, report, calculation_profile)
    pack_id = digest(raw_rulepack)
    rules = {r["id"]: r for r in pack.rules}
    _assert(len(rules) == len(pack.rules), "duplicate rule ID")
    adapted: list[dict] = []
    seen = set()
    for raw in report["signals"]:
        _assert(set(raw) == RAW_FIELDS, "PROVENANCE_MISMATCH: raw RuleHit field set")
        rid = raw["rule_id"]
        _assert(rid in rules, "PROVENANCE_MISMATCH: unknown rule " + rid)
        rule = rules[rid]
        _assert(rid not in seen, "PROVENANCE_MISMATCH: duplicate raw RuleHit")
        seen.add(rid)
        evidence, legacy_fact = _matched_original(rule, chart)
        facts = _fact_keys(rule)
        _assert(raw["evidence"] == evidence, "PROVENANCE_MISMATCH: evidence text")
        _assert(raw["evidence_key"] == rule.get("evidence_group", legacy_fact),
                "PROVENANCE_MISMATCH: evidence key")
        _assert(raw["text"] == rule["text"] and raw["source"] == rule["source"] and
                raw["axis"] == rule["axis"] and raw["polarity"] == rule["polarity"] and
                raw["review_status"] == rule.get("review_status", "unverified") and
                raw["source_url"] == (rule.get("source_detail") or {}).get("url") and
                raw["modifier_only"] == (rule["type"] == "composite"),
                "PROVENANCE_MISMATCH: rule authoring fields")
        # Original matcher is authoritative for weight, provisional and stability.
        if rule["type"] == "composite":
            expected = "composite:" + "+".join(facts)
            _assert(legacy_fact == expected, "composite legacy key/components mismatch")
            _assert(len(facts) >= 2, "composite lacks two original facts")
            related = set(rule.get("related_rule_ids", []))
            component_rules = {r["id"] for r in pack.rules
                               if r["type"] == "placement" and
                               _fact_keys(r)[0] in facts}
            _assert(related == component_rules, "composite related rules mismatch")
            _assert(related.issubset(seen | {x["rule_id"] for x in report["signals"]}),
                    "composite missing original component RuleHits")
        identity = digest({
            "chart_fingerprint": chart_id, "rulepack_digest": pack_id,
            "rule_id": rid, "when_canonical": rule["when"],
            "fact_keys": list(facts), "time_mode": report["time_mode"],
        })
        hit_id = digest({"fact_identity_digest": identity, "raw_rule_hit_exact_fields": raw})
        adapted.append({
            "rule_id": rid, "rule_hit_id": hit_id,
            "fact_identity_digest": identity, "fact_keys": list(facts),
            "dependency_roots": sorted({root for key in facts for root in _roots(key)}),
            "evidence_key": raw["evidence_key"], "axis": raw["axis"],
            "polarity": raw["polarity"], "modifier_only": raw["modifier_only"],
            "raw_digest": digest(raw),
        })
    _assert(len({x["rule_hit_id"] for x in adapted}) == len(adapted),
            "duplicate rule hit content identity")
    # Membership changes MUST invalidate the witness group identity.
    groups: dict[tuple[str, int, str], list[dict]] = {}
    for h in adapted:
        if not h["modifier_only"]:
            groups.setdefault((h["axis"], h["polarity"], h["evidence_key"]), []).append(h)
    for (axis, polarity, key), members in groups.items():
        group_id = digest({"chart_fingerprint": chart_id, "axis": axis,
                           "polarity": polarity, "raw_evidence_key": key,
                           "sorted_rule_hit_ids": sorted(x["rule_hit_id"] for x in members)})
        for h in members:
            h["witness_group_id"] = group_id
    for h in adapted:
        if h["modifier_only"]:
            # Legacy composite RuleHit is editorial provenance; never independent witness.
            h["witness_group_id"] = None
    return {"chart_fingerprint": chart_id, "rulepack_digest": pack_id,
            "time_mode": report["time_mode"], "hits": adapted,
            "trace_digest": digest({"chart_fingerprint": chart_id,
                                    "rulepack_digest": pack_id,
                                    "hits": adapted})}


def alternative_set_id(*, snapshot_id: str, route: str, definition_id: str,
                       role: str, witness_group_ids: list[str]) -> str:
    _assert(route in ("r1_path", "original_composite"), "invalid route")
    _assert(len(witness_group_ids) == len(set(witness_group_ids)),
            "duplicate witness group alternative")
    return digest({"snapshot_id": snapshot_id, "route": route,
                   "definition_id": definition_id, "role": role,
                   "sorted_witness_group_ids": sorted(witness_group_ids)})


def map_r1_witnesses(r1_node: dict, adapted: dict) -> dict:
    """Require every selected R1 group to match original member provenance."""
    candidates: dict[str, list[dict]] = {}
    for h in adapted["hits"]:
        if not h["modifier_only"]:
            candidates.setdefault(h["evidence_key"], []).append(h)
    selected = r1_node.get("selected_witnesses_by_axis")
    _assert(isinstance(selected, dict), "R1 node lacks selected witnesses")
    results = {}
    for axis, witness in selected.items():
        key = witness["evidence_key"]
        members = [h for h in candidates.get(key, []) if h["axis"] == axis]
        _assert(members, "PROVENANCE_MISMATCH: R1 selected unknown evidence")
        _assert(sorted(set(h["rule_id"] for h in members)) == witness["rule_ids"],
                "PROVENANCE_MISMATCH: selected R1 members differ")
        roots = sorted({x for h in members for x in h["dependency_roots"]})
        _assert(roots == sorted(witness["roots"]), "PROVENANCE_MISMATCH: R1 roots")
        results[axis] = {"rule_hit_ids": sorted(h["rule_hit_id"] for h in members),
                         "witness_group_ids": sorted({h["witness_group_id"] for h in members}),
                         "dependency_roots": roots}
    proof_search = r1_node.get("proof_search", {})
    _assert(type(proof_search.get("complete")) is bool, "R1 proof incomplete metadata")
    return {"selected": results, "search_complete": proof_search["complete"],
            "visited": proof_search.get("states"), "cap": proof_search.get("limit"),
            "alternatives": r1_node.get("alternative_facts_by_axis", {})}


def match_composite(composite_rule_id: str, adapted: dict, raw_rulepack: dict) -> dict:
    """Direct independent Route B proof of exactly the original two placements."""
    rules = {r["id"]: r for r in raw_rulepack["rules"]}
    rule = rules.get(composite_rule_id)
    _assert(rule is not None and rule["type"] == "composite" and rule["enabled"],
            "unknown composite rule")
    hits = {h["rule_id"]: h for h in adapted["hits"]}
    _assert(composite_rule_id in hits, "composite not observed by original matcher")
    facts = _fact_keys(rule)
    related = rule["related_rule_ids"]
    _assert(len(related) == len(facts) and len(related) == len(set(related)),
            "composite duplicate/missing related IDs")
    selected = []
    for fact in facts:
        possibilities = [hits[r] for r in related
                         if r in hits and hits[r]["fact_keys"] == [fact] and
                         not hits[r]["modifier_only"]]
        _assert(len(possibilities) == 1, "composite missing/ambiguous component " + fact)
        selected.append(possibilities[0])
    _assert(len({x["rule_hit_id"] for x in selected}) == len(facts),
            "composite duplicates witness")
    return {
        "composite_rule_id": composite_rule_id,
        "exact_when_hash": digest(rule["when"]),
        "component_rule_hit_ids": sorted(x["rule_hit_id"] for x in selected),
        "component_fact_keys": list(facts),
        "component_dependency_roots": sorted({
            root for h in selected for root in h["dependency_roots"]}),
        "related_rule_ids": sorted(related),
        "rule_review_status": rule.get("review_status", "unverified"),
        "composite_is_independent_evidence": False,
    }
