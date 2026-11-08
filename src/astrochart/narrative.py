"""N1: deterministic, read-only Hebrew narrative over an audited R1 report.

This module is a *realizer*, not a new interpretation or inference engine.
It must never turn hypothesis paths into verified claims, promote sources,
resolve unsupported contexts, invent chart positions, or alter R1 evidence.
No model, network, external assets or third-party dependencies are used.
"""
from __future__ import annotations

NARRATIVE_VERSION = "0.1.0"
MAX_PROCESS_PARAGRAPHS = 3
MAX_STANDALONE_AXES = 4


def _hebrew_list(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return values[0] + " ו" + values[1]
    return ", ".join(values[:-1]) + " ו" + values[-1]


def _paragraph(kind: str, text: str, *, node: dict | None = None,
               node_ids: list[str] | None = None,
               rule_ids: list[str] | None = None,
               provisional: bool = False) -> dict:
    """Every substantive claim has its originating R1 node or rule IDs."""
    if node is not None:
        node_ids = [node["id"]]
        rule_ids = node.get("rule_ids", [])
        provisional = bool(node.get("provisional_time"))
    return {
        "kind": kind,
        "text": text,
        "node_ids": list(node_ids or []),
        "rule_ids": sorted(set(rule_ids or [])),
        "source_refs": sorted(set(node.get("source_refs", []))) if node else [],
        "source_review_statuses": (
            sorted(set(node.get("source_review_statuses", []))) if node else []),
        "audit_status": node.get("audit_status") if node else (
            "unresolved" if kind == "tension" else "editorial-disclosure"),
        "provisional_time": provisional,
    }


def _section(section_id: str, title: str, paragraphs: list[dict]) -> dict:
    return {"id": section_id, "title": title, "paragraphs": paragraphs}


def compose_narrative(synthesis: dict) -> dict:
    """Plan natural-language paragraphs using *only* evidence already in R1.

    Selection uses the existing R1 top/summary ordering. Every paragraph
    retains its node and rule IDs, preserving auditability without treating
    R1's editorial weights as probabilities or psychological measurements.
    """
    if (not isinstance(synthesis, dict)
            or not isinstance(synthesis.get("nodes"), list)
            or not isinstance(synthesis.get("summary"), dict)):
        raise ValueError("נדרש דוח סינתזה R1 מובנה")

    nodes = {n["id"]: n for n in synthesis["nodes"] if isinstance(n, dict)
             and isinstance(n.get("id"), str)}
    time_mode = synthesis.get("time_mode", "unknown")
    if time_mode not in ("known", "estimated", "unknown"):
        raise ValueError("מצב שעת לידה אינו מוכר")

    opening = ("זוהי קריאה סמלית המבוססת על כללי המפה ועל מסקנות מנוע R1. "
               "היא אינה אבחון אישיות מדעי, ומשקלי הכללים אינם הסתברויות.")
    if time_mode == "estimated":
        opening += (" שעת הלידה משוערת: פרשנות בתים והיבטים אינה נגזרת "
                    "מן השעה המשוערת, וכל מסקנה תלויה במידע הזמין.")
    elif time_mode == "unknown":
        opening += (" שעת הלידה אינה ידועה: מיקומי דגימה אינם משמשים "
                    "ראיות לבתים או להיבטים, והמסקנות זמניות.")

    sections = [_section("opening", "הקדמה", [
        _paragraph("disclosure", opening, provisional=time_mode != "known")
    ])]

    # R1 has already de-duplicated contiguous subpaths in this list.
    # Do not infer additional paths or choose an unapproved relation here.
    eligible = []
    seen = set()
    for node_id in synthesis["summary"].get("top_hypotheses", []):
        node = nodes.get(node_id)
        if (node is None or node_id in seen or node.get("type") != "synthesis"
                or node.get("audit_status") != "hypothesis"
                or len(node.get("path", [])) < 2
                or len(node.get("independent_facts", [])) != len(node["path"])
                or not node.get("rule_ids")):
            continue
        seen.add(node_id)
        eligible.append(node)

    selected = eligible[:MAX_PROCESS_PARAGRAPHS]
    process_paragraphs = []
    for node in selected:
        path = node["path"]
        if len(path) == 2:
            text = (f"במישור {node['domain']}, הראיות מאפשרות להציע חיבור "
                    f"סמלי בין {path[0]} לבין {path[1]}. ")
        else:
            text = (f"במישור {node['domain']}, אפשר להציע רצף סמלי "
                    f"המחבר את {_hebrew_list(path)}. ")
        text += ("לפי מסגרת ההסקה של R1, הרצף נשען על "
                 f"{len(node['independent_facts'])} ראיות נפרדות. "
                 "הקשר התפקודי ביניהן הוא השערה של המודל, "
                 "ולא כלל פרשנות שאושר בפני עצמו.")
        if node.get("provisional_time"):
            text += " יש לקרוא זאת בזהירות בשל אי־הוודאות בשעת הלידה."
        if not node.get("proof_search", {}).get("complete", True):
            text += " חיפוש החלופות הוגבל ולכן אין זו סקירה ממצה."
        process_paragraphs.append(_paragraph("process", text, node=node))

    if not process_paragraphs:
        process_paragraphs.append(_paragraph(
            "no-process",
            "בנתונים שהמנוע בדק לא נמצאה שרשרת מאפיינים מורכבת "
            "בעלת תמיכה בראיות עצמאיות. אין להסיק מכך שלא קיימים "
            "קשרים אפשריים מחוץ למאגר ולמסלולים שנבדקו."
        ))
    sections.append(_section("processes", "תמונה משולבת", process_paragraphs))

    # Avoid reciting axes already explained as parts of the displayed paths.
    covered_axes = {axis for node in selected for axis in node["path"]}
    tensions = synthesis.get("tensions", [])
    tension_axes = {t["axis"] for t in tensions}
    by_axis = {n.get("axis"): n for n in synthesis["nodes"]
               if n.get("type") == "axis"}
    axis_paragraphs = []
    seen_axes = set()
    for axis in synthesis["summary"].get("leading_axes", []):
        if axis in covered_axes or axis in tension_axes or axis in seen_axes:
            continue
        node = by_axis.get(axis)
        if node is None or not node.get("independent_facts"):
            continue
        seen_axes.add(axis)
        text = (f"בנפרד מן הרצפים שתוארו, כללי המפה מצביעים במסגרת "
                f"המילון הסמלי על הציר {axis}. זהו תיאור של הממצאים "
                "במאגר, ולא קביעה מדעית על אדם.")
        if node.get("provisional_time"):
            text += " המסקנה זמנית בשל אי־הוודאות בשעה."
        axis_paragraphs.append(_paragraph("axis", text, node=node))
        if len(axis_paragraphs) >= MAX_STANDALONE_AXES:
            break
    if axis_paragraphs:
        sections.append(_section("axes", "מאפיינים נוספים", axis_paragraphs))

    tension_paragraphs = []
    for tension in tensions:
        if tension.get("status") != "unresolved":
            continue
        axis = tension["axis"]
        rules = tension.get("positive_rule_ids", []) + tension.get("negative_rule_ids", [])
        text = (f"בציר {axis} קיימות ראיות פרשניות לכיוונים שונים. "
                "הנתונים אינם קובעים מהן הנסיבות שבהן כל כיוון יתבטא, "
                "ולכן המתח נשאר בלתי מוכרע; אין להעדיף אחד מהם ללא מקור נוסף.")
        tension_paragraphs.append(_paragraph(
            "tension", text, rule_ids=rules, provisional=time_mode != "known"))
    if tension_paragraphs:
        sections.append(_section("tensions", "מתחים שלא הוכרעו", tension_paragraphs))

    warnings = list(synthesis.get("warnings", []))
    if warnings:
        sections.append(_section("cautions", "הסתייגויות ושיטת העבודה", [
            _paragraph("warning", warning, provisional=time_mode != "known")
            for warning in warnings
        ]))

    report = {
        "schema_version": 1,
        "narrative_version": NARRATIVE_VERSION,
        "source_engine_version": synthesis.get("engine_version"),
        "source_profile_id": synthesis.get("profile_id"),
        "source_rule_pack": synthesis.get("source_rule_pack"),
        "time_mode": time_mode,
        "mode": "deterministic-read-only-renderer",
        "sections": sections,
        "displayed_hypothesis_ids": [n["id"] for n in selected],
        "not_displayed_hypothesis_ids": [n["id"] for n in eligible[len(selected):]],
        "warnings": warnings,
    }
    return report


def format_narrative(narrative: dict) -> str:
    """Human-readable top-down text; structured provenance is unchanged."""
    if not isinstance(narrative, dict) or "sections" not in narrative:
        raise ValueError("נדרש דוח ניסוח מובנה")
    parts = ["קריאה רציפה — פרשנות סמלית (N1)"]
    for section in narrative["sections"]:
        parts.append("")
        parts.append(section["title"])
        parts.extend(p["text"] for p in section["paragraphs"])
    if narrative.get("not_displayed_hypothesis_ids"):
        parts.extend(["", "נבחרו רק התהליכים המובילים לקריאה זו; "
                      "יתר שרשראות ההסקה זמינות בכרטיסיית הסינתזה והראיות."])
    return "\n\n".join(part for part in parts if part != "")
