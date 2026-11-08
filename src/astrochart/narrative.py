"""N1: deterministic Hebrew explanation of *existing* R1 evidence.

Presentation only. Functional steps, evidence, review states and contradictions
come from the R1 payload; this module never infers chart facts or approves rules.
"""
from __future__ import annotations

NARRATIVE_VERSION = "0.1.1"
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


def _collect_provenance(groups: list[dict]) -> dict:
    """Use the *selected*, polarity-specific R1 witness groups, not all hits."""
    return {
        "rule_ids": sorted({rid for group in groups
                            for rid in group.get("rule_ids", [])}),
        "source_refs": sorted({src for group in groups
                               for src in group.get("source_refs", [])}),
        "source_review_statuses": sorted({
            status for group in groups
            for status in group.get("review_statuses", [])}),
        "evidence_keys": sorted({group["evidence_key"] for group in groups
                                 if group.get("evidence_key")}),
        "evidence_roots": sorted({root for group in groups
                                  for root in group.get("roots", [])}),
    }


def _paragraph(kind: str, text: str, *, node: dict | None = None,
               node_ids: list[str] | None = None,
               rule_ids: list[str] | None = None,
               source_refs: list[str] | None = None,
               source_review_statuses: list[str] | None = None,
               audit_status: str | None = None,
               evidence_by_polarity: dict | None = None,
               provisional: bool = False) -> dict:
    """Keep the existing N1 provenance contract; add polarity when needed."""
    paragraph = {
        "kind": kind,
        "text": text,
        "node_ids": sorted(set(
            node_ids if node_ids is not None else ([node["id"]] if node else []))),
        "rule_ids": sorted(set(
            rule_ids if rule_ids is not None else
            (node.get("rule_ids", []) if node else []))),
        "source_refs": sorted(set(
            source_refs if source_refs is not None else
            (node.get("source_refs", []) if node else []))),
        "source_review_statuses": sorted(set(
            source_review_statuses if source_review_statuses is not None else
            (node.get("source_review_statuses", []) if node else []))),
        "audit_status": audit_status or (
            node.get("audit_status") if node else "editorial-disclosure"),
        "provisional_time": (
            bool(node.get("provisional_time")) if node is not None else provisional),
    }
    if evidence_by_polarity is not None:
        paragraph["evidence_by_polarity"] = evidence_by_polarity
    return paragraph


def _section(section_id: str, title: str, paragraphs: list[dict]) -> dict:
    return {"id": section_id, "title": title, "paragraphs": paragraphs}


def _supported_process(node: dict) -> bool:
    """Narrow renderer gate: validate R1's already-selected proof, not rescore it."""
    path = node.get("path", [])
    witnesses = node.get("independent_facts", [])
    selected = node.get("selected_witnesses_by_axis")
    if (node.get("type") != "synthesis"
            or node.get("audit_status") != "hypothesis"
            or not isinstance(path, list) or len(path) < 2
            or len(set(path)) != len(path)
            or not isinstance(witnesses, list) or len(witnesses) != len(path)
            or not isinstance(selected, dict) or set(selected) != set(path)
            or not node.get("rule_ids")):
        return False
    roots = set()
    for axis, witness in zip(path, witnesses):
        if (not isinstance(witness, dict) or selected[axis] != witness
                or not witness.get("rule_ids")
                or not witness.get("roots")):
            return False
        current = set(witness["roots"])
        if roots.intersection(current):
            return False
        roots.update(current)
    return True


def _functional_steps(node: dict, by_axis: dict[str, dict]) -> list[tuple[str, str]] | None:
    """Functional labels are *read* from R1 axis nodes, never recreated."""
    steps = []
    for axis in node["path"]:
        part = by_axis.get(axis)
        if not part or not part.get("function") or part.get("domain") != node.get("domain"):
            return None
        steps.append((axis, part["function"]))
    return steps


