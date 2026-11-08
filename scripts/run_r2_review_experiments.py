"""R2 review audit experiments A-G, offline and fully reproducible.

Execute: python scripts/run_r2_review_experiments.py --output r2-review-results.json
All charts are synthetic and deliberately controlled; passing a symbolic
holdout gate is *not* independent evidence about real people or semantics.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import astrochart.discovery_r2 as r2
from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart
from astrochart.synthesis import synthesize
from run_r2_experiment import run_experiment

SEED = 20261108
PERMUTATIONS = 1200
FROZEN_THRESHOLDS = {
    "min_support": 3, "min_lift": 1.25, "min_precision": 0.65,
    "min_unique_signatures": 2,
}
TARGET = tuple(sorted(("יוזמה", "רגישות", "חשיבה")))


def chart(**body_signs: int) -> Chart:
    named = {
        "sun": "שמש", "moon": "ירח", "mercury": "מרקורי",
        "venus": "ונוס", "mars": "מאדים",
    }
    bodies = [
        BodyPosition(named[name], 30*sign + 12.5 + j*1.1, False,
                     (sign,), house=None)
        for j, (name, sign) in enumerate(body_signs.items())
    ]
    return Chart(bodies, [], None, None, False, [])


def encode(charts: list[Chart], prefix: str) -> list[dict]:
    out = []
    for i, specimen in enumerate(charts):
        r1_result = synthesize(specimen, interpret_chart(specimen))
        out.append({
            "id": f"{prefix}-{i:02d}",
            "source_id": "synthetic-fixture-generator-not-independent-field-source",
            "independent_record_id": f"{prefix}-{i:02d}",
            "synthesis": r1_result,
        })
    return out


def group_split() -> tuple[list[dict], list[dict], dict]:
    # Pre-specify complete synthetic input configurations and their cohorts.
    # Three distinct positive witness rulesets, two examples from each.
    training = [
        chart(sun=0, moon=3, mercury=5, venus=1),
        chart(sun=0, moon=3, mercury=5, venus=4),
        chart(sun=5, moon=1, mercury=9, venus=3, mars=0),
        chart(sun=5, moon=2, mercury=9, venus=3, mars=0),
        chart(sun=9, moon=0, mercury=3, venus=5),
        chart(sun=10, moon=0, mercury=3, venus=5),
    ] + [
        chart(sun=1, moon=6, mercury=2, venus=v)
        for v in (1, 6, 10, 11, 7, 5)
    ]
    # Holdout positives use *new joint witness combinations*, not just
    # a different Venus sign on the old Sun-Moon-Mercury triad.
    validation = [
        chart(sun=3, moon=5, mercury=1, venus=0),
        chart(sun=0, moon=5, mercury=3, venus=1),
        chart(sun=3, moon=5, mercury=1, venus=1),  # removes A
        chart(sun=1, moon=6, mercury=2, venus=6),  # unrelated
    ]
    train, holdout = encode(training, "research-train"), encode(validation, "research-val")

    def relevant_signatures(items: list[dict]) -> list[str]:
        signatures = []
        for entry in items:
            parsed = r2._parse(entry)
            selected, complete = r2._joint(parsed, TARGET)
            if not complete:
                raise RuntimeError("pre-split proof incomplete")
            if selected:
                signatures.append(r2._support_signature(selected))
        return signatures

    training_signatures = relevant_signatures(train)
    validation_signatures = relevant_signatures(holdout)
    overlap = sorted(set(training_signatures) & set(validation_signatures))
    # Split/identity checks happen BEFORE any candidate mining or threshold
    # selection. Abort rather than let a contaminated trial pass.
    if overlap:
        raise RuntimeError("holdout proof-signature leakage detected before mining")
    return train, holdout, {
        "split_stage": "pre-specified-before-discovery-and-fixed-thresholds",
        "train_case_count": len(train), "holdout_case_count": len(holdout),
        "train_positive_signatures": len(set(training_signatures)),
        "holdout_positive_signatures": len(set(validation_signatures)),
        "overlapping_positive_signatures": overlap,
        "independent_field_data_sources": 0,
        "source_note": "all cases synthesized by one generator; no external validation",
    }


def permutation_control(train: list[dict], candidates: list[tuple[str, ...]],
                        threshold: dict) -> dict:
    """Permutation of column PRESENCE only, fixed candidate sets and marginals.

    It does NOT preserve astro dependency roots or reinvoke R1 proof searches;
    it cannot be interpreted as a calibrated p-value for discovery.
    """
    eligible, _, _, _ = r2._prepare(train)
    candidate_axes = sorted({a for c in candidates for a in c})
    columns = {a: [int(a in specimen["axes"]) for specimen in eligible]
               for a in candidate_axes}
    count = len(eligible)
    rng = random.Random(SEED)
    distribution: Counter[int] = Counter()
    for _ in range(PERMUTATIONS):
        shuffled = {}
        for axis in candidate_axes:
            values = list(columns[axis])
            rng.shuffle(values)
            shuffled[axis] = values
        passes = 0
        for members in candidates:
            full = sum(all(shuffled[axis][i] for axis in members)
                       for i in range(count))
            partial = sum(any(shuffled[axis][i] for axis in members)
                          and not all(shuffled[axis][i] for axis in members)
                          for i in range(count))
            expected = 1.0
            for axis in members:
                expected *= sum(shuffled[axis])/count if count else 0
            lift = full/count/expected if expected and count else 0
            ratio = full/(full+partial) if full+partial else 0
            if (full >= threshold["min_support"]
                    and lift >= threshold["min_lift"]
                    and ratio >= threshold["min_precision"]):
                passes += 1
        distribution[passes] += 1
    return {
        "seed": SEED, "iterations": PERMUTATIONS,
        "compared_fixed_pattern_count": len(candidates),
        "thresholds_frozen": threshold,
        "histogram_qualifying_fixed_sets": dict(sorted(distribution.items())),
        "mean_qualifying_fixed_sets": round(
            sum(k*v for k,v in distribution.items())/PERMUTATIONS, 6),
        "max_qualifying_fixed_sets": max(distribution),
        "caveat": (
            "only axis occurrence marginals preserved; source, dependency, "
            "R1 constraints, novelty search multiplicity NOT preserved; "
            "not a significance test or real-world statistical inference"),
    }


def run_review_experiments() -> dict:
    original = run_experiment()
    train, holdout, split = group_split()

    # A: identical evidence with 30 distinct edited textual metadata payloads.
    first = deepcopy(train[0])
    copies = []
    for i in range(30):
        c = deepcopy(first)
        c["id"] = f"adversarial-copy-{i}"
        c.pop("independent_record_id", None)
        c["synthesis"]["editorial_title"] = f"revision-{i}"
        c["synthesis"]["nodes"][0]["label"] = f"caption-{i}"
        copies.append(c)
    clones = r2.discover(copies, min_support=3, **{
        k:v for k,v in FROZEN_THRESHOLDS.items() if k != "min_support"})

    # B/C: training and holdout are not silently mixed or reused for tuning.
    discovered = r2.discover(train, holdout, **FROZEN_THRESHOLDS)
    target = next((h for h in discovered["hypotheses"]
                   if tuple(h["members"]) == TARGET), None)

    # D: change a base placement so a specific original witness disappears.
    changing = chart(sun=3, moon=5, mercury=1, venus=0)
    changed = chart(sun=3, moon=5, mercury=1, venus=1)
    initial = r2._parse(encode([changing], "factual-positive")[0])
    counterfactual = r2._parse(encode([changed], "factual-negative")[0])
    first_proof, _ = r2._joint(initial, TARGET)
    second_proof, _ = r2._joint(counterfactual, TARGET)

    # E: fixed-seed random baseline of axis marginals, not provenance.
    original_sets = [tuple(h["members"])
                     for h in original["r2"]["hypotheses"]]
    original_sets.extend(
        tuple(x["members"])
        for x in original["r2"]["recurring_but_not_diverse_patterns"])
    perm = permutation_control(train, sorted(set(original_sets)), FROZEN_THRESHOLDS)

    # F: deliberately exhaust the per-proof resource limit.
    limit = r2.MAX_PROOF_STATES
    try:
        r2.MAX_PROOF_STATES = 1
        constrained = r2.discover(train, holdout, **FROZEN_THRESHOLDS)
    finally:
        r2.MAX_PROOF_STATES = limit

    # G: independent sensitivity analysis, not re-tuning holdout to pass.
    sweeps = [
        {"min_support": 3, "min_lift": 1.25, "min_precision": 0.65},
        {"min_support": 4, "min_lift": 1.25, "min_precision": 0.65},
        {"min_support": 3, "min_lift": 1.50, "min_precision": 0.65},
        {"min_support": 3, "min_lift": 1.25, "min_precision": 0.75},
        {"min_support": 3, "min_lift": 1.25, "min_precision": 0.85},
    ]
    sensitivity = []
    for params in sweeps:
        r = r2.discover(train, holdout, min_unique_signatures=2, **params)
        sensitivity.append({
            "thresholds": params,
            "candidates": r["summary"]["novel_hypotheses"],
            "recurrent_insufficient_diversity": (
                r["summary"]["recurrent_insufficient_diversity_count"]),
            "target_present": any(tuple(h["members"]) == TARGET
                                  for h in r["hypotheses"]),
        })

    return {
        "experiment_id": "R2-01-to-R2-08-reviewed-synthetic-protocol",
        "protocol_locked_seed": SEED,
        "frozen_thresholds_prior_to_holdout": FROZEN_THRESHOLDS,
        "original_r1_to_r2": {
            "old_result_reported_hypotheses": 8,
            "after_fix_summary": original["r2"]["summary"],
            "target_after_fix": original["target_cross_domain_pattern"],
        },
        "A_adversarial_copies": {
            "submitted": len(copies),
            "accepted_cases": clones["summary"]["train_eligible_cases"],
            "canonical_duplicates": len(clones["duplicate_cases"]),
            "hypotheses": len(clones["hypotheses"]),
        },
        "B_complete_ontology": {
            "identity": discovered["ontology_identity"],
            "directed_paths": discovered["ontology_directed_path_count"],
            "predefined_observed_or_unobserved": (
                discovered["predefined_r1_patterns"]),
        },
        "C_new_signature_holdout": {
            "split": split,
            "training": discovered["summary"],
            "hypothesis_count": len(discovered["hypotheses"]),
            "target": {
                "found": bool(target),
                "training_metrics": target["metrics"] if target else None,
                "holdout": target["validation"] if target else None,
                "provenance": target["provenance_quality"] if target else None,
            },
            "external_generalization_proven": False,
        },
        "D_controlled_factual_counterfactual": {
            "positive_has_joint_proof": first_proof is not None,
            "modified_has_joint_proof": second_proof is not None,
            "changed_fact": "Venus Aries -> Venus Taurus",
        },
        "E_permutation_control": perm,
        "F_resource_bounds": constrained["search"],
        "G_threshold_sensitivity": sensitivity,
        "research_conclusion": {
            "level_1_recurrent_symbolic_patterns": True,
            "level_2_new_semantic_relation": False,
            "level_3_new_conceptual_understanding": False,
            "limitations": [
                "All positive charts are hand-designed symbolic configurations",
                "No independently collected source population or semantic ground truth",
                "A passed engineered holdout gate cannot establish external generalization",
                "No causal inference, scientific astrology validation, or personality prediction",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("r2-review-results.json"))
    args = parser.parse_args()
    result = run_review_experiments()
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "original": result["original_r1_to_r2"]["after_fix_summary"],
        "A": result["A_adversarial_copies"],
        "C_target": {
            "found": result["C_new_signature_holdout"]["target"]["found"],
            "status": (
                result["C_new_signature_holdout"]["target"]["holdout"]["status"]
                if result["C_new_signature_holdout"]["target"]["holdout"] else None),
        },
        "D": result["D_controlled_factual_counterfactual"],
        "E_mean": result["E_permutation_control"]["mean_qualifying_fixed_sets"],
        "F_search_complete": result["F_resource_bounds"]["witness_proof_search_complete"],
        "G": result["G_threshold_sensitivity"],
    }, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
