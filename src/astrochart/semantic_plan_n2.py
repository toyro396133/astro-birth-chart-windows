"""N2 semantic content planning over EXACT R1-selected path evidence.

Only compare documented editorial readings. An R1 process is a hypothesis,
not permission to invent co-occurrence, causality, reinforcement or a new
psychological trait. This module has no free-form semantic inference.
"""
from __future__ import annotations


def build_process_content_plan(path: list[str], slots: list[dict], domain: str,
                               relation: object, proof_complete: bool) -> dict:
    """Preserve ordered members, selected witnesses and unsupported inferences."""
    if len(path) != len(slots) or [s["axis"] for s in slots] != list(path):
        raise ValueError("R1 path and selected witnesses differ")
    members = []
    for position, slot in enumerate(slots):
        w = slot["witness"]
        meaning = ({"id": w["meaning_id"], "focus": w["focus"],
                    "setting": w["setting"], "behavior": w["behavior"],
                    "distinction": w["distinction"], "limit": w["limitation"]}
                   if w["meaning_id"] else None)
        members.append({
            "position": position, "axis": slot["axis"],
            "selected_rule_id": w["rule_id"],
            "selected_evidence_key": w["evidence_key"],
            "selected_witness": slot["witness"],
            "selected_witness_group": slot["witness_group"],
            "meaning_covered": meaning is not None,
            "documented_meaning": meaning,
        })
    covered = [m for m in members if m["meaning_covered"]]
    missing = [{"position": m["position"], "axis": m["axis"],
                "selected_rule_id": m["selected_rule_id"]}
               for m in members if not m["meaning_covered"]]
    differences = []
    for i, first in enumerate(covered):
        for second in covered[i + 1:]:
            a, b = first["documented_meaning"], second["documented_meaning"]
            if (a["focus"], a["distinction"]) == (b["focus"], b["distinction"]):
                continue
            differences.append({
                "from_position": first["position"], "to_position": second["position"],
                "from_axis": first["axis"], "to_axis": second["axis"],
                "from_rule_id": first["selected_rule_id"],
                "to_rule_id": second["selected_rule_id"],
                "focus_difference": [a["focus"], b["focus"]],
                "context_difference": [a["setting"], b["setting"]],
                "source_distinctions": [a["distinction"], b["distinction"]],
                "source_limits": [a["limit"], b["limit"]],
                "licensed_as": "comparison-only",
            })
    # The ordered perspectives are a bounded reading of R1's selected
    # hypothesis, not independent evidence for a new relationship.
    return {
        "schema_version": 1, "path": list(path), "domain": domain,
        "r1_relation": relation, "proof_search_complete": bool(proof_complete),
        "members": members,
        "coverage": {"total_members": len(members),
                     "covered_members": len(covered),
                     "covered_axes": [m["axis"] for m in covered],
                     "missing_members": missing,
                     "complete": not missing},
        "distinctions": differences,
        "supported_readings": ([{
            "type": "ordered-perspectives-of-r1-hypothesis",
            "positions": [m["position"] for m in members],
            "basis": "selected-r1-path-and-rule-conditioned-editorial-readings",
            "epistemic_status": "hypothesis-not-observed-behavior",
        }] if not missing and differences else []),
        "unsupported_links": [
            "observed-joint-behavior", "psychological-causality",
            "mutual-reinforcement", "predictive-outcome",
        ],
        "new_cross_axis_assertion_supported": False,
        "synthesis_status": "hypothesis-not-proven",
        "comparison_is_supported": bool(differences),
    }
