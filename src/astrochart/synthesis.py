"""Auditable, offline and deliberately conservative composition above interpretation.py.

All new cross-axis readings are hypotheses about *symbolic editorial patterns*.
They are not psychological diagnoses, probabilities, or source-approved rules.
No imported astrology library, network call, training, or rule-pack mutation.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any

from .domain import SIGNS

SYNTHESIS_VERSION = "0.1.0"
PROFILE_ID = "western-tropical-whole-sign-r1"
MAX_NODES = 192  # resource guard, NOT a fixed number of abstraction levels

# A separately auditable *engineering* ontology of functional transitions.
# These edges do not claim to be traditional astrological interpretation rules.
# No complete complex trait, natal placement, or finished narrative is stored.
FUNCTIONS = {
    "יוזמה": ("הנעה", "ביצוע"),
    "גמישות": ("התאמה", "ביצוע"),
    "יציבות": ("ייצוב", "ביצוע"),
    "התמדה": ("שימור", "ביצוע"),
    "אחריות": ("בקרה", "ביצוע"),
    "יצירתיות": ("יצירה", "עיבוד"),
    "חשיבה": ("ניתוח", "עיבוד"),
    "התבוננות": ("בחינה", "עיבוד"),
    "תקשורת": ("הבעה", "עיבוד"),
    "רגישות": ("קליטה", "קשר"),
    "עצמאות": ("בחירה", "קשר"),
    "שיתופיות": ("תיאום", "קשר"),
    "הרמוניה": ("איזון", "קשר"),
}
TRANSITIONS = {
    "יוזמה": ("גמישות", "התמדה"),
    "גמישות": ("התמדה", "אחריות"),
    "יציבות": ("התמדה",),
    "התמדה": ("אחריות",),
    "יצירתיות": ("חשיבה", "תקשורת"),
    "חשיבה": ("התבוננות", "תקשורת"),
    "התבוננות": ("תקשורת",),
    "רגישות": ("שיתופיות",),
    "עצמאות": ("שיתופיות",),
    "שיתופיות": ("הרמוניה",),
}
# Sign-only *classical* dignity subset, independent of trait weights.
# Do not infer triplicity/sect, bounds, face, combustion or accidental strength.
DOMICILE = {
    "שמש": ("אריה",), "ירח": ("סרטן",), "מרקורי": ("תאומים", "בתולה"),
    "ונוס": ("שור", "מאזניים"), "מאדים": ("טלה", "עקרב"),
    "צדק": ("קשת", "דגים"), "שבתאי": ("גדי", "דלי"),
}
EXALTATION = {
    "שמש": "טלה", "ירח": "שור", "מרקורי": "בתולה",
    "ונוס": "דגים", "מאדים": "גדי", "צדק": "סרטן", "שבתאי": "מאזניים",
}
DIGNITY_SOURCE = "https://kerykeion.net/python-library/docs/v6/dignities"
METHOD_SOURCE = "docs/interpretation-synthesis-r1.md"


def _opposite(sign: str) -> str:
    return SIGNS[(SIGNS.index(sign) + 6) % 12]


def _dignity(body_name: str, sign: str) -> dict[str, Any] | None:
    """Documented sign-only subset of traditional point values; not trait scores."""
    if body_name not in DOMICILE:
        return None
    items = []
    if sign in DOMICILE[body_name]:
        items.append({"kind": "domicile", "points": 5})
    if sign == EXALTATION[body_name]:
        items.append({"kind": "exaltation", "points": 4})
    if sign in {_opposite(s) for s in DOMICILE[body_name]}:
        items.append({"kind": "detriment", "points": -5})
    if sign == _opposite(EXALTATION[body_name]):
        items.append({"kind": "fall", "points": -4})
    return {
        "body": body_name, "sign": sign,
        "sign_only_points": sum(item["points"] for item in items),
        "components": items, "method_source": DIGNITY_SOURCE,
        "scope": "partial-essential-dignity-not-trait-score",
    }


def _factor_context(chart, report: dict) -> list[dict]:
    """Never use an unverified sampled longitude as an exact natal value."""
    if chart is None:
        return []
    result = []
    time_mode = report.get("time_mode", "unknown")
    for body in sorted(chart.bodies, key=lambda b: b.name):
        if time_mode == "unknown":
            if len(body.signs_possible) != 1:
                continue
            if SIGNS[body.signs_possible[0]] != body.sign:
                continue
        elif time_mode == "estimated":
            degree = body.longitude % 30
            if min(degree, 30 - degree) < 1:
                continue
        dignity = _dignity(body.name, body.sign)
        if dignity is not None:
            dignity["time_provisional"] = time_mode != "known"
            result.append(dignity)
    return result


def _roots(key: str) -> tuple[str, ...]:
    """Dependency closure: aspects and houses reuse underlying body observations."""
    bits = key.split(":")
    if len(bits) >= 3 and bits[0] == "placement":
        return ("body:" + bits[1],)
    if len(bits) >= 4 and bits[0] == "aspect":
        return tuple(sorted(("body:" + bits[1], "body:" + bits[2])))
    if len(bits) >= 3 and bits[0] == "house":
        return ("body:" + bits[1], "angle:ascendant")
    if key.startswith("composite:"):
        return tuple(sorted(set(root for component in key[10:].split("+")
                                for root in _roots(component))))
    # An explicitly shared evidence_group must remain a single shared source.
    return ("evidence-group:" + key,)


def _independent(hits: list[dict]) -> tuple[list[dict], list[dict]]:
    """Greedy maximum-salience disjoint witnesses; duplicates never add weight."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for hit in hits:
        if hit.get("modifier_only") or hit.get("weight", 0) <= 0:
            continue
        key = hit.get("evidence_key")
        if isinstance(key, str) and key:
            groups[key].append(hit)
    candidates = []
    for key, members in groups.items():
        members = sorted(members, key=lambda h: (-h["weight"], h["rule_id"]))
        candidates.append({
            "evidence_key": key, "roots": list(_roots(key)),
            "weight": members[0]["weight"],
            "rule_ids": sorted({m["rule_id"] for m in members}),
            "review_statuses": sorted({m.get("review_status", "unverified") for m in members}),
            "source_refs": sorted({m["source_url"] for m in members if m.get("source_url")}),
            "details": [m["evidence"] for m in members],
        })
    candidates.sort(key=lambda g: (-g["weight"], g["evidence_key"]))
    selected, dependent, used = [], [], set()
    for group in candidates:
        if used.intersection(group["roots"]):
            dependent.append(group)
        else:
            selected.append(group)
            used.update(group["roots"])
    return selected, dependent