def _explain_process(node: dict, steps: list[tuple[str, str]], index: int) -> str:
    """Explain *R1's* proposed sequence, then name its selected source facts."""
    first_axis, first_function = steps[0]
    last_axis, last_function = steps[-1]
    if len(steps) == 2:
        lead = (
            f"בתחום {node['domain']}, ציר {first_axis} מייצג ב־R1 את פעולת "
            f"{first_function}, וציר {last_axis} את פעולת {last_function}. "
            f"הקשר המשוער הוא שפעולת {first_function} עשויה להזין "
            f"את פעולת {last_function}, ולא רק ששני הצירים נמצאו בנפרד. "
        )
    else:
        transitions = "; ובהמשך ".join(
            f"פעולת {current[1]} עשויה להזין את פעולת {following[1]}"
            for current, following in zip(steps, steps[1:]))
        lead = (
            (f"בתחום {node['domain']} מוצע רצף אפשרי: " if index == 0 else
             f"רצף אחר בתחום {node['domain']} מציע: ")
            + f"{first_axis} ({first_function}) היא נקודת המוצא, "
            + f"ו{last_axis} ({last_function}) היא החוליה האחרונה. "
            + f"על פי מפת המעברים של R1, {transitions}. "
        )
    anchors = []
    for axis, _ in steps:
        witness = node["selected_witnesses_by_axis"][axis]
        description = next((item.strip().rstrip(" .") for item in
                            witness.get("details", [])
                            if isinstance(item, str) and item.strip()), None)
        if description:
            anchors.append(
                f"{axis}: {description} (כלל {witness['rule_ids'][0]})")
    evidence_text = (
        " עוגני הראיות שנבחרו ב־R1: " + "; ".join(anchors) + "."
        if anchors else "")
    return (
        lead
        + f"לכל אחת מ־{len(steps)} החוליות נבחרה ראיה נפרדת מבחינת "
          "תלות הנתונים. "
        + evidence_text
        + " הראיות תומכות בצירים לפי כללי המאגר; הקשר ביניהם "
          "הוא השערת מודל, לא עובדה שנצפתה."
        + (" החיפוש אחר חלופות הוגבל ולכן ייתכנו מסלולים נוספים."
           if not node.get("proof_search", {}).get("complete", True) else "")
        + (" המסקנה מותנית באי־הוודאות בשעת הלידה."
           if node.get("provisional_time") else "")
    )


def _tension_paragraph(tension: dict, by_axis: dict[str, dict]) -> dict:
    """Exact R1 positive/negative proof, with no invented conflict context."""
    axis = tension["axis"]
    node = by_axis.get(axis)
    if node is None:
        raise ValueError("סתירת R1 ללא צומת ציר מקורי: " + axis)
    positive = _collect_provenance(node.get("independent_facts", []))
    negative = _collect_provenance(node.get("counter_facts", []))
    if (positive["rule_ids"] != sorted(set(tension.get("positive_rule_ids", [])))
            or negative["rule_ids"] != sorted(set(tension.get("negative_rule_ids", [])))
            or not positive["rule_ids"] or not negative["rule_ids"]):
        raise ValueError("סתירת R1 אינה תואמת את קבוצות הראיות: " + axis)
    return _paragraph(
        "tension",
        f"לגבי {axis}, R1 מציג ראיות התומכות בציר וגם ראיות בכיוון "
        "ההפוך. שתי הקבוצות נשמרות בנפרד; אין בדוח נתון המזהה מתי "
        "כל כיוון עשוי לחול, ולכן הסתירה נותרת בלתי מוכרעת.",
        node=node,
        rule_ids=positive["rule_ids"] + negative["rule_ids"],
        source_refs=positive["source_refs"] + negative["source_refs"],
        source_review_statuses=(
            positive["source_review_statuses"] +
            negative["source_review_statuses"]),
        audit_status="unresolved",
        evidence_by_polarity={
            "positive": positive, "negative": negative,
            "shared_roots": list(tension.get("shared_roots", [])),
        },
    )


def _review_disclosure(paragraphs: list[dict]) -> dict | None:
    """Describe only statuses present in *displayed* R1-backed claims."""
    claims = [p for p in paragraphs if p["kind"] in ("overview", "process", "axis", "tension")]
    statuses = sorted({s for p in claims for s in p["source_review_statuses"]})
    if not statuses:
        return None
    statements = []
    if "unverified" in statuses:
        statements.append("יש כללי מקור שטרם אומתו פרטנית")
    if "reviewed" in statuses:
        statements.append("יש כללים שנבדקו אך לא קיבלו מעמד 'מאושר'")
    if "approved" in statuses:
        statements.append("יש כללים המסומנים 'מאושר' במאגר")
    else:
        statements.append("אף כלל המוצג כאן אינו מסומן 'מאושר'")
    if "conflicting" in statuses:
        statements.append("יש גם מקורות עם ביקורת סותרת")
    unknown = [status for status in statuses
               if status not in {"unverified", "reviewed", "approved", "conflicting"}]
    if unknown:
        statements.append("קיימים סטטוסים נוספים המפורטים בנתונים המובנים")
    text = ("מעמד המקורות של הטענות המוצגות: "
            + "; ".join(statements)
            + ". גם מעמד 'מאושר' של כלל בודד אינו מאשר את המעברים "
              "התפקודיים ש־R1 מציע כהשערה.")
    return _paragraph(
        "source-disclosure", text,
        node_ids=[nid for p in claims for nid in p["node_ids"]],
        rule_ids=[rid for p in claims for rid in p["rule_ids"]],
        source_refs=[src for p in claims for src in p["source_refs"]],
        source_review_statuses=statuses,
        provisional=any(p["provisional_time"] for p in claims),
    )


