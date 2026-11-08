"""Held-out N2 evaluation: independent real JPL charts + matched-axis controls.

The 20261108-stage2 seed and chart cases were fixed before observing outputs.
The generated set is a SOFTWARE holdout, not blinded human/psychological
validation. Full original N1/N2 texts, semantic-only N2 and trace JSON are saved.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, time, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from random import Random
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from astrochart.domain import BodyPosition, Chart
from astrochart.engine import Calculator
from astrochart.narrative_n2 import semantic_only_n2
from n2_comparison import produce


SEED = 2026110802


def fixture(*positions, mode="known"):
    return Chart(
        [BodyPosition(name, lon, False, (int(lon // 30),), house=house)
         for name, lon, house in positions],
        [], None, None, mode == "unknown", [],
        time_certainty=mode,
    )


def synthetic_pairs():
    """Not development's A/B, and no GUI QA chart/time is reused."""
    common = ("שמש", 251.7, None)
    return {
        "pair-persistence-mercury": fixture(common, ("מרקורי", 46.3, None)),
        "pair-persistence-mars": fixture(common, ("מאדים", 46.3, None)),
        "pair-persistence-both": fixture(common, ("מרקורי", 46.3, None),
                                           ("מאדים", 46.3, None)),
        "pair-responsibility-saturn": fixture(common, ("שבתאי", 289.8, None)),
        "pair-responsibility-house": fixture(("שמש", 251.7, 10)),
        "pair-material-shift-a": fixture(("שמש", 26.4, None)),
        "pair-material-shift-b": fixture(("שמש", 111.4, None)),
        "pair-irrelevant-degree": fixture(("שמש", 27.1, None)),
        "pair-unknown": fixture(("מרקורי", 45.6, None), mode="unknown"),
        "pair-estimated": fixture(("מרקורי", 45.6, None), mode="estimated"),
    }


def actual_jpl_holdout():
    """New dates never used by the earlier N2 design examples."""
    rnd = Random(SEED)
    calculator = Calculator()
    charts = {}
    for i in range(12):
        day = date(1992, 1, 1) + timedelta(days=rnd.randrange(0, 9500))
        hh, mm = rnd.randrange(0, 24), rnd.randrange(0, 60)
        lat = round(rnd.uniform(-39.0, 57.0), 3)
        lon = round(rnd.uniform(-110.0, 128.0), 3)
        chart = calculator.calculate(day, time(hh, mm), "Etc/UTC", lat, lon)
        charts[f"jpl-unseen-{i+1:02d}"] = chart
    return charts


def meaning_signature(report: dict) -> set[tuple[str, str, str]]:
    claims = report["semantic"]["claims"]
    return {
        (c["axis"] or "", c["content"]["focus"], c["content"]["distinction"])
        for c in claims if c["kind"] == "axis-example"
    }


def jaccard(a: set, b: set) -> float:
    return 1.0 if not a and not b else len(a & b) / max(1, len(a | b))