def _stable_id(path: tuple[str, ...]) -> str:
    return "synth-" + sha256(("r1|" + "|".join(path)).encode("utf-8")).hexdigest()[:16]


def _collect(groups: list[dict]) -> tuple[list[str], list[str], list[str]]:
    return (
        sorted({rid for group in groups for rid in group["rule_ids"]}),
        sorted({src for group in groups for src in group["source_refs"]}),
        sorted({status for group in groups for status in group["review_statuses"]}),
    )


def _base_features(report: dict) -> tuple[list[dict], list[dict]]:
    by_axis: dict[str, list[dict]] = defaultdict(list)
    for hit in report.get("signals", []):
        if hit.get("axis") in FUNCTIONS:
            by_axis[hit["axis"]].append(hit)

    features, tensions = [], []
    for axis in sorted(by_axis):
        items = by_axis[axis]
        positive, pos_dependent = _independent([h for h in items if h["polarity"] > 0])
        negative, neg_dependent = _independent([h for h in items if h["polarity"] < 0])
        # Conflicting premises are never resolved by a simple difference of scores.
        if positive and negative:
            tensions.append({
                "axis": axis, "status": "unresolved",
                "positive_rule_ids": _collect(positive)[0],
                "negative_rule_ids": _collect(negative)[0],
                "shared_roots": sorted(set(r for p in positive for r in p["roots"])
                                       & set(r for n in negative for r in n["roots"])),
                "context": None,
                "explanation": "שני הכיוונים נתמכים; אין ראיה לנסיבות המבדילות ביניהם.",
            })
        if not positive:
            continue
        rule_ids, sources, statuses = _collect(positive)
        all_ids, _, _ = _collect(positive + pos_dependent)
        features.append({
            "id": _stable_id((axis,)), "type": "axis",
            "axis": axis, "path": [axis], "level": 0,
            "label": axis, "function": FUNCTIONS[axis][0],
            "domain": FUNCTIONS[axis][1],
            "parents": [], "relation": "observed-axis",
            "strength": round(max(p["weight"] for p in positive), 3),
            "strength_kind": "legacy-editorial-max-not-probability",
            "independent_facts": positive, "dependent_facts": pos_dependent,
            "counter_facts": negative, "dependent_counter_facts": neg_dependent,
            "evidence_roots": sorted({r for p in positive for r in p["roots"]}),
            "rule_ids": rule_ids, "related_rule_ids": all_ids,
            "source_refs": sources, "source_review_statuses": statuses,
            "audit_status": "symbolic-input",
            "has_unresolved_tension": bool(negative),
            "provisional_time": bool(report.get("time_uncertain")),
        })
    return features, tensions