def compose_narrative(synthesis: dict) -> dict:
    """Plan a bounded readable view over R1, without mutating or reranking it."""
    if (not isinstance(synthesis, dict)
            or not isinstance(synthesis.get("nodes"), list)
            or not isinstance(synthesis.get("summary"), dict)):
        raise ValueError("נדרש דוח סינתזה R1 מובנה")

    nodes = {n["id"]: n for n in synthesis["nodes"] if isinstance(n, dict)
             and isinstance(n.get("id"), str)}
    time_mode = synthesis.get("time_mode", "unknown")
    if time_mode not in ("known", "estimated", "unknown"):
        raise ValueError("מצב שעת לידה אינו מוכר")
    by_axis = {
        n["axis"]: n for n in synthesis["nodes"]
        if isinstance(n, dict) and n.get("type") == "axis"
        and isinstance(n.get("axis"), str) and n.get("id")
    }

    eligible = []
    seen = set()
    for node_id in synthesis["summary"].get("top_hypotheses", []):
        node = nodes.get(node_id)
        if node_id in seen or node is None or not _supported_process(node):
            continue
        if _functional_steps(node, by_axis) is None:
            continue
        seen.add(node_id)
        eligible.append(node)
    selected = eligible[:MAX_PROCESS_PARAGRAPHS]

    opening = ("זו קריאה סמלית מתוך ראיות וכללי פרשנות שמנוע R1 כבר עיבד. "
               "הקריאה אינה אבחון אישיות מדעי, והמשקלים אינם הסתברויות. "
               "חיבור בין פעולות הוא אפשרות פרשנית של המודל, לא עובדה על אדם.")
    if time_mode == "estimated":
        opening += (" שעת הלידה משוערת; לא נגזרות מן הדגימה "
                    "ראיות לבתים או להיבטים, ויש לקרוא את הטענות כזמניות.")
    elif time_mode == "unknown":
        opening += (" שעת הלידה אינה ידועה; נתוני דגימה אינם ראיות "
                    "לבתים או להיבטים, והמסקנות מותנות במידע הזמין.")

    opening_paragraphs = [
        _paragraph("disclosure", opening, provisional=time_mode != "known")]
    if selected:
        lead = selected[0]
        steps = _functional_steps(lead, by_axis)
        assert steps is not None
        operations = [function for _, function in steps]
        opening_paragraphs.append(_paragraph(
            "overview",
            f"במרכז הדוח עומדת השערה לרצף בתחום {lead['domain']}: "
            f"מעבר תפקודי מ{operations[0]} אל {operations[-1]}"
            + (f", דרך {_hebrew_list(operations[1:-1])}" if len(operations) > 2 else "")
            + ". כל שלב נשען על ראיה משלו; המעבר בין השלבים "
              "עדיין אינו כלל שנבדק ואושר.",
            node=lead,
        ))
    sections = [_section("opening", "התמונה בקצרה", opening_paragraphs)]

    processes = []
    for index, node in enumerate(selected):
        steps = _functional_steps(node, by_axis)
        assert steps is not None
        processes.append(_paragraph(
            "process", _explain_process(node, steps, index), node=node))
    if not processes:
        processes = [_paragraph(
            "no-process",
            "לא נמצאה שרשרת תפקודית מורכבת בדוח R1 המגובה בראיות "
            "עצמאיות. היעדר מסלול כזה אינו שולל קשרים שהמנוע לא בדק.")]
    sections.append(_section("processes", "כיצד הצירים עשויים להתחבר", processes))

    covered_axes = {axis for node in selected for axis in node["path"]}
    tensions = [t for t in synthesis.get("tensions", [])
                if t.get("status") == "unresolved"]
    tension_axes = {t["axis"] for t in tensions}
    ranked_axes = sorted(by_axis.values(), key=lambda n: (
        -n.get("strength", 0), n["axis"]))
    ordered_axes = []
    for axis in synthesis["summary"].get("leading_axes", []):
        if axis in by_axis and axis not in ordered_axes:
            ordered_axes.append(axis)
    ordered_axes.extend(n["axis"] for n in ranked_axes
                        if n["axis"] not in ordered_axes)
    axis_paragraphs = []
    not_displayed_axes = []
    excluded_axes = {"covered_by_process": [], "unresolved_tension": []}
    for axis in ordered_axes:
        node = by_axis[axis]
        if axis in covered_axes:
            excluded_axes["covered_by_process"].append(node["id"])
            continue
        if axis in tension_axes:
            excluded_axes["unresolved_tension"].append(node["id"])
            continue
        if not node.get("independent_facts"):
            continue
        if len(axis_paragraphs) >= MAX_STANDALONE_AXES:
            not_displayed_axes.append(node["id"])
            continue
        function, domain = node.get("function"), node.get("domain")
        index = len(axis_paragraphs)
        if index == 0:
            text = (f"לצד ההשערות על רצפים, ציר {axis} מופיע בנפרד. "
                    f"במיפוי R1 הוא קשור לפעולת {function} בתחום {domain}.")
        elif index == 1:
            text = (f"ציר עצמאי נוסף הוא {axis}: תיאורו התפקודי ב־R1 "
                    f"הוא {function}, בתחום {domain}.")
        elif index == 2:
            text = (f"בתחום {domain} מופיע גם {axis}, "
                    f"שתפקידו במיפוי הוא {function}.")
        else:
            text = (f"נוסף לכך, {axis} מתואר כפעולת {function} "
                    f"בתחום {domain}.")
        if index == 0:
            text += (" תיאור הצירים העומדים בפני עצמם אינו קובע "
                     "שיש קשר סיבתי ביניהם.")
        axis_paragraphs.append(_paragraph("axis", text, node=node))
    if axis_paragraphs:
        sections.append(_section("axes", "צירים העומדים בפני עצמם", axis_paragraphs))

    tension_paragraphs = [_tension_paragraph(t, by_axis) for t in tensions]
    if tension_paragraphs:
        sections.append(_section("tensions", "עדויות לכיוונים מנוגדים", tension_paragraphs))

    claims = opening_paragraphs + processes + axis_paragraphs + tension_paragraphs
    source_disclosure = _review_disclosure(claims)
    if source_disclosure:
        sections.append(_section("sources", "מה נבדק ומה אושר", [source_disclosure]))

    warnings = list(synthesis.get("warnings", []))
    # R1's standard disclaimers remain untouched in the structured payload;
    # the opening/sources already express them in clearer, nonrepetitive prose.
    already_explained = {
        "כל ההסקות החדשות הן השערות הנובעות מאונטולוגיה הנדסית; לא כללים מאושרים.",
        "משקלי הכללים ומקדמי העוצמה אינם הסתברויות או מדדי אישיות.",
        "ניקוד עוצמת גוף חלקי לפי מזל אינו מתורגם לציון תכונת אופי.",
        "שעת הלידה אינה ודאית; אין להסיק בתים או היבטים מהדגימה.",
    }
    additional = [w for w in warnings if w not in already_explained]
    if additional:
        sections.append(_section("cautions", "מגבלות נוספות", [
            _paragraph("warning", warning, provisional=time_mode != "known")
            for warning in additional]))

    return {
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
        "displayed_axis_ids": [p["node_ids"][0] for p in axis_paragraphs],
        "not_displayed_axis_ids": not_displayed_axes,
        "excluded_axis_ids": excluded_axes,
        "warnings": warnings,
    }


def format_narrative(narrative: dict) -> str:
    """Readable text; per-paragraph provenance remains in the JSON contract."""
    if not isinstance(narrative, dict) or "sections" not in narrative:
        raise ValueError("נדרש דוח ניסוח מובנה")
    parts = ["קריאה רציפה — פרשנות סמלית (N1)"]
    for section in narrative["sections"]:
        parts.append(section["title"])
        parts.extend(p["text"] for p in section["paragraphs"])
    if narrative.get("not_displayed_hypothesis_ids") or narrative.get("not_displayed_axis_ids"):
        parts.append("מוצגים רק הממצאים שנבחרו לקריאה זו; יתר הצמתים "
                     "ושרשראות ההסקה זמינים בלשוניות הסינתזה והראיות.")
    return "\n\n".join(parts)
