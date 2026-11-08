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
MAX_PROOF_STATES = 20_000  # bounded alternatives; never claim exhaustion on a capped search

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


def _candidate_groups(hits: list[dict]) -> list[dict]:
    """Group equal rule evidence, retaining every possible physical witness."""
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
    return sorted(candidates, key=lambda g: (-g["weight"], g["evidence_key"]))


def _independent(hits: list[dict]) -> tuple[list[dict], list[dict], bool]:
    """Bounded exact alternative search: independence, then count, then weight.

    The sum of editorial weights is ONLY a tie-breaker after maximizing
    independent fact coverage; it is never exposed as a trait strength.
    """
    candidates = _candidate_groups(hits)
    best: tuple[int, float] = (-1, -1.0)
    best_keys: tuple[str, ...] = ()
    best_indexes: tuple[int, ...] = ()
    states = 0
    limited = False

    def visit(i: int, used: frozenset[str], chosen: tuple[int, ...],
              total_weight: float) -> None:
        nonlocal states, limited, best, best_keys, best_indexes
        if states >= MAX_PROOF_STATES:
            limited = True
            return
        states += 1
        if len(chosen) + len(candidates) - i < best[0]:
            return
        if i == len(candidates):
            score = (len(chosen), round(total_weight, 6))
            keys = tuple(sorted(candidates[k]["evidence_key"] for k in chosen))
            if score > best or (score == best and keys < best_keys):
                best, best_keys, best_indexes = score, keys, chosen
            return
        item = candidates[i]
        if used.isdisjoint(item["roots"]):
            visit(i + 1, used | frozenset(item["roots"]),
                  chosen + (i,), total_weight + item["weight"])
        visit(i + 1, used, chosen, total_weight)

    visit(0, frozenset(), (), 0.0)
    chosen_set = set(best_indexes)
    return (
        [item for i, item in enumerate(candidates) if i in chosen_set],
        [item for i, item in enumerate(candidates) if i not in chosen_set],
        limited,
    )


def _choose_path_proof(path: tuple[str, ...], by_axis: dict[str, dict]
                       ) -> tuple[list[dict] | None, dict[str, list[dict]], bool, int]:
    """Find one *jointly* root-disjoint original witness for each path axis.

    A previously selected axis-wide group is not a binding choice. All chart
    witnesses are considered again for every path (including deep extensions).
    Proof feasibility comes first. Then maximize weakest editorial weight,
    then sum of editorial weights as a deterministic tie-breaker only.
    """
    options = {axis: by_axis[axis]["available_facts"] for axis in path}
    if any(not choices for choices in options.values()):
        return None, options, False, 0
    ordered_axes = sorted(path, key=lambda axis: (len(options[axis]), axis))
    best: dict[str, dict] | None = None
    best_score: tuple[float, float] = (-1.0, -1.0)
    best_keys: tuple[str, ...] = ()
    states = 0
    limited = False

    def visit(depth: int, used: frozenset[str], chosen: dict[str, dict]) -> None:
        nonlocal best, best_score, best_keys, states, limited
        if states >= MAX_PROOF_STATES:
            limited = True
            return
        states += 1
        if depth == len(ordered_axes):
            ordered = [chosen[axis] for axis in path]
            score = (min(item["weight"] for item in ordered),
                     round(sum(item["weight"] for item in ordered), 6))
            keys = tuple(item["evidence_key"] for item in ordered)
            if score > best_score or (score == best_score and keys < best_keys):
                best, best_score, best_keys = dict(chosen), score, keys
            return
        axis = ordered_axes[depth]
        for item in options[axis]:
            if used.isdisjoint(item["roots"]):
                chosen[axis] = item
                visit(depth + 1, used | frozenset(item["roots"]), chosen)
                del chosen[axis]
                if limited:
                    return

    visit(0, frozenset(), {})
    if best is None:
        return None, options, limited, states
    selected = [best[axis] for axis in path]
    alternatives = {
        axis: [item for item in options[axis]
               if item["evidence_key"] != best[axis]["evidence_key"]]
        for axis in path
    }
    return selected, alternatives, limited, states

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
        positive, pos_dependent, pos_limited = _independent([h for h in items if h["polarity"] > 0])
        negative, neg_dependent, neg_limited = _independent([h for h in items if h["polarity"] < 0])
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
            "available_facts": _candidate_groups([h for h in items if h["polarity"] > 0]),
            "selection_search_limited": pos_limited or neg_limited,
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
    search_limited_paths: set[tuple[str, ...]] = set()

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
                path = tuple(prior["path"] + [target])
                if path in seen:
                    continue
                chosen, alternatives, proof_limited, visited = _choose_path_proof(path, by_axis)
                if proof_limited:
                    search_limited_paths.add(path)
                if chosen is None:
                    continue
                if len(nodes) >= MAX_NODES:
                    truncated = True
                    break
                seen.add(path)
                # Parent IDs describe functional steps; this node's selected
                # witnesses constitute its complete, standalone joint proof.
                witnesses = chosen
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
                    "selected_witnesses_by_axis": dict(zip(path, witnesses)),
                    "alternative_facts_by_axis": alternatives,
                    "proof_search": {"states": visited, "limit": MAX_PROOF_STATES,
                                     "complete": not proof_limited},
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
    # Present maximal *contiguous* functional sequences only. Non-contiguous
    # overlaps may describe different processes and remain separate.
    ordered = sorted(derived, key=lambda n: (-len(n["path"]), -n["strength"], n["id"]))
    top = []
    subsumed_by: dict[str, str] = {}
    for node in ordered:
        path = node["path"]
        covering = next((
            longer for longer in top
            if longer["domain"] == node["domain"]
            and any(longer["path"][i:i + len(path)] == path
                    for i in range(len(longer["path"]) - len(path) + 1))
        ), None)
        if covering is not None:
            subsumed_by[node["id"]] = covering["id"]
        else:
            top.append(node)
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
            "subsumed_by": subsumed_by,
            "proof_search_limited_paths": [list(p) for p in sorted(search_limited_paths)],
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
            *(["חיפוש הראיות הוגבל במשאבים; היעדר מסלול אינו הוכחה שלא קיימת חלופה."]
              if search_limited_paths or any(n.get("selection_search_limited") for n in base)
              else []),
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
