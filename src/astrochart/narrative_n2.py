"""N2 paragraph planning and offline Hebrew realization.

Each paragraph is a view over already attributed atomic semantic claims.
The realizer cannot add chart facts, independent evidence or discovered links.
"""
from __future__ import annotations

from .semantics_n2 import N2_SEMANTIC_VERSION

N2_NARRATIVE_VERSION = "0.1.0"


def _list_he(items: list[str]) -> str:
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " ו" + items[-1]


def _merge(section: str, kind: str, claims: list[dict], text: str) -> dict:
    def union(field: str) -> list[str]:
        return sorted({x for c in claims for x in c.get(field, [])})
    return {
        "kind": kind, "text": text, "section": section,
        "claim_ids": [c["id"] for c in claims],
        "classifications": union("classification") if False else
                           sorted({c["classification"] for c in claims}),
        "node_ids": union("node_ids"),
        "rule_ids": union("rule_ids"),
        "source_refs": union("source_refs"),
        "source_review_statuses": union("source_review_statuses"),
        "evidence_keys": union("evidence_keys"),
        "evidence_roots": union("evidence_roots"),
        "meaning_ids": union("meaning_ids"),
        "audit_statuses": sorted({c["audit_status"] for c in claims}),
        "provisional_time": any(c["provisional_time"] for c in claims),
    }


def _section(section_id: str, title: str, paragraphs: list[dict]) -> dict:
    return {"id": section_id, "title": title, "paragraphs": paragraphs}


class DeterministicHebrewRealizer:
    """Replaceable local-only surface adapter; source claims remain immutable."""

    def axis(self, claims: list[dict], index: int, *, secondary: bool) -> str:
        by_kind = {c["kind"]: c for c in claims}
        meaning = by_kind["axis-meaning"]["content"]
        example = by_kind["axis-example"]["content"]
        anchor = by_kind.get("rule-anchor")
        axis = meaning["axis"]
        definition = meaning["definition"].rstrip(".")
        situation, behavior = example["situation"], example["behavior"]
        strength = meaning["strength"].rstrip(".")
        challenge = meaning["challenge"].rstrip(".")
        if secondary:
            text = (
                f"עוד אפשרות העולה מן המפה היא {axis} — {definition}. "
                f"{situation}, {behavior}. "
                f"הצד המסייע עשוי להיות {strength}; בצד זאת ייתכן גם {challenge}.")
        elif index == 0:
            text = (
                f"מאפיין אפשרי מרכזי הוא {axis}: {definition}. "
                f"{situation}, {behavior}. "
                f"יש כאן פוטנציאל של {strength}, לצד קושי אפשרי של {challenge}.")
        elif index == 1:
            text = (
                f"{situation}, {behavior}. האפשרות הזו משתלבת בציר {axis}, "
                f"שמשמעותו {definition}. "
                f"הצד המועיל עשוי להיות {strength}; לעומתו, {challenge} "
                "עשוי להצריך תשומת לב.")
        else:
            text = (
                f"לא כל הדפוסים פועלים באותה צורה: {axis} מתייחס ל{definition}. "
                f"מצד אחד, {strength}. מצד אחר, {challenge}. "
                f"למשל, {situation}, {behavior}.")
        if anchor is not None:
            fact = anchor["content"]
            text += (
                f" העוגן במפה הוא {fact['chart_evidence']}; "
                f"הכלל הקיים מתאר זאת כך: {fact['rule_text'].rstrip('.')}."
            )
        if index == 0 and not secondary:
            text += (" בדומה לכך, " + example["recurrence_note"].rstrip(".")
                     + ". זו אפשרות לדפוס חוזר, לא תיאור של עברו או ניבוי לאירוע.")
        return text

    def process(self, claims: list[dict], index: int) -> str:
        by_kind = {c["kind"]: c for c in claims}
        reading = by_kind["process-reading"]["content"]
        example = by_kind["process-example"]["content"]
        path = reading["path"]
        actions = example["actions"]
        sequence = ", לאחר מכן ".join(actions)
        intro = ("מתוך הצירוף המסוים של הראיות במפה עולה גם אפשרות "
                 "לקריאה משולבת. " if index == 0 else
                 "צירוף נוסף שאפשר לבחון בנפרד: ")
        return (
            intro + f"{example['scenario']}, ייתכן מהלך של "
            + sequence + ". "
            + f"הצירים {_list_he(path)} מופיעים כמסלול ב־R1, "
            + "אך החיבור ביניהם הוא השערת סינתזה ולא כלל מאושר. "
            + "התרחיש מתאר כיצד הדבר *יכול* להיראות בחיי היום־יום; "
            + "אין ראיה שבעל המפה נהג כך בפועל."
            + ("" if reading["proof_search_complete"] else
               " חיפוש חלופות הראיות למסלול זה הוגבל.")
        )

    def tension(self, claims: list[dict]) -> str:
        item = claims[0]["content"]
        return (
            f"בעניין {item['axis']}, הראיות המקוריות מציגות שני כיוונים "
            "סמליים מנוגדים. ייתכן שאף אחד מהם אינו מתאר את בעל המפה, "
            "והמידע אינו מאפשר להכריע ביניהם או לייחס כל כיוון "
            "לנסיבות חיים מסוימות. לכן הסתירה נשארת פתוחה."
        )