def synthesize(chart, report: dict) -> dict:
    """Derive finite acyclic functional paths with proof-level provenance.

    Edges mean 'this functional operation may feed the next'; the *presence*
    of every operation is determined by actual, mutually independent chart facts.
    The derived process never feeds back as a new independent fact.
    """
    if not isinstance(report, dict) or "signals" not in report:
        raise ValueError("נדרש דוח כללים מחושב")
    base, tensions = _base_features(report)
    by_axis = {node["axis"]: node for node in base}
    nodes = list(base)
    seen = {tuple(node["path"]) for node in base}
    active = [node for node in base if not node["has_unresolved_tension"]]
    frontier = list(active)
    truncated = False

    while frontier:
        next_frontier = []
        for prior in sorted(frontier, key=lambda n: tuple(n["path"])):
            last = prior["path"][-1]
            for target in TRANSITIONS.get(last, ()):
                if target not in by_axis or target in prior["path"]:
                    continue
                successor = by_axis[target]
                if successor["has_unresolved_tension"]:
                    continue
                if successor["domain"] != prior["domain"]:
                    continue
                if set(prior["evidence_roots"]) & set(successor["evidence_roots"]):
                    continue
                path = tuple(prior["path"] + [target])
                if path in seen:
                    continue
                if len(nodes) >= MAX_NODES:
                    truncated = True
                    break
                seen.add(path)
                # Note: derived nodes are only *transformations* of leaf evidence,
                # not additional votes. Each parent path is strictly shorter.
                group_map = {
                    group["evidence_key"]: group
                    for group in (prior["independent_facts"] + successor["independent_facts"])
                }
                witnesses = [group_map[k] for k in sorted(group_map)]
                rule_ids, sources, statuses = _collect(witnesses)
                functions = [FUNCTIONS[name][0] for name in path]
                node = {
                    "id": _stable_id(path), "type": "synthesis",
                    "axis": None, "path": list(path), "level": len(path) - 1,
                    "label": "תהליך " + FUNCTIONS[target][1] + ": " + " ← ".join(functions),
                    "domain": successor["domain"],
                    "relation": "functional-composition",
                    "parents": [prior["id"], successor["id"]],
                    "strength": round(min(prior["strength"], successor["strength"]), 3),
                    "strength_kind": "weakest-editorial-witness-not-probability",
                    "independent_facts": witnesses,
                    "dependent_facts": [], "counter_facts": [],
                    "evidence_roots": sorted(set(prior["evidence_roots"])
                                             | set(successor["evidence_roots"])),
                    "rule_ids": rule_ids, "related_rule_ids": rule_ids,
                    "source_refs": sources, "source_review_statuses": statuses,
                    "audit_status": "hypothesis",
                    "hypothesis_reason": "הקשר התפקודי בין צירים הוא הנחת מודל הנדסית, לא כלל פרשנות שאושר מול מקור פרטני.",
                    "provisional_time": bool(report.get("time_uncertain")),
                }
                nodes.append(node)
                next_frontier.append(node)
            if truncated:
                break
        if truncated:
            break
        frontier = next_frontier

    derived = [n for n in nodes if n["type"] == "synthesis"]
    parent_ids = {p for n in derived for p in n["parents"]}
    top = [n for n in derived if n["id"] not in parent_ids]
    top.sort(key=lambda n: (-n["level"], -n["strength"], n["id"]))
    axes = sorted(base, key=lambda n: (-n["strength"], n["axis"]))
    return {
        "schema_version": 1, "engine_version": SYNTHESIS_VERSION,
        "profile_id": PROFILE_ID, "source_rule_pack": report.get("pack_version"),
        "status": "symbolic-hypothesis-overlay",
        "calculation_direction": "bottom-up",
        "presentation_direction": "top-down",
        "time_mode": report.get("time_mode"),
        "factor_conditions": _factor_context(chart, report),
        "nodes": nodes,
        "top_feature_ids": [n["id"] for n in top],
        "tensions": tensions,
        "summary": {
            "leading_axes": [n["axis"] for n in axes[:5]],
            "top_hypotheses": [n["id"] for n in top[:8]],
            "hypothesis_count": len(derived),
            "unresolved_tension_count": len(tensions),
        },
        "feedback_contract": {
            "choices": ["A", "B", "both", "neither", "unknown"],
            "automatic_learning_enabled": False,
        },
        "warnings": [
            "כל ההסקות החדשות הן השערות הנובעות מאונטולוגיה הנדסית; לא כללים מאושרים.",
            "משקלי הכללים ומקדמי העוצמה אינם הסתברויות או מדדי אישיות.",
            "ניקוד עוצמת גוף חלקי לפי מזל אינו מתורגם לציון תכונת אופי.",
            *(
                ["גבול משאבים: מספר הצמתים הוגבל; לא כל המסלולים נבדקו."]
                if truncated else []
            ),
            *(["שעת הלידה אינה ודאית; אין להסיק בתים או היבטים מהדגימה."]
              if report.get("time_uncertain") else []),
        ],
    }


