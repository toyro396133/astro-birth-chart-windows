"""Build-time only: admit an immutable PR #29 N2 fixture against original rules.

This script accepts a local path, NEVER fetches a network resource and NEVER
writes into production. Only digests and non-personal admission results are output.
"""
import argparse
import json
from pathlib import Path
from astrochart.n3_contracts import digest, make_manifest, n2_content_digests
from astrochart.n3_n2 import verify_n2_catalog
from astrochart.synthesis import FUNCTIONS, TRANSITIONS, SYNTHESIS_VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--locked-git-head", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert len(args.locked_git_head) == 40 and all(
        c in "0123456789abcdef" for c in args.locked_git_head)
    rules_path = Path(__file__).resolve().parents[1] / "src/astrochart/interpretation_rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    catalog = json.loads(args.fixture.read_text(encoding="utf-8"))
    validated = verify_n2_catalog(catalog, rules)
    ontology = {"functions": FUNCTIONS, "transitions": TRANSITIONS,
                "version": SYNTHESIS_VERSION}
    manifest = make_manifest(rules, catalog, ontology, r1_version=SYNTHESIS_VERSION,
                             n2_version=catalog["catalog_version"])
    cats, policies = n2_content_digests(catalog)
    report = {"upstream_ref_type": "locked_fixture",
              "upstream_git_head": args.locked_git_head,
              "n2_catalog_version": catalog["catalog_version"],
              "n2_catalog_sha256": digest(catalog),
              "n2_category_digests": cats, "n2_category_policies_digest": policies,
              "compatible_upstream_hash": manifest["compatible_upstream_hash"],
              "category_counts": validated["category_counts"],
              "accepted": True, "positive_gold_approved": 0,
              "production_enabled": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
