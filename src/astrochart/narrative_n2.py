"""Offline Hebrew realization from verified, rule-conditioned N2 claims.

Rendered paragraphs keep evidence quotations in a separate evidence_text field.
semantic_text is the report's meaning, excluding citations and fixed disclosures:
it is the correct target for differential acceptance and duplicate tests.
"""
from __future__ import annotations

from .semantics_n2 import N2_SEMANTIC_VERSION

N2_NARRATIVE_VERSION = "0.2.0"
STATUS_HE = {
    "unverified": "טרם אומת", "reviewed": "נבדק, לא אושר",
    "approved": "מאושר בכלל המקורי בלבד",
    "conflicting": "מקור שנוי במחלוקת",
    "rejected": "נדחה",
}


def _he_list(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " ו" + items[-1]


def _source_line(item: dict) -> str:
    x = item["content"]
    # A selected rule has its own status and URL. Group-wide union statuses
    # are lineage metadata only; never attribute another rule's status to it.
    status_text = STATUS_HE.get(x["review_status"], x["review_status"])
    source = x.get("selected_source_url") or "מקור שלא סופקה לו כתובת"
    return (f"{x['chart_evidence']} — כלל {x['selected_rule_id']} "
            f"({status_text}); מקור: {source}; נוסח הכלל: {x['rule_text']}")


def _merge(section: str, kind: str, claims: list[dict], semantic: str,
           evidence: str = "") -> dict:
    def union(field: str) -> list[str]:
        return sorted({x for c in claims for x in c.get(field, [])})
    return {
        "kind": kind,
        "text": semantic + ("\n" + evidence if evidence else ""),
        "semantic_text": semantic,
        "evidence_text": evidence,
        "section": section,
        "claim_ids": [c["id"] for c in claims],
        "classifications": sorted({c["classification"] for c in claims}),
        "node_ids": union("node_ids"), "rule_ids": union("rule_ids"),
        "source_refs": union("source_refs"),
        "source_review_statuses": union("source_review_statuses"),
        "evidence_keys": union("evidence_keys"),
        "evidence_roots": union("evidence_roots"),
        "meaning_ids": union("meaning_ids"),
        "audit_statuses": sorted({c["audit_status"] for c in claims}),
        "provisional_time": any(c["provisional_time"] for c in claims),
    }


def _section(name: str, title: str, paragraphs: list[dict]) -> dict:
    return {"id": name, "title": title, "paragraphs": paragraphs}


class DeterministicHebrewRealizer:
    """Presentation adapter only: no free-form link mining or guessed context."""

    def axis(self, claims: list[dict], index: int, *,
             secondary: bool) -> tuple[str, str]:
        meaning = next(c for c in claims if c["kind"] == "axis-meaning")["content"]
        anchors = [c for c in claims if c["kind"] == "rule-anchor"]
        examples = [c["content"] for c in claims if c["kind"] == "axis-example"]
        axis = meaning["axis"]
        count = meaning["independent_evidence_count"]
        evidence = "ראיות הכללים שנבחרו ב־R1:\n" + "\n".join(
            "• " + _source_line(a) for a in anchors)
        if not examples:
            text = (
                f"המפה מציגה ראיות לציר {axis}, אך במאגר N2 אין עדיין "
                "משמעות התנהגותית ייחודית ומבוססת־כלל עבור הראיות שנבחרו. "
                "לכן אין להסיק מהן תרחיש חיים מפורט. "
                f"ההגדרה הכללית של הציר היא {meaning['definition']}.")
            return text, evidence
        if len(examples) == 1:
            e = examples[0]
            if e["evidence_type"] == "house":
                intro = f"בקריאה זו ציר {axis} מופיע דרך סמליות של בית: "
            elif e["evidence_type"] == "aspect":
                intro = f"כאן ציר {axis} נקשר להיבט אסטרולוגי קיים: "
            else:
                intro = (f"נקודת המוצא לציר {axis} היא " if index == 0
                         else f"בציר {axis} ניכר דגש מסוים: ")
            text = (intro + e["focus"] + ". "
                    + f"{e['situation']}, בעל המפה {e['behavior']}. "
                    + e["distinction"] + ". "
                    + e["limit"] + ".")
            if count > 1:
                text += (f" ל־R1 נבחרו {count} קבוצות ראיה עצמאיות לציר הזה; "
                         "רק זו שתוארה כאן כוללת הרחבה התנהגותית מבוקרת במאגר.")
            return text, evidence
        phrases = [
            f"{e['focus']} (ראיה {i+1})" for i, e in enumerate(examples)]
        detail = "; ".join(e["distinction"] for e in examples)
        shown = examples[:2]
        situations = "; ".join(
            f"{e['situation']}, בעל המפה {e['behavior']}" for e in shown)
        text = (
            f"מתוך {count} קבוצות ראיה עצמאיות לציר {axis}, "
            f"ל־{len(examples)} יש פירוש עריכתי תלוי־כלל: "
            + "; ".join(phrases) + ". "
            + "ההבחנות בין המשמעויות הן: " + detail + ". "
            + f"לשם המחשה בלבד מובאות {len(shown)} דוגמאות התנהגות נפרדות: "
            + situations + ". "
            + "הדוגמאות אינן ממצות את כלל הראיות או מוכיחות "
              "שהתיאורים מתקיימים יחד."
        )
        if count > len(examples):
            text += (f" ל־{count - len(examples)} קבוצות ראיה נוספות "
                     "אין פירוש התנהגותי ייחודי במאגר.")
        return text, evidence

    def process(self, claims: list[dict], index: int) -> tuple[str, str]:
        reading = next(c for c in claims if c["kind"] == "process-reading")["content"]
        plan = reading["content_plan"]
        path, slots = plan["path"], reading["slots"]
        compare = next((c for c in claims if c["kind"] == "process-example"), None)
        evidence = "ראיות המסלול שנבחרו ב־R1:\n" + "\n".join(
            f"• {slot['axis']}: {slot['witness']['evidence']} "
            f"(כלל {slot['witness']['rule_id']}; "
            f"{STATUS_HE.get(slot['witness']['review_status'], slot['witness']['review_status'])}; "
            f"מקור: {slot['witness']['source_url'] or 'לא צוין'})"
            for slot in slots)
        coverage = plan["coverage"]
        if compare is None:
            return (f"מסלול R1 {_he_list(path)} הושאר ללא השוואה פרשנית: "
                    "אין די במשמעויות מובחנות ומתועדות לכללים שנבחרו. "
                    "המסלול מתועד ב־JSON אך אין הצדקה להשלים את פעריו.", evidence)
        components = compare["content"]["components"]
        missing = coverage["missing_members"]
        positions = [f"{x['axis']}: {x['focus']}" for x in components]
        if missing:
            opening = (
                f"מסלול R1 המלא הוא {' → '.join(path)}. "
                f"זוהי השוואה חלקית בלבד: {len(components)} מתוך "
                f"{len(path)} רכיבי המסלול מכוסים בפירוש עריכתי "
                f"({_he_list([x['axis'] for x in components])}); "
                f"לרכיבים {_he_list([x['axis'] for x in missing])} "
                "אין עדיין משמעות תלויה בכלל שנבחר. ")
        else:
            opening = (
                f"במסלול R1 {' → '.join(path)} כל {len(path)} הרכיבים "
                "מכוסים בפירוש עריכתי, אך עצם הרצף הוא השערה. ")
        evidence_count = "שלוש ראיות" if len(components) == 3 else (
            "שתי הראיות" if len(components) == 2 else "ראיות נבחרות")
        text = opening + evidence_count + " מצביעות על מוקדים שונים: "
        text += "; ".join(positions) + ". "
        text += ("ההבדל ביניהן אינו רק בשם הציר אלא גם בזירת ההמחשה: "
                 + "; ".join(f"{c['axis']} — {c['setting']}" for c in components)
                 + ". ")
        # Role-sensitive composition uses actual contextual readings, not
        # fabricated co-occurrence. No new behavioral proposition is asserted.
        if not missing:
            text += (
                "בקריאה משולבת וזהירה אפשר להחזיק את השאלות בנפרד, "
                "לפי סדר המסלול: "
                + "; ".join(
                    f"ב{c['axis']} מה ניתן לתאר באמצעות {c['focus']}"
                    for c in components)
                + ". אין זה סיפור על מעשים שהתרחשו ברצף. ")
        else:
            text += ("ההשוואה מתייחסת רק לרכיבים המכוסים, "
                     "ולא מסבירה את המסלול המלא. ")
        text += ("גם גבולות ההסקה שונים: "
                 + "; ".join(f"{c['axis']} — {c['limit']}" for c in components)
                 + ". ")
        text += ("המשמעויות המתועדות מאפשרות להבחין בדגשים; "
                 "הן אינן מוכיחות שהדגשים פועלים יחד, מחזקים זה את זה "
                 "או שאחד גורם לאחר.")
        if not reading["proof_search_complete"]:
            text += " חיפוש החלופות למסלול הוגבל."
        return text, evidence

    def tension(self, claims: list[dict]) -> tuple[str, str]:
        item = claims[0]["content"]
        def describe(witnesses):
            return "\n".join(
                f"• {x['evidence']} — כלל {x['rule_id']} "
                f"({STATUS_HE.get(x['review_status'], x['review_status'])}); "
                f"מקור: {x['source_url'] or 'לא צוין'}; "
                f"נוסח הכלל: {x['text']}"
                for x in witnesses)
        evidence = (
            "ראיות לכיוון החיובי:\n" + describe(item["positive_witnesses"])
            + "\nראיות לכיוון המנוגד:\n"
            + describe(item["negative_witnesses"]))
        text = (
            f"לציר {item['axis']} נבחרו ב־R1 ראיות לשני כיוונים מנוגדים. "
            "הכללים והמקורות של שני הצדדים מוצגים בנפרד. "
            "המידע אינו מאפשר להכריע ביניהם, לייחס כל כיוון "
            "לנסיבות חיים מסוימות או לייחס לבעל המפה התנהגות בפועל.")
        return text, evidence


def compose_narrative_n2(semantics: dict, *,
                         realizer: DeterministicHebrewRealizer | None = None) -> dict:
    if (not isinstance(semantics, dict)
            or semantics.get("semantic_version") != N2_SEMANTIC_VERSION
            or not isinstance(semantics.get("claims"), list)
            or not isinstance(semantics.get("plan"), dict)):
        raise ValueError("נדרש מודל משמעות N2 תקין")
    realizer = realizer or DeterministicHebrewRealizer()
    claims = {c["id"]: c for c in semantics["claims"]}
    plan = semantics["plan"]
    primary, secondary, processes, tensions = [], [], [], []
    for name, target in (("primary", primary), ("secondary", secondary)):
        for index, ids in enumerate(plan[name]):
            group = [claims[i] for i in ids]
            semantic, evidence = realizer.axis(group, index, secondary=name == "secondary")
            target.append(_merge(name, "axis", group, semantic, evidence))
    abstained = []
    for index, ids in enumerate(plan["processes"]):
        group = [claims[i] for i in ids]
        content = next(c for c in group if c["kind"] == "process-reading")["content"]
        content_plan = content["content_plan"]
        has_comparison = any(c["kind"] == "process-example" for c in group)
        if not has_comparison:
            abstained.append((group, content_plan))
            continue
        semantic, evidence = realizer.process(group, index)
        p = _merge("processes", "process", group, semantic, evidence)
        p["process_content_plan"] = content_plan
        processes.append(p)
    abstained_paths = [{
        "path": cp["path"], "coverage": cp["coverage"],
        "node_ids": sorted({n for c in group for n in c["node_ids"]}),
        "claim_ids": [c["id"] for c in group],
        "rule_ids": sorted({r for c in group for r in c["rule_ids"]}),
        "reason": "insufficient-distinct-rule-meanings",
    } for group, cp in abstained]
    if abstained:
        all_claims = [c for group, _ in abstained for c in group]
        names = [" → ".join(cp["path"]) for _, cp in abstained]
        summary = (
            f"אותרו {len(abstained)} מסלולים נוספים ב־R1 "
            f"({_he_list(names)}), אך אין עדיין די במשמעויות מובחנות "
            "ומתועדות כדי להסביר אותם. לא הוסקו מהם קשרים התנהגותיים. "
            "פירוט כל רכיב חסר וכל ראיה שנבחרה נשמר ב־JSON.")
        evidence = "\n".join(
            f"• {' → '.join(cp['path'])}: "
            + "; ".join(
                f"{m['axis']} — כלל {m['selected_rule_id']}"
                + (" (ללא פירוש עריכתי)" if not m["meaning_covered"] else "")
                for m in cp["members"])
            for _, cp in abstained)
        p = _merge("processes", "process-abstention", all_claims, summary, evidence)
        p["abstained_paths"] = abstained_paths
        processes.append(p)
    for ids in plan["tensions"]:
        group = [claims[i] for i in ids]
        semantic, evidence = realizer.tension(group)
        p = _merge("tensions", "unresolved-tension", group, semantic, evidence)
        p["evidence_by_polarity"] = group[0]["evidence_by_polarity"]
        tensions.append(p)
    sections = []
    if primary:
        sections.append(_section("primary", "משמעויות התלויות בכללי המקור", primary))
    if secondary:
        sections.append(_section("secondary", "דגשים נוספים והבדלים בין ראיות", secondary))
    if processes:
        sections.append(_section("processes", "צירוף דגשים במסלול קיים של R1", processes))
    if tensions:
        sections.append(_section("tensions", "סתירות שלא הוכרעו", tensions))
    if not (primary or secondary or processes or tensions):
        sections.append(_section("limited", "גבולות המידע", [{
            "kind": "no-supported-claims",
            "text": "אין די בצמתי R1 בעלי ראיות מתאימות כדי לתאר דפוס אישיותי. "
                    "המערכת אינה משלימה את החסר בתיאור כללי.",
            "semantic_text": "אין די בראיות מתאימות לתיאור דפוס.",
            "evidence_text": "", "section": "limited", "claim_ids": [],
            "classifications": [], "node_ids": [], "rule_ids": [],
            "source_refs": [], "source_review_statuses": [], "evidence_keys": [],
            "evidence_roots": [], "meaning_ids": [],
            "audit_statuses": ["insufficient-evidence"],
            "provisional_time": semantics["time_mode"] != "known",
        }]))
    statuses = sorted({status for p in primary + secondary + processes + tensions
                       for status in p["source_review_statuses"]})
    disclosure = (
        "זו קריאה אסטרולוגית סמלית, לא בדיקת אישיות מדעית או תיאור ביוגרפי. "
        "הרחבות ההתנהגות במאגר N2 הן דוגמאות עריכתיות שלא אומתו, "
        "והן אינן כללים אסטרולוגיים חדשים. מסלולי R1 הם השערות תפקודיות "
        "בלבד; אין להסיק מהם סיבתיות או קשרים אישיותיים מאושרים.")
    unexpanded = semantics.get("unexpanded_axis_names", [])
    if unexpanded:
        disclosure += (
            " לא נוצר תיאור התנהגותי מפורט לצירים "
            + _he_list(unexpanded)
            + ", מפני שאין עדיין יחידת משמעות ייעודית ברמת הכלל במאגר N2.")
    if "unverified" in statuses:
        disclosure += " יש כללים שלא אומתו."
    if "reviewed" in statuses:
        disclosure += " חלק מהכללים נבדקו אך לא אושרו."
    if "approved" in statuses:
        disclosure += " כללים שמסומנים מאושרים אינם מאשרים את הרחבות N2."
    if "conflicting" in statuses:
        disclosure += " חלק מהמקורות שנויים במחלוקת."
    mode = semantics["time_mode"]
    if mode == "unknown":
        disclosure += (" שעת הלידה אינה ידועה; דגימת אמצע היום אינה "
                       "ראיה למעלות, לבתים או להיבטים מדויקים.")
    elif mode == "estimated":
        disclosure += (" שעת הלידה משוערת; לא נלקחו מן הדגימה "
                       "טענות על בתים או היבטים מדויקים.")
    sections.append(_section("limits", "מגבלות הקריאה", [{
        "kind": "disclosure", "text": disclosure,
        "semantic_text": "", "evidence_text": "", "section": "limits",
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
        "abstained_processes": abstained_paths,
    }


def format_narrative_n2(report: dict) -> str:
    if not isinstance(report, dict) or not isinstance(report.get("sections"), list):
        raise ValueError("נדרש דוח N2 מובנה")
    parts = ["פרשנות אישית (N2) — קריאה אסטרולוגית סמלית"]
    for section in report["sections"]:
        parts.append(section["title"])
        parts.extend(p["text"] for p in section["paragraphs"])
    return "\n\n".join(parts)


def semantic_only_n2(report: dict) -> list[str]:
    """Comparable claims without original rule quotes, URLs or disclosures."""
    return [p.get("semantic_text", "") for section in report["sections"]
            for p in section["paragraphs"]
            if p["kind"] in ("axis", "process", "process-abstention", "unresolved-tension")]
