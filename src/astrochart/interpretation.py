"""Versioned, auditable symbolic interpretation of computed chart facts.

This is NOT psychological diagnosis or empirically validated personality scoring.
Rules are editorial statements, not natural laws. The engine has no network calls,
no arbitrary rule evaluation, no automatic self-modification, and no LLM runtime.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .domain import BODIES, SIGNS, degree_in_sign

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
    if not rule["enabled"]:
        return
    if (rule.get("type") not in ("placement", "aspect", "house")
            or not isinstance(rule.get("axis"), str)
            or not 2 <= len(rule["axis"]) <= 32
            or any(ord(ch) < 32 for ch in rule["axis"])
            or type(rule.get("polarity")) is not int
            or rule["polarity"] not in (-1, 1)
            or type(rule.get("weight")) not in (float, int)
            or not 0 < rule["weight"] <= 5):
        raise RulePackError("תנאי, ציר או משקל כלל אינם תקינים: " + rule["id"])
    for field in ("text", "source"):
        if (not isinstance(rule.get(field), str) or
                not 5 <= len(rule[field]) <= 350):
            raise RulePackError("חסר תיאור או מקור עריכתי בכלל " + rule["id"])
    when = rule.get("when")
    if not isinstance(when, dict):
        raise RulePackError("שדה when חסר בכלל " + rule["id"])
    if rule["type"] == "placement":
        if (set(when) != {"body", "sign"} or
                when["body"] not in BODIES or when["sign"] not in SIGNS):
            raise RulePackError("כלל מיקום בלתי מוכר: " + rule["id"])
    elif rule["type"] == "house":
        if (set(when) != {"body", "house"} or
                when["body"] not in BODIES or
                type(when["house"]) is not int or not 1 <= when["house"] <= 12):
            raise RulePackError("כלל בית בלתי מוכר: " + rule["id"])
    else:
        if (set(when) != {"pair", "kind"} or
                not isinstance(when["pair"], list) or len(when["pair"]) != 2 or
                not all(isinstance(body, str) for body in when["pair"]) or
                len(set(when["pair"])) != 2 or
                any(body not in BODIES for body in when["pair"]) or
                when["kind"] not in ASPECT_KINDS):
            raise RulePackError("כלל היבט בלתי מוכר: " + rule["id"])


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


def _match(rule, chart, bodies, uncertain_time):
    when = rule["when"]
    rule_type = rule["type"]
    if rule_type == "aspect":
        if uncertain_time:
            return None  # Midpoint aspects are not natal birth-time facts.
        pair = set(when["pair"])
        for aspect in chart.aspects:
            if {aspect.first, aspect.second} == pair and aspect.kind == when["kind"]:
                if not all(b in bodies for b in pair):
                    return None
                return (f"{aspect.first}–{aspect.second}: {aspect.kind}, "
                        f"סטייה {aspect.orb:.2f}°", max(.35, 1.0 - aspect.orb / 10))
        return None
    body = bodies.get(when["body"])
    if body is None:
        return None
    if rule_type == "house":
        if uncertain_time or body.house is None or body.house != when["house"]:
            return None
        return (f"{body.name} בבית {body.house}", 1.0)
    possible = body.signs_possible
    # A birth day with multiple candidate signs cannot support a single
    # placement claim. Stable signs can still be described conditionally.
    if chart.approximate and (not possible or len(possible) != 1):
        return None
    if body.sign != when["sign"]:
        return None
    return (f"{body.name} במזל {body.sign} ({degree_in_sign(body.longitude):.2f}°"
            + (" — שעה לא ידועה)" if chart.approximate else ")"), 1.0)


def interpret_chart(chart, pack: RulePack | None = None) -> dict:
    """Deterministic, evidence-backed signals; all scores are editorial weights."""
    if chart is None:
        raise ValueError("יש לחשב מפה לפני יצירת פרשנות")
    pack = pack or load_rulepack()
    bodies = {body.name: body for body in chart.bodies}
    approximate_hour = any("שעת הלידה משוערת" in warning for warning in chart.warnings)
    uncertain_time = chart.approximate or approximate_hour
    hits = []
    for rule in pack.rules:
        matched = _match(rule, chart, bodies, uncertain_time)
        if matched is None:
            continue
        evidence, reliability = matched
        hits.append(RuleHit(
            rule_id=rule["id"], axis=rule["axis"], polarity=rule["polarity"],
            weight=round(float(rule["weight"]) * reliability, 3),
            text=rule["text"], evidence=evidence, source=rule["source"],
            provisional=uncertain_time,
        ))
    hits.sort(key=lambda h: (h.axis, -h.weight, h.rule_id))
    axes = []
    for axis in sorted({h.axis for h in hits}):
        contributors = [h for h in hits if h.axis == axis]
        support = round(sum(h.weight for h in contributors if h.polarity > 0), 3)
        counter = round(sum(h.weight for h in contributors if h.polarity < 0), 3)
        axes.append({
            "axis": axis,
            "support": support,
            "counter": counter,
            "net": round(support - counter, 3),
            "has_tension": bool(support and counter),
            "evidence_ids": [h.rule_id for h in contributors],
        })
    warnings = [
        "פרשנות אסטרולוגית סמלית לפי חבילת כללים עריכתית; אינה אבחון אופי מדעי."
    ]
    if uncertain_time:
        warnings.append(
            "השעה אינה ודאית: לא הוסקו משמעויות מבתים או מהיבטים תלויי־שעה; "
            "אין להציג השערות כעובדות.")
    if chart.approximate and any(len(b.signs_possible) > 1 for b in chart.bodies):
        warnings.append("דולגו פרשנויות מיקום של גופים שעשויים לעבור מזל במהלך היום.")
    if not hits:
        warnings.append("אין מספיק התאמות לכללים בחבילה הנוכחית.")
    return {
        "schema_version": SCHEMA_VERSION,
        "pack_version": pack.version,
        "tradition": pack.tradition,
        "status": "symbolic-editorial",
        "time_uncertain": uncertain_time,
        "axes": axes,
        "signals": [asdict(hit) for hit in hits],
        "warnings": warnings,
    }


def format_interpretation(report: dict) -> str:
    """Readable Hebrew digest without inventing unstated character claims."""
    lines = [
        "פרשנות אופי סמלית — לפי כללים אסטרולוגיים",
        f"גרסת כללים: {report['pack_version']}",
        "משקלות אלה אינם ציוני אישיות מאומתים.",
        "",
    ]
    lookup = {h["rule_id"]: h for h in report["signals"]}
    for axis in report["axes"]:
        lines.append(f"◆ {axis}")
        if axis["has_tension"]:
            lines.append("  קיימות השפעות סמליות בכיוונים שונים; אין מסקנה חד־משמעית.")
        for rule_id in axis["evidence_ids"]:
            hit = lookup[rule_id]
            lines.append(f"  • {hit['text']}")
            lines.append(f"    בסיס: {hit['evidence']} | כלל {rule_id}")
        lines.append("")
    lines.extend(["הסתייגויות:", *(f"• {text}" for text in report["warnings"])])
    return "\n".join(lines)


def model_input(chart, report: dict) -> dict:
    """Local structured hand-off to an *optional* future model, never a request."""
    return {
        "schema_version": 1,
        "rule_pack_version": report["pack_version"],
        "tradition": report["tradition"],
        "chart_facts": {
            "bodies": [{
                "name": b.name, "longitude": round(b.longitude, 5),
                "possible_signs": [SIGNS[s] for s in b.signs_possible] if chart.approximate
                                  else [b.sign],
                "house": None if report["time_uncertain"] else b.house,
            } for b in chart.bodies],
            "aspects": [] if report["time_uncertain"] else [{
                "first": a.first, "second": a.second, "kind": a.kind,
                "orb": round(a.orb, 3),
            } for a in chart.aspects],
            "time_uncertain": report["time_uncertain"],
        },
        "rule_evidence": report["signals"],
        "warnings": report["warnings"],
        "generation_constraints": {
            "do_not_invent_chart_facts": True,
            "interpretation_is_symbolic_not_diagnostic": True,
            "quote_rule_ids_for_claims": True,
        },
    }
