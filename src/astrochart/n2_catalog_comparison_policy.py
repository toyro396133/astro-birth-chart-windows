"""C29 presentation policy: do not confuse an allowed comparison with a useful one.

No new N3 relationship or alternative N2 inference contract is introduced.
The existing process-reading interpretation_decisions determine whether a
bounded comparison is allowed; this local step *only* prevents repetition of
readings already displayed, or duplicated process evidence in one report.
"""
from __future__ import annotations


def selected_reading_signature(plan: dict) -> tuple:
    """Non-linguistic: one selected R1 rule/evidence/meaning per covered slot."""
    return tuple(
        (m["position"], m["axis"], m["selected_rule_id"],
         m["selected_evidence_key"],
         (m["documented_meaning"] or {}).get("id"))
        for m in plan["members"] if m["meaning_covered"]
    )


def presentation_decision(plan: dict, already_visible: set[tuple[str, str, str]],
                          previous: set[tuple]) -> dict:
    """Choose whether a *permitted* comparison adds anything to the report.

    Matching a lexical synonym or length is never a novelty signal.
    Distinctness arises only from independently selected rule/evidence/meaning
    that was not described in another visible axis/process paragraph.
    """
    signature = selected_reading_signature(plan)
    if not plan["comparison_is_supported"]:
        return {"display": False, "reason": "comparison-not-permitted",
                "signature": signature}
    if signature in previous:
        return {"display": False, "reason": "no-novel-comparison",
                "basis": "same-selected-meaning-signature-as-prior-process",
                "signature": signature}
    covered = [m for m in plan["members"] if m["meaning_covered"]]
    all_shown = bool(covered) and all(
        (m["selected_rule_id"], m["selected_evidence_key"],
         m["documented_meaning"]["id"]) in already_visible
        for m in covered)
    if all_shown:
        return {"display": False, "reason": "no-novel-comparison",
                "basis": "all-exact-selected-meanings-already-explained-as-axes",
                "signature": signature}
    return {"display": True, "reason": "previously-unshown-selected-reading",
            "basis": "at-least-one-new-rule-evidence-meaning-triple",
            "signature": signature}
