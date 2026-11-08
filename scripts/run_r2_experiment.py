"""Reproducible R2 experiment using REAL R1 outputs from synthetic charts.

No personal birth data, internet, astrology-library switch or model training.
Run: python scripts/run_r2_experiment.py [--output r2-results.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from astrochart.discovery_r2 import discover
from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart
from astrochart.synthesis import synthesize


def make_chart(sun_sign: int, moon_sign: int, mercury_sign: int,
               venus_sign: int, *, unknown_time: bool = False) -> Chart:
    specs = [
        ("שמש", sun_sign, 11.7),
        ("ירח", moon_sign, 14.1),
        ("מרקורי", mercury_sign, 17.2),
        ("ונוס", venus_sign, 19.4),
    ]
    bodies = [
        BodyPosition(name, 30 * sign + degree, False,
                     signs_possible=(sign,), house=None)
        for name, sign, degree in specs
    ]
    return Chart(bodies, [], None, None, unknown_time, [])


def run_experiment() -> dict:
    """Hold out charts BEFORE R2 discovery; counterfactual changes Mercury."""
    train_charts = [
        make_chart(0, 3, 5, sign)
        for sign in (0, 1, 2, 4, 7, 8)
    ] + [
        make_chart(1, 6, 2, sign)
        for sign in (0, 3, 4, 5, 10, 11)
    ]
    # Experimental input sensitivity: same Sun/Moon, different Mercury.
    holdout_charts = [
        make_chart(0, 3, 5, 9),
        make_chart(0, 3, 2, 9),
        make_chart(1, 6, 2, 6),  # held-out Venus sign absent from training
    ]
    train_charts.append(make_chart(0, 3, 5, 11, unknown_time=True))
    def encode(charts, prefix):
        result = []
        for i, chart in enumerate(charts):
            legacy = interpret_chart(chart)
            r1 = synthesize(chart, legacy)
            result.append({"id": f"{prefix}-{i:02d}", "synthesis": r1})
        return result
    train = encode(train_charts, "train")
    holdout = encode(holdout_charts, "holdout")
    r1_paths = {
        tuple(node["path"])
        for record in train for node in record["synthesis"]["nodes"]
        if node["type"] == "synthesis"
    }
    r2 = discover(train, holdout, min_support=3, min_lift=1.25)
    core = ("יוזמה", "רגישות", "חשיבה")
    core_hypothesis = next(
        (h for h in r2["hypotheses"] if set(h["members"]) == set(core)), None)
    return {
        "experiment": "r2-independent-synthetic-r1-reports",
        "input": "interpret_chart -> synthesize (same 96 original rules)",
        "method": "original R1; purely synthetic configurations; holdout includes a Mercury counterfactual",
        "r1_baseline": {
            "train_reports": len(train),
            "distinct_predefined_composition_paths": len(r1_paths),
            "has_cross_domain_initiative_sensitivity_thinking_path":
                any(set(core) == set(path) for path in r1_paths),
        },
        "r2": r2,
        "target_cross_domain_pattern": {
            "members": sorted(core),
            "found": core_hypothesis is not None,
            "metrics": core_hypothesis["metrics"] if core_hypothesis else None,
            "heldout": core_hypothesis["validation"] if core_hypothesis else None,
        },
        "research_limit": (
            "All outputs are engineering hypotheses about symbolic rule matches, "
            "not validated predictions about people or physical causation."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="optional reproducible JSON report")
    args = parser.parse_args()
    result = run_experiment()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({
        "experiment": result["experiment"],
        "r1": result["r1_baseline"],
        "r2": result["r2"]["summary"],
        "target": {
            "found": result["target_cross_domain_pattern"]["found"],
            "metrics": result["target_cross_domain_pattern"]["metrics"],
            "heldout_status": (
                result["target_cross_domain_pattern"]["heldout"]["status"]
                if result["target_cross_domain_pattern"]["heldout"] else None),
        },
    }, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
