"""N2 semantic personality representation, strictly downstream of unchanged R1.

Only supported R1 nodes may license an editorial meaning. Meaning examples are
not new astrological rules, observed conduct, independent proofs or diagnoses.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from .narrative import _supported_process

N2_SEMANTIC_VERSION = "0.1.0"
CATALOG_FILE = "meaning_catalog_n2.json"
MAX_PRIMARY = 3
MAX_SECONDARY = 2
MAX_PROCESSES = 2


def load_meaning_catalog(path: Path | None = None) -> dict:
    """Read and validate an explicit, separately reviewable editorial glossary."""
    source = path or Path(__file__).with_name(CATALOG_FILE)
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("entries"), list):
        raise ValueError("מאגר משמעות N2 אינו תקין")
    from .synthesis import FUNCTIONS  # vocabulary only; never mutate R1
    entries = data["entries"]
    if (len(entries) != len(FUNCTIONS)
            or {e.get("axis") for e in entries} != set(FUNCTIONS)
            or len({e.get("id") for e in entries}) != len(entries)):
        raise ValueError("מאגר N2 אינו מכסה באופן ייחודי את צירי R1")
    for entry in entries:
        required = ("id", "axis", "definition", "strength", "challenge",
                    "process_action", "recurrence_note")
        if (any(not isinstance(entry.get(k), str) or not entry[k].strip()
                for k in required)
                or not isinstance(entry.get("example"), dict)
                or any(not isinstance(entry["example"].get(k), str)
                       or not entry["example"][k].strip()
                       for k in ("situation", "behavior"))
                or entry.get("kind") != "axis_meaning"
                or entry.get("provenance", {}).get("review_status") != "unverified"
                or entry.get("provenance", {}).get("astrological_rule") is not False):
            raise ValueError("יחידת משמעות N2 חסרה או בעלת מעמד שגוי")
    return data


def _distinct(values) -> list[str]:
    return sorted({v for v in values if isinstance(v, str) and v})


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
    for group in groups:
        if (not isinstance(group, dict) or not isinstance(group.get("rule_ids"), list)
                or not group["rule_ids"] or not group.get("evidence_key")
                or not group.get("roots") or not isinstance(group.get("review_statuses"), list)):
            return []
    result = _provenance(groups)
    if field == "independent_facts" and (
        result["rule_ids"] != _distinct(node.get("rule_ids", []))
        or result["source_refs"] != _distinct(node.get("source_refs", []))
        or result["source_review_statuses"] != _distinct(
            node.get("source_review_statuses", []))
    ):
        return []
    return groups


def _key(node: dict, kind: str, suffix: str = "") -> str:
    code = "|".join((node["id"], kind, suffix))
    return "n2-" + sha256(code.encode("utf-8")).hexdigest()[:15]


def _claim(node: dict, kind: str, classification: str, content: dict,
           *, groups: list[dict] | None = None, meaning_ids: list[str] | None = None,
           suffix: str = "", polarity: dict | None = None,
           audit_status: str | None = None) -> dict:
    witness_groups = groups if groups is not None else _verified_groups(node)
    proof = _provenance(witness_groups)
    claim = {
        "id": _key(node, kind, suffix),
        "kind": kind,
        "classification": classification,
        "axis": node.get("axis"),
        "content": content,
        "node_ids": [node["id"]],
        "rule_ids": proof["rule_ids"],
        "source_refs": proof["source_refs"],
        "source_review_statuses": proof["source_review_statuses"],
        "evidence_keys": proof["evidence_keys"],
        "evidence_roots": proof["evidence_roots"],
        "meaning_ids": list(meaning_ids or []),
        "audit_status": audit_status or node.get("audit_status", "symbolic-input"),
        "provisional_time": bool(node.get("provisional_time")),
        "limitations": [
            "symbolic-not-psychological-diagnosis",
            *([] if classification == "existing_rule" else
              ["editorial-not-source-approved"]),
            *([] if classification != "synthesis_hypothesis" else
              ["r1-transition-is-hypothesis"]),
        ],
    }
    if polarity is not None:
        claim["evidence_by_polarity"] = polarity
    return claim


def _anchor_hit(node: dict, interpretation: dict | None) -> dict | None:
    """Bind exact rule text to a SELECTED R1 witness, never unrelated hits."""
    if not interpretation:
        return None
    groups = _verified_groups(node)
    candidates = []
    for hit in interpretation.get("signals", []):
        if (hit.get("axis") != node["axis"]
                or hit.get("polarity") != 1 or hit.get("modifier_only")):
            continue
        if any(hit.get("evidence_key") == g["evidence_key"]
               and hit.get("rule_id") in g["rule_ids"] for g in groups):
            candidates.append(hit)
    candidates.sort(key=lambda h: (-h.get("weight", 0), h.get("rule_id", "")))
    return candidates[0] if candidates else None


def _axis_claims(node: dict, entry: dict, interpretation: dict | None) -> list[dict]:
    groups = _verified_groups(node)
    if node.get("type") != "axis" or not groups or node.get("has_unresolved_tension"):
        return []
    claims = []
    hit = _anchor_hit(node, interpretation)
    if hit is not None and isinstance(hit.get("text"), str) and hit["text"].strip():
        witness = next(g for g in groups
                       if hit["rule_id"] in g["rule_ids"]
                       and hit["evidence_key"] == g["evidence_key"])
        # Source status must remain the status of the original rule.
        direct = _claim(node, "rule-anchor", "existing_rule", {
            "rule_text": hit["text"].strip(),
            "chart_evidence": hit.get("evidence", ""),
            "selected_rule_id": hit["rule_id"],
        }, groups=[{
            "rule_ids": [hit["rule_id"]],
            "source_refs": [hit["source_url"]] if hit.get("source_url") else [],
            "review_statuses": [hit.get("review_status", "unverified")],
            "evidence_key": witness["evidence_key"],
            "roots": witness["roots"],
        }])
        claims.append(direct)
    claims.append(_claim(node, "axis-meaning", "editorial_extension", {
        "axis": node["axis"], "definition": entry["definition"],
        "strength": entry["strength"], "challenge": entry["challenge"],
        "independent_evidence_count": len(groups),
    }, meaning_ids=[entry["id"]]))
    claims.append(_claim(node, "axis-example", "possible_behavior_example", {
        "situation": entry["example"]["situation"],
        "behavior": entry["example"]["behavior"],
        "recurrence_note": entry["recurrence_note"],
    }, meaning_ids=[entry["id"]]))
    return claims


def _process_claims(node: dict, axis_nodes: dict, catalog: dict) -> list[dict]:
    if not _supported_process(node) or not _verified_groups(node):
        return []
    path = node["path"]
    # The model's original selected witnesses and its axis nodes must agree.
    selected = node.get("selected_witnesses_by_axis", {})
    if (set(selected) != set(path)
            or any(a not in axis_nodes or a not in catalog
                   or axis_nodes[a].get("has_unresolved_tension")
                   or axis_nodes[a].get("domain") != node.get("domain")
                   for a in path)
            or any(selected[a] != fact for a, fact in
                   zip(path, node["independent_facts"]))):
        return []
    return [
        _claim(node, "process-reading", "synthesis_hypothesis", {
            "path": list(path), "domain": node["domain"],
            "model_relation": node.get("relation"),
            "proof_search_complete": node.get("proof_search", {}).get("complete", True),
        }, meaning_ids=[catalog[a]["id"] for a in path],
           audit_status="hypothesis"),
        _claim(node, "process-example", "possible_behavior_example", {
            "path": list(path), "domain": node["domain"],
            "actions": [catalog[a]["process_action"] for a in path],
            "scenario": {
                "ביצוע": "כאשר עומדת לפניו משימה שיש בה כמה שלבים",
                "עיבוד": "כאשר עליו להבין רעיון מורכב",
                "קשר": "כאשר נדרשת התנהלות מול כמה נקודות מבט",
            }.get(node["domain"], "כאשר עולה צורך לפעול"),
        }, meaning_ids=[catalog[a]["id"] for a in path],
           audit_status="hypothesis"),
    ]


def _tension_claim(tension: dict, axis_nodes: dict) -> dict:
    axis = tension["axis"]
    node = axis_nodes.get(axis)
    if node is None:
        raise ValueError("סתירת R1 ללא צומת ציר: " + axis)
    positive = _verified_groups(node)
    negative = _verified_groups(node, "counter_facts")
    pos, neg = _provenance(positive), _provenance(negative)
    if (not positive or not negative
            or pos["rule_ids"] != _distinct(tension.get("positive_rule_ids", []))
            or neg["rule_ids"] != _distinct(tension.get("negative_rule_ids", []))):
        raise ValueError("סתירה שאינה תואמת את ראיות R1: " + axis)
    all_groups = positive + negative
    return _claim(node, "unresolved-tension", "unresolved_tension", {
        "axis": axis, "explanation": tension.get("explanation"),
        "context": None,
    }, groups=all_groups, audit_status="unresolved",
       polarity={
           "positive": pos, "negative": neg,
           "shared_roots": list(tension.get("shared_roots", [])),
       })


def build_personality_model(synthesis: dict, interpretation: dict | None = None,
                            *, catalog: dict | None = None) -> dict:
    """Assemble attributable content; no generative or relationship mining."""
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
    by_meaning = {e["axis"]: e for e in meanings["entries"]}
    node_by_id = {n["id"]: n for n in synthesis["nodes"]
                  if isinstance(n, dict) and isinstance(n.get("id"), str)}
    axis_nodes = {n["axis"]: n for n in synthesis["nodes"]
                  if isinstance(n, dict) and n.get("type") == "axis"
                  and isinstance(n.get("axis"), str)}
    ranked = sorted(axis_nodes.values(), key=lambda n: (
        -n.get("strength", 0), n["axis"]))
    ordered_axes = []
    for axis in synthesis["summary"].get("leading_axes", []):
        if axis in axis_nodes and axis not in ordered_axes:
            ordered_axes.append(axis)
    ordered_axes += [n["axis"] for n in ranked if n["axis"] not in ordered_axes]
    plans = {"primary": [], "secondary": [], "processes": [], "tensions": []}
    claims = []
    covered = []
    for axis in ordered_axes:
        node = axis_nodes[axis]
        if axis not in by_meaning or node.get("has_unresolved_tension"):
            continue
        target = ("primary" if len(plans["primary"]) < MAX_PRIMARY else
                  "secondary" if len(plans["secondary"]) < MAX_SECONDARY else None)
        if target is None:
            continue
        items = _axis_claims(node, by_meaning[axis], interpretation)
        if not items:
            continue
        claims.extend(items)
        plans[target].append([c["id"] for c in items])
        covered.append(axis)
    seen = set()
    for node_id in synthesis["summary"].get("top_hypotheses", []):
        if node_id in seen or len(plans["processes"]) >= MAX_PROCESSES:
            continue
        seen.add(node_id)
        node = node_by_id.get(node_id)
        if node is None or node.get("type") != "synthesis":
            continue
        items = _process_claims(node, axis_nodes, by_meaning)
        if items:
            claims.extend(items)
            plans["processes"].append([c["id"] for c in items])
    for item in synthesis.get("tensions", []):
        if item.get("status") != "unresolved":
            continue
        c = _tension_claim(item, axis_nodes)
        claims.append(c)
        plans["tensions"].append([c["id"]])
    warnings = list(synthesis.get("warnings", []))
    return {
        "schema_version": 1, "semantic_version": N2_SEMANTIC_VERSION,
        "source_engine_version": synthesis.get("engine_version"),
        "source_profile_id": synthesis.get("profile_id"),
        "source_rule_pack": synthesis.get("source_rule_pack"),
        "catalog_version": meanings.get("catalog_version"),
        "catalog_review_status": "unverified",
        "time_mode": mode,
        "symbolic_not_diagnostic": True,
        "relationship_discovery_enabled": False,
        "local_language_model_enabled": False,
        "claims": claims, "plan": plans,
        "displayed_axis_names": covered,
        "warnings": warnings,
    }
