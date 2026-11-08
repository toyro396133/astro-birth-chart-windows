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


def _abstention_reason(plan: dict) -> tuple[str, str]:
    """Distinguish absent knowledge, indistinct readings and an unlicensed link."""
    missing = plan["coverage"]["missing_members"]
    if missing:
        names = _he_list([m["axis"] for m in missing])
        noun = "לרכיב" if len(missing) == 1 else "לרכיבים"
        return ("missing-catalog-coverage",
                f"{noun} {names} חסר פירוש ייעודי לכלל שנבחר במאגר")
    if not plan["comparison_is_supported"]:
        return ("no-meaningful-distinction",
                "המשמעויות הקיימות אינן מציגות הבחנה פרשנית מהותית")
    return ("no-supported-combined-assertion",
            "יש הבחנות בין רכיבים, אך אין ראיה מספקת לטענה חדשה על השילוב")


class DeterministicHebrewRealizer:
    """Presentation adapter only: no free-form link mining or guessed context."""

    def axis(self, claims: list[dict], index: int, *,
             secondary: bool) -> tuple[str, str]:
        meaning = next(c for c in claims if c["kind"] == "axis-meaning")["content"]
        anchors = [c for c in claims if c["kind"] == "rule-anchor"]
        example_claims = [c for c in claims if c["kind"] == "axis-example"]
        examples = [c["content"] for c in example_claims]
        # Full catalog membership is computed before the presentation cap.
        catalog_total = meaning.get("catalog_coverage_count", len(examples))
        displayed_total = len(examples)
        missing_in_catalog = max(0, meaning["independent_evidence_count"] - catalog_total)
        omitted_for_length = max(0, catalog_total - displayed_total)
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
                         f"ל־{catalog_total} מהן קיים פירוש תלוי־כלל במאגר, "
                         "ורק פירוש אחד מוצג בפסקה.")
                if omitted_for_length:
                    text += f" {omitted_for_length} פירושים נוספים לא הוצגו בשל מגבלת אורך."
                if missing_in_catalog:
                    text += f" ל־{missing_in_catalog} קבוצות אין עדיין פירוש תלוי־כלל."
            return text, evidence
        # Label meaning with the ORIGINAL selected R1 witness-group ordinal,
        # not its ordinal among curated examples (which may skip witnesses).
        original_positions = {
            tuple(a.get("evidence_keys", [])): position + 1
            for position, a in enumerate(anchors) if a.get("evidence_keys")
        }
        phrases = [
            f"{e['focus']} (קבוצת ראיה "
            f"{original_positions.get(tuple(c.get('evidence_keys', [])), i + 1)})"
            for i, (e, c) in enumerate(zip(examples, example_claims))]
        detail = "; ".join(e["distinction"] for e in examples)
        shown = examples[:2]
        situations = "; ".join(
            f"{e['situation']}, בעל המפה {e['behavior']}" for e in shown)
        text = (
            f"ציר {axis} נתמך בכמה ראיות עצמאיות: מתוך {count} קבוצות, "
            f"ל־{catalog_total} יש פירוש עריכתי תלוי־כלל. "
            + (f"מתוכן מוצגות כאן {displayed_total} הרחבות בלבד בשל מגבלת אורך: "
               if omitted_for_length else "המשמעויות המוצגות הן: ")
            + "; ".join(phrases) + ". "
            + "ההבחנות בין המשמעויות הן: " + detail + ". "
            + f"לשם המחשה בלבד מובאות {len(shown)} דוגמאות התנהגות נפרדות: "
            + situations + ". "
            + "הדוגמאות אינן ממצות את כלל הראיות או מוכיחות "
              "שהתיאורים מתקיימים יחד."
        )
        if missing_in_catalog:
            if missing_in_catalog == 1:
                text += " לקבוצת ראיה אחת נוספת אין פירוש התנהגותי ייחודי במאגר."
            else:
                text += (f" ל־{missing_in_catalog} קבוצות ראיה נוספות "
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
                + (f"לרכיב {missing[0]['axis']} "
                   if len(missing) == 1 else
                   f"לרכיבים {_he_list([x['axis'] for x in missing])} ")
                + "אין עדיין משמעות תלויה בכלל שנבחר. ")
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
                "הסדר של R1 מסדר כאן נקודות מבט על מצבים שונים, "
                "אך אינו מתאר שרשרת אירועים שאכן התרחשה. ")
        else:
            text += ("ההשוואה מתייחסת רק לרכיבים המכוסים, "
                     "ולא מסבירה את המסלול המלא. ")
        text += ("גם גבולות ההסקה שונים: "
                 + "; ".join(f"{c['axis']} — {c['limit']}" for c in components)
                 + ". ")
        text += ("המשמעויות המתועדות מאפשרות להבחין בדגשים; "
                 "הן אינן מוכיחות שהדגשים פועלים יחד, מחזקים זה את זה "
                 "או שאחד גורם לאחר. הסדר אינו ראיה לקשר סיבתי.")
        if not reading["proof_search_complete"]:
            text += " חיפוש החלופות למסלול הוגבל."
        # Long evidence may contain several R1 witness groups. Keep every
        # selected witness in evidence_text and the full plan in JSON, but
        # do not turn a single GUI paragraph into a wall of prose.
        if len(text) + len(evidence) > 1240:
            text = (opening + evidence_count + " מצביעות על מוקדים שונים: "
                    + "; ".join(positions) + ". "
                    + "ההבדל ביניהן ניכר גם בהקשר: "
                    + "; ".join(f"{c['axis']} — {c['setting']}" for c in components)
                    + ". ")
            if missing:
                text += "זהו תיאור חלקי בלבד, לא של המסלול כולו. "
            text += ("הסדר התפקודי אינו ראיה לקשר סיבתי, לחיזוק הדדי "
                     "או להתנהגויות שהתרחשו יחד.")
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
    process_decisions = []
    for index, ids in enumerate(plan["processes"]):
        group = [claims[i] for i in ids]
        base = next(c for c in group if c["kind"] == "process-reading")
        content = base["content"]
        content_plan = content["content_plan"]
        has_comparison = any(c["kind"] == "process-example" for c in group)
        # Legacy hand-built fixtures may lack the new decision fields. Actual
        # production claims always carry two independent decisions.
        decisions = content.get("interpretation_decisions")
        if decisions is None:
            fallback_reason, _ = _abstention_reason(content_plan)
            decisions = {
                "schema_version": 1,
                "comparison": {
                    "permitted": has_comparison,
                    "reason": ("documented-distinct-readings" if has_comparison
                               else fallback_reason),
                    "scope": ("partial" if content_plan["coverage"]["missing_members"]
                              else "full") if has_comparison else "none",
                },
                "combined_assertion": {
                    "permitted": False,
                    "reason": "no-supported-combined-assertion",
                },
            }
        if decisions["comparison"]["permitted"] != has_comparison:
            raise ValueError("החלטת השוואה אינה תואמת לטענות המסלול")
        record = {
            "path": content_plan["path"],
            "coverage": content_plan["coverage"],
            "node_ids": sorted({n for c in group for n in c["node_ids"]}),
            "claim_ids": [c["id"] for c in group],
            "rule_ids": sorted({r for c in group for r in c["rule_ids"]}),
            "source_refs": sorted({r for c in group for r in c["source_refs"]}),
            "source_review_statuses": sorted({
                r for c in group for r in c["source_review_statuses"]}),
            "evidence_keys": sorted({r for c in group for r in c["evidence_keys"]}),
            "evidence_roots": sorted({r for c in group for r in c["evidence_roots"]}),
            "meaning_ids": sorted({r for c in group for r in c["meaning_ids"]}),
            "comparison": decisions["comparison"],
            "combined_assertion": decisions["combined_assertion"],
        }
        process_decisions.append(record)
        if not has_comparison:
            abstained.append((group, content_plan, record))
            continue
        semantic, evidence = realizer.process(group, index)
        p = _merge("processes", "process", group, semantic, evidence)
        p["process_content_plan"] = content_plan
        p["interpretation_decisions"] = record
        processes.append(p)
    abstained_paths = []
    for group, cp, record in abstained:
        reason, explanation = _abstention_reason(cp)
        abstained_paths.append({
            **record,
            "reason": reason, "reason_explanation": explanation,
        })
    if abstained:
        all_claims = [c for group, _, _ in abstained for c in group]
        names = [" → ".join(cp["path"]) for _, cp, _ in abstained]
        if len(abstained) == 1:
            summary = (f"אותר מסלול נוסף ב־R1 ({names[0]}), "
                       f"אך לא נוצרה השוואה פרשנית: "
                       f"{abstained_paths[0]['reason_explanation']}. "
                       "לא הוסק ממנו קשר התנהגותי. "
                       "פירוט הרכיבים והראיות שנבחרו נשמר ב־JSON.")
        else:
            reasons = "; ".join(
                f"{name} — {abstained_paths[i]['reason_explanation']}"
                for i, name in enumerate(names))
            summary = (f"אותרו {len(abstained)} מסלולים נוספים ב־R1 "
                       f"({_he_list(names)}), אך לא נוצרה עבורם השוואה "
                       f"פרשנית. הסיבות לפי מסלול: {reasons}. "
                       "לא הוסקו מהם קשרים התנהגותיים. "
                       "פירוט הרכיבים והראיות שנבחרו נשמר ב־JSON.")
        evidence = "\n".join(
            f"• {' → '.join(cp['path'])}: "
            + "; ".join(
                f"{m['axis']} — כלל {m['selected_rule_id']}"
                + (" (ללא פירוש עריכתי)" if not m["meaning_covered"] else "")
                for m in cp["members"])
            for _, cp, _ in abstained)
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
        # All R1 paths, including those with a permitted comparison, keep an
        # explicit unlicensed-combination decision and complete provenance.
        "process_decisions": process_decisions,
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
