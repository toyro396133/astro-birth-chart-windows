"""Build-time only: admit an immutable PR #29 N2 fixture against original rules.

This script accepts a local path, NEVER fetches a network resource and NEVER
writes into production. Only digests and non-personal admission results are output.
"""
import argparse
import json
import subprocess
from pathlib import Path
from astrochart.n3_contracts import digest, make_manifest, n2_content_digests, N3ValidationError, _assert
from astrochart.n3_n2 import verify_n2_catalog
from astrochart.synthesis import FUNCTIONS, TRANSITIONS, SYNTHESIS_VERSION

# Pinned by source review/CI, not supplied by the fixture or command arguments.
# A new PR29 HEAD must be separately reviewed and this constant deliberately changed.
REVIEWED_PR29_HEAD = "d03e4c8127007b70f69e28da7708097c46f901b4"
CATALOG_PATH_IN_COMMIT = "src/astrochart/meaning_catalog_n2.json"


def verified_committed_catalog(raw_file: bytes, git_head: str) -> dict:
    _assert(git_head == REVIEWED_PR29_HEAD, "UNTRUSTED_N2_HEAD: not independently pinned")
    repo = Path(__file__).resolve().parents[1]
    try:
        committed = subprocess.run(
            ["git", "show", git_head + ":" + CATALOG_PATH_IN_COMMIT],
            cwd=repo, capture_output=True, timeout=15, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise N3ValidationError("UNVERIFIED_GIT_HEAD: local Git commit unavailable") from exc
    _assert(committed == raw_file, "N2_PROVENANCE_MISMATCH: fixture does not match pinned git blob")
    try:
        return json.loads(committed.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise N3ValidationError("invalid pinned catalog bytes") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--locked-git-head", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    _assert(args.locked_git_head == REVIEWED_PR29_HEAD, "UNTRUSTED_N2_HEAD")
    rules_path = Path(__file__).resolve().parents[1] / "src/astrochart/interpretation_rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    catalog = verified_committed_catalog(args.fixture.read_bytes(), args.locked_git_head)
    validated = verify_n2_catalog(catalog, rules)
    ontology = {"functions": FUNCTIONS, "transitions": TRANSITIONS,
                "version": SYNTHESIS_VERSION}
    manifest = make_manifest(rules, catalog, ontology, r1_version=SYNTHESIS_VERSION,
                             n2_version=catalog["catalog_version"])
    cats, policies = n2_content_digests(catalog)
    report = {"upstream_ref_type": "git_blob_verified_locked_fixture",
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