def compose_narrative_n2(semantics: dict, *,
                         realizer: DeterministicHebrewRealizer | None = None) -> dict:
    """Translate a semantic plan into attributed paragraphs, without inference."""
    if (not isinstance(semantics, dict) or
            semantics.get("semantic_version") != N2_SEMANTIC_VERSION or
            not isinstance(semantics.get("claims"), list) or
            not isinstance(semantics.get("plan"), dict)):
        raise ValueError("נדרש מודל משמעות N2 תקין")
    realizer = realizer or DeterministicHebrewRealizer()
    claims = {c["id"]: c for c in semantics["claims"]}
    plan = semantics["plan"]
    sections = []
    primary, secondary, processes, tensions = [], [], [], []
    for i, ids in enumerate(plan["primary"]):
        group = [claims[c] for c in ids]
        primary.append(_merge("primary", "axis",
                              group, realizer.axis(group, i, secondary=False)))
    for i, ids in enumerate(plan["secondary"]):
        group = [claims[c] for c in ids]
        secondary.append(_merge("secondary", "axis",
                                group, realizer.axis(group, i, secondary=True)))
    for i, ids in enumerate(plan["processes"]):
        group = [claims[c] for c in ids]
        processes.append(_merge("processes", "process",
                                group, realizer.process(group, i)))
    for ids in plan["tensions"]:
        group = [claims[c] for c in ids]
        paragraph = _merge("tensions", "unresolved-tension",
                           group, realizer.tension(group))
        paragraph["evidence_by_polarity"] = group[0]["evidence_by_polarity"]
        tensions.append(paragraph)
    if primary:
        sections.append(_section("primary", "נטיות בולטות בקריאה הסמלית", primary))
    if secondary:
        sections.append(_section("secondary", "נטיות נוספות", secondary))
    if processes:
        sections.append(_section("processes", "כיצד נטיות עשויות להשתלב", processes))
    if tensions:
        sections.append(_section("tensions", "היכן הראיות אינן מכריעות", tensions))
    if not (primary or secondary or processes or tensions):
        sections.append(_section("limited", "גבולות המידע", [{
            "kind": "no-supported-claims",
            "text": "אין די בצמתי R1 בעלי ראיות מתאימות כדי לתאר דפוס אישיותי. "
                    "המערכת אינה משלימה את החסר בתיאור כללי.",
            "claim_ids": [], "classifications": [],
            "node_ids": [], "rule_ids": [], "source_refs": [],
            "source_review_statuses": [], "evidence_keys": [],
            "evidence_roots": [], "meaning_ids": [],
            "audit_statuses": ["insufficient-evidence"],
            "provisional_time": semantics["time_mode"] != "known",
            "section": "limited",
        }]))
    statuses = sorted({c for p in primary + secondary + processes + tensions
                       for c in p["source_review_statuses"]})
    disclosure = (
        "מדובר בפרשנות אסטרולוגית סמלית ובתרחישי התנהגות אפשריים, "
        "לא במדידה מדעית או באבחון אישיות. דוגמאות החיים הן הרחבות "
        "עריכתיות שטרם אומתו, והן אינן מוסיפות כללים או ראיות למפה. "
        "קשרים בין צירים הם השערות של R1 בלבד.")
    if "unverified" in statuses:
        disclosure += " בין הכללים המוצגים יש כללים שטרם אומתו."
    if "reviewed" in statuses:
        disclosure += " חלק מן הכללים נבדקו, אך לא אושרו."
    if "approved" in statuses:
        disclosure += " יש כללים בודדים שמסומנים מאושרים; אין בכך אישור להרחבות."
    if "conflicting" in statuses:
        disclosure += " בחלק מן המקורות נותרו אי־הסכמות."
    mode = semantics["time_mode"]
    if mode == "unknown":
        disclosure += (" שעת הלידה אינה ידועה; דגימת אמצע היום אינה "
                       "ראיה למעלות, לבתים או להיבטים מדויקים.")
    elif mode == "estimated":
        disclosure += (" שעת הלידה משוערת; לא נלקחו מן הדגימה "
                       "טענות על בתים או היבטים מדויקים.")
    sections.append(_section("limits", "כיצד לקרוא את התיאור", [{
        "kind": "disclosure", "text": disclosure, "section": "limits",
        "claim_ids": [], "classifications": ["editorial-disclosure"],
        "node_ids": [], "rule_ids": [], "source_refs": [],
        "source_review_statuses": statuses, "evidence_keys": [],
        "evidence_roots": [], "meaning_ids": [],
        "audit_statuses": ["editorial-disclosure"],
        "provisional_time": mode != "known",
    }]))
    return {
        "schema_version": 1, "narrative_version": N2_NARRATIVE_VERSION,
        "source_semantic_version": semantics["semantic_version"],
        "source_engine_version": semantics["source_engine_version"],
        "source_rule_pack": semantics["source_rule_pack"],
        "time_mode": mode, "mode": "local-deterministic-attributed-hebrew",
        "sections": sections, "warnings": list(semantics["warnings"]),
    }


def format_narrative_n2(report: dict) -> str:
    if not isinstance(report, dict) or not isinstance(report.get("sections"), list):
        raise ValueError("נדרש דוח N2 מובנה")
    parts = ["פרשנות אישית (N2) — קריאה אסטרולוגית סמלית"]
    for section in report["sections"]:
        parts.append(section["title"])
        parts.extend(p["text"] for p in section["paragraphs"])
    return "\n\n".join(parts)