def evaluate(root: Path, samples: dict) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    reports, index = {}, []
    for name, chart in samples.items():
        item = produce(chart)
        reports[name] = item
        full_semantics = item["narrative_n2"]
        sem_only = "\n\n".join(semantic_only_n2(full_semantics))
        for suffix, output in (("n1.txt", item["n1"]),
                               ("n2.txt", item["n2"]),
                               ("semantic-only.txt", sem_only)):
            (root / f"{name}-{suffix}").write_text(output + "\n", encoding="utf-8")
        (root / f"{name}-trace.json").write_text(
            json.dumps({"semantics": item["semantic"],
                        "narrative": full_semantics},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        signature = sorted(meaning_signature(item))
        index.append({
            "case": name, "time_mode": item["time_mode"],
            "meaning_signature": signature,
            "n2_claims": len(item["semantic"]["claims"]),
            "n2_axis_readings": len(signature),
            "n2_process_hypotheses": sum(
                c["kind"] == "process-example" for c in item["semantic"]["claims"]),
            "excluded_from_semantic_text": "rule quotations, URLs, IDs, fixed disclosures",
        })
    labels = sorted(reports)
    similarities = []
    exact_repeats = Counter(
        text for name in labels for text in
        semantic_only_n2(reports[name]["narrative_n2"]) if text)
    for i, left in enumerate(labels):
        for right in labels[i+1:]:
            l = "\n".join(semantic_only_n2(reports[left]["narrative_n2"]))
            r = "\n".join(semantic_only_n2(reports[right]["narrative_n2"]))
            sa, sb = meaning_signature(reports[left]), meaning_signature(reports[right])
            similarities.append({
                "a": left, "b": right, "concept_jaccard": round(jaccard(sa, sb), 4),
                "text_similarity_without_quotes": round(SequenceMatcher(None, l, r).ratio(), 4),
                "same_meaning_signature": sa == sb,
            })
    def sign(name):
        return meaning_signature(reports[name])
    assert sign("pair-persistence-mercury") != sign("pair-persistence-mars")
    assert sign("pair-responsibility-saturn") != sign("pair-responsibility-house")
    assert len(sign("pair-persistence-both")) > len(sign("pair-persistence-mercury"))
    assert (semantic_only_n2(reports["pair-material-shift-a"]["narrative_n2"]) ==
            semantic_only_n2(reports["pair-irrelevant-degree"]["narrative_n2"]))
    assert (semantic_only_n2(reports["pair-material-shift-a"]["narrative_n2"]) !=
            semantic_only_n2(reports["pair-material-shift-b"]["narrative_n2"]))
    metrics = {
        "seed": SEED, "total_cases": len(reports),
        "real_jpl_charts": sum(n.startswith("jpl-unseen") for n in reports),
        "new_matched_axis_cases": len(reports) - sum(
            n.startswith("jpl-unseen") for n in reports),
        "method": "compare semantic-only text and curated meaning IDs, excluding quotes, proof IDs and disclosure; not psychological validation",
        "semantic_only_exact_repeated_paragraph_instances": sum(
            n-1 for n in exact_repeats.values() if n > 1),
        "semantic_only_distinct_paragraphs": len(exact_repeats),
        "pair_count": len(similarities),
        "signature_distinct_pairs": sum(not x["same_meaning_signature"] for x in similarities),
        "signature_equal_pairs": sum(x["same_meaning_signature"] for x in similarities),
        "comparisons": similarities,
        "indices": index,
        "human_linguistic_review": "PENDING_INDEPENDENT",
    }
    (root / "holdout-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print("N2_HOLDOUT_PASS", metrics["total_cases"],
          "real JPL", metrics["real_jpl_charts"],
          "signature-distinct pairs", metrics["signature_distinct_pairs"])
    print("N2_HOLDOUT_METRICS", json.dumps({
        "total_cases": metrics["total_cases"],
        "jpl_real": metrics["real_jpl_charts"],
        "pair_count": metrics["pair_count"],
        "signature_distinct_pairs": metrics["signature_distinct_pairs"],
        "signature_equal_pairs": metrics["signature_equal_pairs"],
        "semantic_exact_repeat_instances": metrics[
            "semantic_only_exact_repeated_paragraph_instances"],
        "semantic_unique_paragraphs": metrics["semantic_only_distinct_paragraphs"],
        "human_review": metrics["human_linguistic_review"],
    }, ensure_ascii=False))
    for name in ("pair-persistence-mercury", "pair-persistence-mars",
                 "pair-responsibility-saturn", "pair-responsibility-house",
                 "pair-persistence-both"):
        parts = semantic_only_n2(reports[name]["narrative_n2"])
        print("N2_HOLDOUT_EXCERPT", name, "\\n".join(parts).encode(
            "unicode_escape").decode("ascii"))
    return metrics


def main() -> None:
    charts = synthetic_pairs()
    charts.update(actual_jpl_holdout())
    evaluate(ROOT / "qa-output" / "n2-holdout", charts)


if __name__ == "__main__":
    main()
