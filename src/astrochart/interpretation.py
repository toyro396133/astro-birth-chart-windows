"""Versioned, auditable symbolic interpretation of computed chart facts.

This is NOT psychological diagnosis or empirically validated personality scoring.
Rules are editorial statements, not natural laws. The engine has no network calls,
no arbitrary rule evaluation, no automatic self-modification, and no LLM runtime.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .domain import ASPECTS, BODIES, SIGNS, degree_in_sign, short_separation

SCHEMA_VERSION = 1
MAX_PACK_BYTES = 256_000
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
AXES = {
    "יוזמה", "יציבות", "גמישות", "תקשורת", "חשיבה", "רגישות",
    "יצירתיות", "עצמאות", "אחריות", "שיתופיות", "התבוננות",
    "התמדה", "הרמוניה", "עוצמה",
}
ASPECT_KINDS = {"צמידות", "שישים", "ריבוע", "משולש", "ניגוד"}
REVIEW_STATUSES = {"unverified", "reviewed", "approved", "conflicting", "rejected"}
MAX_ORBS = {name: orb for _, name, orb in ASPECTS}
ASPECT_ANGLES = {name: angle for angle, name, _ in ASPECTS}


class RulePackError(ValueError):
    pass


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    axis: str
    polarity: int
    weight: float
    text: str
    evidence: str
    source: str
    provisional: bool
    review_status: str = 'unverified'
    evidence_key: str = ''
    source_url: str | None = None
    modifier_only: bool = False


@dataclass(frozen=True)
class RulePack:
    version: str
    tradition: str
    rules: tuple[dict, ...]


def _read_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_PACK_BYTES:
        raise RulePackError("קובץ הכללים חסר או גדול מדי")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RulePackError("קובץ כללים אינו JSON תקין") from exc
    if not isinstance(data, dict):
        raise RulePackError("שורש קובץ הכללים חייב להיות אובייקט")
    return data


def _version(value: object) -> bool:
    return isinstance(value, str) and VERSION.fullmatch(value) is not None


def _validate_rule(rule: dict):
    if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
        raise RulePackError("לכל כלל נדרש מזהה טקסטואלי")
    if IDENTIFIER.fullmatch(rule["id"]) is None:
        raise RulePackError("מזהה כלל אינו תקין")
    if not isinstance(rule.get("enabled"), bool):
        raise RulePackError("לכל כלל נדרש שדה enabled בוליאני")
    status = rule.get("review_status", "unverified")
    if status not in REVIEW_STATUSES or (status == "rejected" and rule["enabled"]):
        raise RulePackError("סטטוס ביקורת לא תקין: " + rule["id"])
    for key in ("created_in", "updated_in"):
        if key in rule and not _version(rule[key]):
            raise RulePackError("גרסת עריכה לא תקינה: " + rule["id"])
    for key in ("revision_note", "evidence_group"):
        if key in rule and (not isinstance(rule[key], str)
                            or not 3 <= len(rule[key]) <= 350):
            raise RulePackError("מטא־נתון לא תקין: " + rule["id"])
    refs = rule.get("related_rule_ids", [])
    if (not isinstance(refs, list) or len(refs) > 16
            or any(not isinstance(x, str) or not IDENTIFIER.fullmatch(x) for x in refs)):
        raise RulePackError("הפניה לא תקינה לכלל קשור: " + rule["id"])
    detail = rule.get("source_detail")
    if detail is not None and (
        not isinstance(detail, dict)
        or not isinstance(detail.get("url"), str)
        or not detail["url"].startswith("https://")
        or any(not isinstance(detail.get(k), str) or not detail[k]
               for k in ("title", "section", "scope"))
        or any(not isinstance(v, str) or len(v) > 350 for v in detail.values())
    ):
        raise RulePackError("פרטי מקור לא תקינים: " + rule["id"])
    if status == "approved" and (
        not isinstance(detail, dict)
        or detail.get("scope") != "rule-specific-verified"
        or not rule.get("revision_note")
    ):
        raise RulePackError("אישור כלל מחייב מקור פרטני ותיעוד החלטת ביקורת: " + rule["id"])
    if not rule["enabled"]:
        return
    if (rule.get("type") not in ("placement", "aspect", "house", "composite")
            or not isinstance(rule.get("axis"), str)
            or not 2 <= len(rule["axis"]) <= 32
            or any(ord(ch) < 32 for ch in rule["axis"])
            or type(rule.get("polarity")) is not int
            or rule["polarity"] not in (-1, 1)
            or type(rule.get("weight")) not in (float, int)
            or not math.isfinite(rule["weight"])
            or not 0 < rule["weight"] <= 5):
        raise RulePackError("תנאי, ציר או משקל כלל אינם תקינים: " + rule["id"])
    for field in ("text", "source"):
        if (not isinstance(rule.get(field), str) or not 5 <= len(rule[field]) <= 350):
            raise RulePackError("חסר תיאור או מקור עריכתי בכלל " + rule["id"])
    when = rule.get("when")
    if not isinstance(when, dict):
        raise RulePackError("שדה when חסר בכלל " + rule["id"])
    if rule["type"] == "placement":
        if (set(when) != {"body", "sign"}
                or when["body"] not in BODIES or when["sign"] not in SIGNS):
            raise RulePackError("כלל מיקום בלתי מוכר: " + rule["id"])
    elif rule["type"] == "house":
        if (set(when) != {"body", "house"} or when["body"] not in BODIES
                or type(when["house"]) is not int or not 1 <= when["house"] <= 12):
            raise RulePackError("כלל בית בלתי מוכר: " + rule["id"])
    elif rule["type"] == "aspect":
        if (set(when) != {"pair", "kind"}
                or not isinstance(when["pair"], list) or len(when["pair"]) != 2
                or not all(isinstance(b, str) for b in when["pair"])
                or len(set(when["pair"])) != 2
                or any(b not in BODIES for b in when["pair"])
                or when["kind"] not in ASPECT_KINDS):
            raise RulePackError("כלל היבט בלתי מוכר: " + rule["id"])
    else:
        clauses = when.get("all")
        if (set(when) != {"all"} or not isinstance(clauses, list)
                or not 2 <= len(clauses) <= 3
                or any(not isinstance(c, dict) or set(c) != {"body", "sign"}
                       or c["body"] not in BODIES or c["sign"] not in SIGNS
                       for c in clauses)
                or len({c["body"] for c in clauses}) != len(clauses)):
            raise RulePackError("כלל משולב לא תקין: " + rule["id"])

def _validated_pack(data: dict) -> RulePack:
    if (data.get("schema_version") != SCHEMA_VERSION
            or not _version(data.get("pack_version"))
            or data.get("tradition") != "western-tropical-whole-sign"
            or not isinstance(data.get("rules"), list)
            or len(data["rules"]) > 500):
        raise RulePackError("גרסת סכימה, מסורת או מבנה חבילה אינם מתאימים")
    seen = set()
    for rule in data["rules"]:
        _validate_rule(rule)
        if rule["id"] in seen:
            raise RulePackError("מזהה כלל כפול: " + rule["id"])
        seen.add(rule["id"])
    for rule in data["rules"]:
        if any(rid not in seen for rid in rule.get("related_rule_ids", [])):
            raise RulePackError("הפניה לכלל שאינו קיים: " + rule["id"])
    return RulePack(data["pack_version"], data["tradition"],
                    tuple(rule for rule in data["rules"] if rule["enabled"]))


def load_rulepack(*, path: Path | None = None, overlay_path: Path | None = None) -> RulePack:
    """Load versioned built-in rules; an explicit JSON overlay may override by ID.

    No implicit search in user directories, and no untrusted executable expressions.
    An overlay must name the base version it was reviewed against.
    """
    base = _read_json(Path(path) if path else Path(__file__).with_name("interpretation_rules.json"))
    _validated_pack(base)
    if overlay_path is None:
        return _validated_pack(base)
    overlay = _read_json(Path(overlay_path))
    if (overlay.get("schema_version") != SCHEMA_VERSION
            or overlay.get("base_pack_version") != base["pack_version"]
            or not _version(overlay.get("pack_version"))
            or overlay.get("pack_version") == base["pack_version"]
            or not isinstance(overlay.get("rules"), list)
            or len(overlay["rules"]) > 100):
        raise RulePackError("שכבת השינויים אינה תואמת לחבילת הבסיס")
    by_id = {r["id"]: dict(r) for r in base["rules"]}
    seen = set()
    for rule in overlay["rules"]:
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            raise RulePackError("שינוי ללא מזהה כלל")
        if rule["id"] in seen:
            raise RulePackError("שינוי כפול לאותו כלל")
        seen.add(rule["id"])
        if (any(field in rule for field in ("text", "when", "polarity", "weight"))
                and "source" not in rule):
            raise RulePackError("שינוי תוכן מחייב מקור עריכתי מפורש")
        updated = dict(by_id.get(rule["id"], {}))
        updated.update(rule)
        _validate_rule(updated)
        by_id[rule["id"]] = updated
    merged = {
        "schema_version": SCHEMA_VERSION,
        "pack_version": overlay["pack_version"],
        "tradition": base["tradition"],
        "rules": list(by_id.values()),
    }
    return _validated_pack(merged)


def _placement_fact(body_name, sign, chart, bodies, uncertain_time):
    body = bodies.get(body_name)
    if body is None or body.sign != sign:
        return None
    if chart.approximate:
        if len(body.signs_possible) != 1 or SIGNS[body.signs_possible[0]] != sign:
            return None
        evidence = f"{body_name} במזל {sign} (אותו מזל בכל הדגימות; לא מעלת לידה)"
    elif uncertain_time:
        degree = degree_in_sign(body.longitude)
        if min(degree, 30 - degree) < 1:
            return None
        evidence = f"{body_name} במזל {sign} לפי שעה משוערת (ללא מעלה מדויקת)"
    else:
        evidence = f"{body_name} במזל {sign} ({degree_in_sign(body.longitude):.2f}°)"
    return (evidence, 1.0, f"placement:{body_name}:{sign}")


def _match(rule, chart, bodies, uncertain_time):
    when = rule["when"]
    rule_type = rule["type"]
    if rule_type == "placement":
        return _placement_fact(when["body"], when["sign"], chart, bodies, uncertain_time)
    if rule_type == "composite":
        facts = [_placement_fact(c["body"], c["sign"], chart, bodies,
                                 uncertain_time) for c in when["all"]]
        if any(f is None for f in facts):
            return None
        return (" יחד עם ".join(f[0] for f in facts), 1.0,
                "composite:" + "+".join(sorted(f[2] for f in facts)))
    if rule_type == "aspect":
        if uncertain_time or not set(when["pair"]).issubset(bodies):
            return None
        pair = set(when["pair"])
        for aspect in chart.aspects:
            if {aspect.first, aspect.second} != pair or aspect.kind != when["kind"]:
                continue
            if (not math.isfinite(aspect.orb) or aspect.orb < 0
                    or aspect.orb > MAX_ORBS[aspect.kind]):
                continue
            first, second = when["pair"]
            calculated_orb = abs(short_separation(bodies[first].longitude,
                                                  bodies[second].longitude)
                                 - ASPECT_ANGLES[aspect.kind])
            if abs(calculated_orb - aspect.orb) > 0.02:
                continue  # Never trust an aspect contradicted by body positions.
            return (f"{aspect.first}–{aspect.second}: {aspect.kind}, "
                    f"סטייה {aspect.orb:.2f}°", max(.35, 1 - aspect.orb / 10),
                    "aspect:" + ":".join(sorted(pair)) + ":" + aspect.kind)
        return None
    body = bodies.get(when["body"])
    if (body is None or uncertain_time or body.house is None
            or body.house != when["house"]):
        return None
    return (f"{body.name} בבית {body.house} (Whole Sign)", 1.0,
            f"house:{body.name}:{body.house}")

def interpret_chart(chart, pack: RulePack | None = None) -> dict:
    """Deterministic symbolic reading; scores are editorial, not clinical."""
    if chart is None:
        raise ValueError("יש לחשב מפה לפני יצירת פרשנות")
    pack = pack or load_rulepack()
    bodies = {body.name: body for body in chart.bodies}
    estimated = any("שעת הלידה משוערת" in warning for warning in chart.warnings)
    uncertain_time = chart.approximate or estimated
    hits = []
    for rule in pack.rules:
        matched = _match(rule, chart, bodies, uncertain_time)
        if matched is None:
            continue
        evidence, reliability, fact_key = matched
        modifier_only = rule["type"] == "composite"
        hits.append(RuleHit(
            rule_id=rule["id"], axis=rule["axis"], polarity=rule["polarity"],
            weight=0.0 if modifier_only else round(float(rule["weight"]) * reliability, 3),
            text=rule["text"], evidence=evidence, source=rule["source"],
            provisional=uncertain_time,
            review_status=rule.get("review_status", "unverified"),
            evidence_key=rule.get("evidence_group", fact_key),
            source_url=(rule.get("source_detail") or {}).get("url"),
            modifier_only=modifier_only,
        ))
    hits.sort(key=lambda h: (h.axis, -h.weight, h.rule_id))
    axes = []
    for axis in sorted({h.axis for h in hits}):
        contributors = [h for h in hits if h.axis == axis]
        groups = {}
        for hit in contributors:
            if hit.modifier_only:
                continue
            group = groups.setdefault(hit.evidence_key, {"positive": [], "negative": []})
            group["positive" if hit.polarity > 0 else "negative"].append(hit)
        support = round(sum(max((h.weight for h in g["positive"]), default=0)
                            for g in groups.values()), 3)
        counter = round(sum(max((h.weight for h in g["negative"]), default=0)
                            for g in groups.values()), 3)
        same_fact_conflicts = [key for key, group in groups.items()
                               if group["positive"] and group["negative"]]
        axes.append({
            "axis": axis, "support": support, "counter": counter,
            "net": round(support - counter, 3),
            "has_tension": bool(support and counter),
            "tension_kind": ("same-fact-conflict" if same_fact_conflicts
                             else "different-facts" if support and counter else "none"),
            "source_conflict_keys": same_fact_conflicts,
            "independent_fact_count": len(groups),
            "duplicated_rule_count": sum(max(0, len(g["positive"]) - 1)
                                         + max(0, len(g["negative"]) - 1)
                                         for g in groups.values()),
            "modifier_rule_ids": [h.rule_id for h in contributors if h.modifier_only],
            "evidence_ids": [h.rule_id for h in contributors],
        })
    warnings = ["פרשנות אסטרולוגית סמלית לפי חבילת כללים עריכתית; אינה אבחון אופי מדעי."]
    if estimated:
        warnings.append("שעת הלידה משוערת: סימני מזל מוצגים באופן מותנה; "
                        "בתים והיבטים הושמטו; מיקומים סמוכי גבול הושמטו.")
    if chart.approximate:
        warnings.append("השעה אינה ידועה: דגימת אמצע היום אינה מעלת לידה; "
                        "נכללו רק מזלות יציבים בדגימות, ללא בתים או היבטים.")
        if any(len(b.signs_possible) > 1 for b in chart.bodies):
            warnings.append("דולגו פרשנויות מיקום של גופים שעשויים לעבור מזל במהלך היום.")
    if any(h.review_status in ("unverified", "conflicting") for h in hits):
        warnings.append("כללים מסוימים טרם אומתו פרטנית מול מקור; אין לייחס להם מעמד מאושר.")
    if not hits:
        warnings.append("אין מספיק התאמות לכללים בחבילה הנוכחית.")
    return {
        "schema_version": SCHEMA_VERSION, "pack_version": pack.version,
        "tradition": pack.tradition, "status": "symbolic-editorial",
        "time_uncertain": uncertain_time,
        "time_mode": "unknown" if chart.approximate else "estimated" if estimated else "known",
        "axes": axes, "signals": [asdict(hit) for hit in hits],
        "warnings": warnings,
    }

def format_interpretation(report: dict) -> str:
    """Readable digest; statements remain linked to their rule and chart fact."""
    lines = [
        "פרשנות אופי סמלית — לפי כללים אסטרולוגיים",
        f"גרסת כללים: {report['pack_version']}",
        "המשקלים הם סדרי עדיפות עריכתיים, לא מדידות או הסתברויות.",
        "",
    ]
    lookup = {hit["rule_id"]: hit for hit in report["signals"]}
    for axis in report["axes"]:
        lines.append(f"◆ {axis['axis']}")
        if axis["has_tension"]:
            lines.append("  קיימות השפעות סמליות בכיוונים שונים; אין מסקנה חד־משמעית.")
            if axis.get("source_conflict_keys"):
                lines.append("  חלק מהסתירה מקורו בכללים סותרים על אותה ראיה.")
        if axis.get("duplicated_rule_count"):
            lines.append("  כללים חופפים על אותה ראיה אינם נספרים כראיות עצמאיות.")
        for rule_id in axis["evidence_ids"]:
            hit = lookup[rule_id]
            lines.append(("  • השלמה מותנית: " if hit.get("modifier_only") else "  • ")
                         + hit["text"])
            lines.append(f"    בסיס: {hit['evidence']} | כלל {rule_id}"
                         f" | ביקורת: {hit.get('review_status', 'unverified')}")
        lines.append("")
    lines.extend(["הסתייגויות:", *(f"• {msg}" for msg in report["warnings"])])
    return "\n".join(lines)

def model_input(chart, report: dict) -> dict:
    """Local structured hand-off to an *optional* future model, never a request."""
    return {
        "schema_version": 1,
        "rule_pack_version": report["pack_version"],
        "tradition": report["tradition"],
        "chart_facts": {
            "bodies": [{
                "name": b.name, "longitude": None if report["time_uncertain"] else round(b.longitude, 5),
                "possible_signs": [SIGNS[s] for s in b.signs_possible] if chart.approximate
                                  else [b.sign],
                "house": None if report["time_uncertain"] else b.house,
                "sign_is_confirmed": not report["time_uncertain"],
                "longitude_is_sample": report["time_uncertain"],
            } for b in chart.bodies],
            "aspects": [] if report["time_uncertain"] else [{
                "first": a.first, "second": a.second, "kind": a.kind,
                "orb": round(a.orb, 3),
            } for a in chart.aspects
            if (a.first in {b.name for b in chart.bodies}
                and a.second in {b.name for b in chart.bodies}
                and a.kind in MAX_ORBS and math.isfinite(a.orb)
                and 0 <= a.orb <= MAX_ORBS[a.kind]
                and abs(abs(short_separation(
                    next(b.longitude for b in chart.bodies if b.name == a.first),
                    next(b.longitude for b in chart.bodies if b.name == a.second)
                ) - ASPECT_ANGLES[a.kind]) - a.orb) <= 0.02)],
            "time_uncertain": report["time_uncertain"],
            "time_mode": report["time_mode"],
        },
        "rule_evidence": report["signals"],
        "warnings": report["warnings"],
        "generation_constraints": {
            "do_not_invent_chart_facts": True,
            "interpretation_is_symbolic_not_diagnostic": True,
            "quote_rule_ids_for_claims": True,
            "do_not_treat_editorial_weights_as_probabilities": True,
        },
    }
