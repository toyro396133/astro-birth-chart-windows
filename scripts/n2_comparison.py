"""Reproducible N1-vs-N2 blindable local comparison on held-out chart fixtures.

Run: python scripts/n2_comparison.py
All chart inputs are synthetic, not real persons or empirical validations.
"""
from copy import deepcopy
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from astrochart.domain import BodyPosition, Chart
from astrochart.interpretation import interpret_chart
from astrochart.narrative import compose_narrative, format_narrative
from astrochart.synthesis import synthesize
from astrochart.semantics_n2 import build_personality_model
from astrochart.narrative_n2 import compose_narrative_n2, format_narrative_n2


def sample(sun: float, mercury: float, *, mode="known") -> Chart:
    return Chart(
        [BodyPosition("שמש", sun, False, (int(sun // 30),)),
         BodyPosition("מרקורי", mercury, False, (int(mercury // 30),)),
         BodyPosition("שבתאי", 286.0, False, (9,))],
        [], None, None, mode == "unknown", [],
        time_certainty=mode,
    )


def produce(chart: Chart, *, conflict=False) -> dict:
    source = interpret_chart(chart)
    if conflict:
        original = deepcopy(next(h for h in source["signals"]
                                 if h["axis"] == "יוזמה" and h["polarity"] == 1))
        original.update(rule_id="fixture-n2-counter", polarity=-1)
        source["signals"].append(original)
    r1 = synthesize(chart, source)
    n1 = compose_narrative(r1)
    semantics = build_personality_model(r1, source)
    n2 = compose_narrative_n2(semantics)
    return {
        "n1": format_narrative(n1),
        "n2": format_narrative_n2(n2),
        "semantic": semantics,
        "narrative_n2": n2,
        "narrative_n1": n1,
        "source_rule_ids": sorted({h["rule_id"] for h in source["signals"]}),
        "r1_node_ids": [n["id"] for n in r1["nodes"]],
        "time_mode": r1["time_mode"],
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "qa-output" / "n2-comparison"
    root.mkdir(parents=True, exist_ok=True)
    examples = {
        "a-known": produce(sample(12.4, 35)),
        "b-different-axes": produce(sample(72.4, 155)),
        "a-irrelevant-degree": produce(sample(14.5, 35)),
        "a-estimated": produce(sample(12.4, 35, mode="estimated")),
        "a-unknown": produce(sample(12.4, 35, mode="unknown")),
        "a-contradiction-fixture": produce(sample(12.4, 35), conflict=True),
    }
    assert examples["a-known"]["n2"] != examples["b-different-axes"]["n2"]
    assert examples["a-known"]["n2"] == examples["a-irrelevant-degree"]["n2"]
    # N1 may echo measured degrees in its witness quotations; only N2 prose is normalized.
    assert "שעת הלידה משוערת" in examples["a-estimated"]["n2"]
    assert "שעת הלידה אינה ידועה" in examples["a-unknown"]["n2"]
    assert any(c["classification"] == "unresolved_tension" for c in
               examples["a-contradiction-fixture"]["semantic"]["claims"])
    index = []
    for name, item in examples.items():
        ids = set(item["r1_node_ids"])
        rules = set(item["source_rule_ids"])
        for claim in item["semantic"]["claims"]:
            assert set(claim["node_ids"]) <= ids
            assert set(claim["rule_ids"]) <= rules
            assert claim["rule_ids"]
        for version in ("n1", "n2"):
            (root / f"{name}-{version}.txt").write_text(item[version] + "\n",
                                                       encoding="utf-8")
        (root / f"{name}-trace.json").write_text(json.dumps({
            "semantics": item["semantic"],
            "narrative": item["narrative_n2"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({
            "fixture": name, "time_mode": item["time_mode"],
            "n1_chars": len(item["n1"]), "n2_chars": len(item["n2"]),
            "n2_claims": len(item["semantic"]["claims"]),
            "n2_section_ids": [s["id"] for s in item["narrative_n2"]["sections"]],
            "note": "Synthetic fixtures; human semantic review still required.",
        })
    (root / "comparison-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("N2_COMPARISON_PASS", len(index), "full paired texts and lineage saved")


if __name__ == "__main__":
    main()
