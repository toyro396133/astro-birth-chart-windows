"""Evidence-conditioned N2 semantic graph; no changes to R1 or original rules.

R1 selects independent evidence. N2 validates its complete original RuleHit
witness groups, then attaches *unverified* editorial meanings ONLY to exact
existing rule texts. Unknown rules do not license a fabricated example.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from pathlib import Path

from .narrative import _supported_process
from .semantic_plan_n2 import build_process_content_plan

N2_SEMANTIC_VERSION = "0.2.0"
CATALOG_FILE = "meaning_catalog_n2.json"
MAX_PRIMARY = 3
MAX_SECONDARY = 2
MAX_PROCESSES = 2
MAX_READINGS_PER_AXIS = 3
VALID_STATUSES = {"unverified", "reviewed", "approved", "conflicting", "rejected"}


def _distinct(values) -> list[str]:
    return sorted({v for v in values if isinstance(v, str) and v})


def _strip_degrees(text: str) -> str:
    # Suppress irrelevant numeric noise in presentation; keep unmodified evidence.
    return re.sub(r"\s*\(\d+(?:\.\d+)?°\)", "", text)


def load_meaning_catalog(path: Path | None = None) -> dict:
    source = path or Path(__file__).with_name(CATALOG_FILE)
    data = json.loads(source.read_text(encoding="utf-8"))
    from .synthesis import FUNCTIONS
    from .interpretation import load_rulepack
    entries = data.get("entries", [])
    readings = data.get("rule_readings", [])
    if (data.get("schema_version") != 1 or not isinstance(entries, list)
            or not isinstance(readings, list)
            or len(entries) != len(FUNCTIONS)
            or {e.get("axis") for e in entries} != set(FUNCTIONS)
            or len({e.get("id") for e in entries}) != len(entries)):
        raise ValueError("מאגר משמעות N2 אינו מכסה את צירי R1")
    for e in entries:
        if (e.get("kind") != "axis_meaning" or
                any(not isinstance(e.get(k), str) or not e[k].strip()
                    for k in ("id", "axis", "definition", "strength", "challenge"))
                or e.get("provenance", {}).get("review_status") != "unverified"
                or e.get("provenance", {}).get("astrological_rule") is not False):
            raise ValueError("ציר משמעות N2 אינו תקין")
    original = {r["id"]: r for r in load_rulepack().rules}
    if len({r.get("rule_id") for r in readings}) != len(readings):
        raise ValueError("קיימות משמעויות כפולות לאותו כלל")
    for e in readings:
        rule = original.get(e.get("rule_id"))
        if (not rule or e.get("kind") != "rule_reading"
                or rule["text"] != e.get("source_rule_text")
                or rule["axis"] != e.get("axis")
                or rule["type"] != e.get("evidence_type")
                or e.get("eligible_polarity") != 1
                or any(not isinstance(e.get(k), str) or not e[k].strip()
                       for k in ("id", "focus", "setting", "behavior", "distinction", "limit"))
                or e.get("provenance", {}).get("review_status") != "unverified"
                or e.get("provenance", {}).get("astrological_rule") is not False):
            raise ValueError("פירוש עריכתי אינו תואם את נוסח הכלל המקורי")
    return data


def _provenance(groups: list[dict]) -> dict:
    return {
        "rule_ids": _distinct(r for g in groups for r in g.get("rule_ids", [])),
        "source_refs": _distinct(r for g in groups for r in g.get("source_refs", [])),
        "source_review_statuses": _distinct(
            s for g in groups for s in g.get("review_statuses", [])),
        "evidence_keys": _distinct(g.get("evidence_key") for g in groups),
        "evidence_roots": _distinct(r for g in groups for r in g.get("roots", [])),
    }


def _verified_groups(node: dict, field: str = "independent_facts") -> list[dict]:
    groups = node.get(field)
    if not isinstance(groups, list) or not groups:
        return []
    for g in groups:
        if (not isinstance(g, dict) or not g.get("rule_ids")
                or not isinstance(g.get("rule_ids"), list)
                or not g.get("evidence_key") or not g.get("roots")
                or not isinstance(g.get("review_statuses"), list)
                or not isinstance(g.get("source_refs"), list)):
            return []
    proof = _provenance(groups)
    if field == "independent_facts" and (
            proof["rule_ids"] != _distinct(node.get("rule_ids", []))
            or proof["source_refs"] != _distinct(node.get("source_refs", []))
            or proof["source_review_statuses"] != _distinct(
                node.get("source_review_statuses", []))):
        return []
    return groups


def _matching_hits(axis: str, group: dict, signals: list[dict],
                   polarity: int, time_mode: str, rule_types: dict) -> list[dict]:
    """Verify ALL hits in a grouped R1 witness, not merely ID/key membership.

    Mismatched source URL, status, evidence detail, or original RuleHit text
    causes fail-closed omission. Grouped equal evidence may contain several hits.
    """
    matches = [h for h in signals
               if h.get("axis") == axis and h.get("polarity") == polarity
               and h.get("evidence_key") == group.get("evidence_key")
               and not h.get("modifier_only") and h.get("weight", 0) > 0]
    matches.sort(key=lambda h: (-h["weight"], h["rule_id"]))
    if not matches or any(
            not isinstance(h.get("rule_id"), str)
            or not isinstance(h.get("text"), str) or not h["text"].strip()
            or not isinstance(h.get("evidence"), str) or not h["evidence"]
            or h.get("review_status") not in VALID_STATUSES
            or h.get("provisional") != (time_mode != "known")
            or (time_mode != "known"
                and rule_types.get(h["rule_id"]) in ("house", "aspect"))
            for h in matches):
        return []
    # For built-in rules, also demand the original catalog wording/status/source.
    # Custom overlay IDs may appear in R1, but never gain a curated N2 reading.
    from .interpretation import load_rulepack
    canonical = {r["id"]: r for r in load_rulepack().rules}
    for h in matches:
        rule = canonical.get(h["rule_id"])
        if rule is not None and (
                h["text"] != rule["text"]
                or h["review_status"] != rule.get("review_status", "unverified")
                or h.get("source_url") != (rule.get("source_detail") or {}).get("url")
                or h.get("source") != rule["source"]
                or h["polarity"] != rule["polarity"]):
            return []
    if (group.get("rule_ids") != _distinct(h["rule_id"] for h in matches)
            or group.get("source_refs") != _distinct(
                h.get("source_url") for h in matches)
            or group.get("review_statuses") != _distinct(
                h["review_status"] for h in matches)
            or sorted(group.get("details", [])) != sorted(h["evidence"] for h in matches)):
        return []
    return matches


def _all_witnesses(node: dict, field: str, polarity: int,
                   signals: list[dict], time_mode: str, rule_types: dict) -> list:
    groups = _verified_groups(node, field)
    if not groups:
        return []
    validated = []
    for g in groups:
        hits = _matching_hits(node["axis"], g, signals, polarity, time_mode, rule_types)
        if not hits:
            return []
        validated.append((g, hits))
    return validated


def _key(node: dict, kind: str, suffix: str = "") -> str:
    return "n2-" + sha256("|".join((node["id"], kind, suffix))
                           .encode("utf-8")).hexdigest()[:15]


def _claim(node: dict, kind: str, classification: str, content: dict,
           *, groups: list[dict] | None = None, meaning_ids: list[str] | None = None,
           suffix: str = "", polarity: dict | None = None,
           audit_status: str | None = None) -> dict:
    proof = _provenance(groups if groups is not None else _verified_groups(node))
    claim = {
        "id": _key(node, kind, suffix),
        "kind": kind, "classification": classification, "axis": node.get("axis"),
        "content": content, "node_ids": [node["id"]],
        "rule_ids": proof["rule_ids"], "source_refs": proof["source_refs"],
        "source_review_statuses": proof["source_review_statuses"],
        "evidence_keys": proof["evidence_keys"],
        "evidence_roots": proof["evidence_roots"],
        "meaning_ids": list(meaning_ids or []),
        "audit_status": audit_status or node.get("audit_status", "symbolic-input"),
        "provisional_time": bool(node.get("provisional_time")),
        "limitations": ["symbolic-not-psychological-diagnosis"] +
            ([] if classification == "existing_rule" else ["editorial-not-source-approved"]) +
            (["r1-transition-is-hypothesis"] if classification == "synthesis_hypothesis" else []),
    }
    if polarity is not None:
        claim["evidence_by_polarity"] = polarity
    return claim


def _witness_summary(hit: dict, reading: dict | None, rule_types: dict) -> dict:
    return {
        "rule_id": hit["rule_id"], "type": rule_types.get(hit["rule_id"], "unknown"),
        "evidence_key": hit["evidence_key"],
        "evidence": _strip_degrees(hit["evidence"]),
        "raw_evidence": hit["evidence"],
        "text": hit["text"],
        "source_url": hit.get("source_url"),
        "review_status": hit["review_status"],
        "meaning_id": reading["id"] if reading else None,
        "focus": reading["focus"] if reading else None,
        "distinction": reading["distinction"] if reading else None,
        "limitation": reading["limit"] if reading else None,
        "setting": reading["setting"] if reading else None,
        "behavior": reading["behavior"] if reading else None,
    }


def _axis_claims(node: dict, axis_entry: dict, interpretation: dict,
                 readings: dict, rule_types: dict) -> list[dict]:
    if node.get("type") != "axis" or node.get("has_unresolved_tension"):
        return []
    groups = _all_witnesses(node, "independent_facts", 1,
                            interpretation["signals"], interpretation["time_mode"],
                            rule_types)
    if not groups:
        return []
    # All selected R1 evidence groups are validated before any claim is emitted.
    claims = [_claim(node, "axis-meaning", "editorial_extension", {
        "axis": node["axis"], "definition": axis_entry["definition"],
        "strength": axis_entry["strength"], "challenge": axis_entry["challenge"],
        "independent_evidence_count": len(groups),
        "rule_conditioned_coverage": 0,
    }, meaning_ids=[axis_entry["id"]])]
    curated = 0
    for g, hits in groups:
        hit = hits[0]  # strongest validated RuleHit per independent witness
        reading = readings.get(hit["rule_id"])
        direct = _claim(node, "rule-anchor", "existing_rule", {
            "rule_text": hit["text"],
            "chart_evidence": _strip_degrees(hit["evidence"]),
            "raw_chart_evidence": hit["evidence"],
            "selected_rule_id": hit["rule_id"],
            "evidence_type": rule_types.get(hit["rule_id"], "unknown"),
            "review_status": hit["review_status"],
            "selected_source_url": hit.get("source_url"),
            "selected_source": hit["source"],
            "witness_group_rule_ids": list(g["rule_ids"]),
        }, groups=[g], suffix=g["evidence_key"])
        claims.append(direct)
        if reading and curated < MAX_READINGS_PER_AXIS:
            claims.append(_claim(node, "axis-example", "possible_behavior_example", {
                "focus": reading["focus"], "situation": reading["setting"],
                "behavior": reading["behavior"],
                "distinction": reading["distinction"],
                "limit": reading["limit"],
                "selected_rule_id": hit["rule_id"],
                "evidence_type": reading["evidence_type"],
                "editorial_review_status": "unverified",
            }, groups=[g], meaning_ids=[reading["id"]],
               suffix=g["evidence_key"]))
            curated += 1
    claims[0]["content"]["rule_conditioned_coverage"] = curated
    return claims


def _process_claims(node: dict, axis_nodes: dict, readings: dict,
                    signals: list[dict], time_mode: str, rule_types: dict) -> list[dict]:
    if not _supported_process(node) or not _verified_groups(node):
        return []
    path = node["path"]
    selected = node.get("selected_witnesses_by_axis", {})
    if (set(selected) != set(path) or
            any(a not in axis_nodes or axis_nodes[a].get("has_unresolved_tension")
                or axis_nodes[a].get("domain") != node.get("domain") for a in path) or
            any(selected[a] != fact for a, fact in zip(path, node["independent_facts"]))):
        return []
    slots, meanings = [], []
    for axis in path:
        group = selected[axis]
        # A valid R1 path may select an alternative from available_facts,
        # not the axis's preferred independent_facts. Verify the exact
        # path-selected group against that R1 candidate list and RuleHits.
        available = axis_nodes[axis].get("available_facts", [])
        if group not in available:
            return []
        matched = _matching_hits(axis, group, signals, 1, time_mode, rule_types)
        if not matched:
            return []
        primary = matched[0]
        reading = readings.get(primary["rule_id"])
        slots.append({"axis": axis,
                      "witness": _witness_summary(primary, reading, rule_types),
                      "witness_group": group})
        if reading:
            meanings.append(reading["id"])
    content_plan = build_process_content_plan(
        list(path), slots, node["domain"], node.get("relation"),
        node.get("proof_search", {}).get("complete", True))
    base = _claim(node, "process-reading", "synthesis_hypothesis", {
        "path": list(path), "domain": node["domain"], "slots": slots,
        "model_relation": node.get("relation"),
        "proof_search_complete": node.get("proof_search", {}).get("complete", True),
        "content_plan": content_plan,
    }, meaning_ids=meanings, audit_status="hypothesis")
    # No "whole-path" claim may silently drop the first, middle or last
    # member. Comparison always carries full path coverage and missing slots.
    if not content_plan["comparison_is_supported"]:
        return [base]
    components = [{
        "axis": m["axis"], "position": m["position"],
        "focus": m["documented_meaning"]["focus"],
        "setting": m["documented_meaning"]["setting"],
        "behavior": m["documented_meaning"]["behavior"],
        "distinction": m["documented_meaning"]["distinction"],
        "limit": m["documented_meaning"]["limit"],
        "rule_id": m["selected_rule_id"],
    } for m in content_plan["members"] if m["meaning_covered"]]
    comparison = _claim(node, "process-example", "possible_behavior_example", {
        "path": list(path), "domain": node["domain"],
        "reading_type": "attributed-comparison-not-new-edge",
        "components": components, "content_plan": content_plan,
        "limitation": "Comparison only; no causal, joint-behavior or "
                      "psychological link is established.",
    }, meaning_ids=meanings, audit_status="hypothesis")
    return [base, comparison]


def _tension_claim(tension: dict, axis_nodes: dict, interpretation: dict,
                   rule_types: dict) -> dict | None:
    axis = tension["axis"]
    node = axis_nodes.get(axis)
    if node is None:
        return None
    signals = interpretation["signals"]
    positive = _all_witnesses(node, "independent_facts", 1, signals,
                              interpretation["time_mode"], rule_types)
    negative = _all_witnesses(node, "counter_facts", -1, signals,
                              interpretation["time_mode"], rule_types)
    if not positive or not negative:
        return None
    pos = _provenance([g for g, _ in positive])
    neg = _provenance([g for g, _ in negative])
    if (pos["rule_ids"] != _distinct(tension.get("positive_rule_ids", []))
            or neg["rule_ids"] != _distinct(tension.get("negative_rule_ids", []))):
        return None
    all_groups = [g for g, _ in positive + negative]
    return _claim(node, "unresolved-tension", "unresolved_tension", {
        "axis": axis, "context": None, "explanation": tension.get("explanation"),
        "positive_witnesses": [
            _witness_summary(hit, None, rule_types) for _, hits in positive for hit in hits],
        "negative_witnesses": [
            _witness_summary(hit, None, rule_types) for _, hits in negative for hit in hits],
    }, groups=all_groups, audit_status="unresolved",
       polarity={"positive": pos, "negative": neg,
                 "shared_roots": list(tension.get("shared_roots", []))})


def build_personality_model(synthesis: dict, interpretation: dict | None = None,
                            *, catalog: dict | None = None) -> dict:
    """Strict source matching prevents unsupported or mismatched N2 text."""
    if (not isinstance(synthesis, dict)
            or not isinstance(synthesis.get("nodes"), list)
            or not isinstance(synthesis.get("summary"), dict)):
        raise ValueError("נדרש דוח R1 מובנה")
    mode = synthesis.get("time_mode")
    if mode not in ("known", "estimated", "unknown"):
        raise ValueError("שעת לידה: ערך לא מוכר")
    if interpretation is not None and interpretation.get("time_mode") != mode:
        raise ValueError("דוח כללים ודוח R1 אינם מסכימים על שעת הלידה")
    meanings = catalog if catalog is not None else load_meaning_catalog()
    by_axis = {e["axis"]: e for e in meanings["entries"]}
    readings = {e["rule_id"]: e for e in meanings.get("rule_readings", [])}
    from .interpretation import load_rulepack
    rule_types = {r["id"]: r["type"] for r in load_rulepack().rules}
    nodes = [n for n in synthesis["nodes"] if isinstance(n, dict)
             and isinstance(n.get("id"), str)]
    by_id = {n["id"]: n for n in nodes}
    axis_nodes = {n["axis"]: n for n in nodes
                  if n.get("type") == "axis" and isinstance(n.get("axis"), str)}
    ranked = sorted(axis_nodes.values(), key=lambda n: (-n.get("strength", 0), n["axis"]))
    order = []
    for axis in synthesis["summary"].get("leading_axes", []):
        if axis in axis_nodes and axis not in order:
            order.append(axis)
    order += [n["axis"] for n in ranked if n["axis"] not in order]
    plan = {"primary": [], "secondary": [], "processes": [], "tensions": []}
    claims, covered, skipped, unexpanded = [], [], [], []
    safe_input = (isinstance(interpretation, dict)
                  and isinstance(interpretation.get("signals"), list)
                  and interpretation.get("time_mode") == mode)
    if safe_input:
        for axis in order:
            node = axis_nodes[axis]
            if axis not in by_axis or node.get("has_unresolved_tension"):
                continue
            target = ("primary" if len(plan["primary"]) < MAX_PRIMARY else
                      "secondary" if len(plan["secondary"]) < MAX_SECONDARY else None)
            if target is None:
                continue
            items = _axis_claims(node, by_axis[axis], interpretation, readings, rule_types)
            if not items:
                skipped.append(axis)
                continue
            # No curated per-rule behavior: do not consume scarce narrative
            # slots with a generic axis paragraph that could fit every chart.
            if not any(item["kind"] == "axis-example" for item in items):
                unexpanded.append(axis)
                continue
            claims.extend(items)
            plan[target].append([c["id"] for c in items])
            covered.append(axis)
        seen = set()
        for node_id in synthesis["summary"].get("top_hypotheses", []):
            if node_id in seen or len(plan["processes"]) >= MAX_PROCESSES:
                continue
            seen.add(node_id)
            node = by_id.get(node_id)
            if node is None or node.get("type") != "synthesis":
                continue
            items = _process_claims(node, axis_nodes, readings,
                                    interpretation["signals"], mode, rule_types)
            if items:
                claims.extend(items)
                plan["processes"].append([c["id"] for c in items])
        for item in synthesis.get("tensions", []):
            if item.get("status") != "unresolved":
                continue
            c = _tension_claim(item, axis_nodes, interpretation, rule_types)
            if c is not None:
                claims.append(c)
                plan["tensions"].append([c["id"]])
            else:
                skipped.append(item.get("axis", "unknown"))
    warnings = list(synthesis.get("warnings", []))
    if skipped or not safe_input:
        warnings.append("N2: טענות הושמטו בשל חוסר התאמה בין ראיות R1 לבין פלט הכללים.")
    return {
        "schema_version": 1, "semantic_version": N2_SEMANTIC_VERSION,
        "source_engine_version": synthesis.get("engine_version"),
        "source_profile_id": synthesis.get("profile_id"),
        "source_rule_pack": synthesis.get("source_rule_pack"),
        "catalog_version": meanings.get("catalog_version"),
        "catalog_review_status": "unverified",
        "time_mode": mode, "symbolic_not_diagnostic": True,
        "relationship_discovery_enabled": False,
        "local_language_model_enabled": False,
        "claims": claims, "plan": plan,
        "displayed_axis_names": covered, "skipped_unverifiable_axes": _distinct(skipped),
        "unexpanded_axis_names": _distinct(unexpanded),
        "warnings": warnings,
    }