def format_synthesis(result: dict) -> str:
    """Hebrew top-down disclosure with a readable derivation and audit trail."""
    by_id = {n["id"]: n for n in result["nodes"]}
    lines = [
        "תמונה כללית — סינתזה אסטרולוגית סמלית (ניסוי)",
        "אין מדובר באבחון אישיות מדעי. קשרים מוסקים הם השערות עד לביקורת פרטנית.",
        "שיטה: " + result["profile_id"],
        "",
    ]
    top = result["summary"]["top_hypotheses"]
    if top:
        lines.append("◆ מאפיינים מורכבים (השערות)")
        for node_id in top:
            node = by_id[node_id]
            lines.extend([
                "  • " + node["label"],
                "    שרשרת: " + " ← ".join(node["path"]),
                "    הנמקה: " + ", ".join(node["rule_ids"]),
                "    ראיות עצמאיות: " + str(len(node["independent_facts"])),
                "    עוצמת החוליה החלשה לפי משקל עריכתי: " + str(node["strength"]),
                "    מעמד: השערה; טרם אושר קשר ההסקה.",
            ])
    else:
        lines.append("לא נמצאה שרשרת מאפיינים מורכבת בעלת ראיות נפרדות.")
    lines.extend(["", "◆ מאפיינים מרכזיים",
                  ", ".join(result["summary"]["leading_axes"]) or "אין ראיות מתאימות."])
    if result["tensions"]:
        lines.extend(["", "◆ מתחים לא מוכרעים"])
        for item in result["tensions"]:
            lines.append("  • " + item["axis"] + ": " + item["explanation"])
            lines.append("    בעד: " + ", ".join(item["positive_rule_ids"])
                         + " | נגד: " + ", ".join(item["negative_rule_ids"]))
    lines.extend(["", "הסתייגויות:", *(f"• {w}" for w in result["warnings"])])
    return "\n".join(lines)
