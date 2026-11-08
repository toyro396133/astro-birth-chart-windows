"""N3 read-only N2 category admission. No catalogs are vendored or merged.

Load only an explicit, immutable file/fixture and pin its SHA-256 digest.
A symbolic explanation is *never* a behavioral semantic atom or source license.
"""
from __future__ import annotations

import json
from pathlib import Path

from .n3_contracts import N2_CATEGORIES, N3ValidationError, _assert, digest


def verify_n2_catalog(catalog: dict, rulepack: dict,
                      *, locked_digest: str | None = None) -> dict:
    _assert(catalog.get("schema_version") == 1, "unsupported N2 schema")
    _assert(isinstance(catalog.get("catalog_version"), str) and
            bool(catalog["catalog_version"]), "missing N2 version")
    _assert(isinstance(catalog.get("rule_reading_policy"), str) and
            bool(catalog["rule_reading_policy"]), "missing N2 policy")
    _assert(all(isinstance(catalog.get(k, []), list) for k in N2_CATEGORIES),
            "N2 category must be an array")
    if locked_digest is not None:
        _assert(digest(catalog) == locked_digest, "N2 locked fixture drift")
    rules = {r["id"]: r for r in rulepack["rules"]}
    _assert(len(rules) == len(rulepack["rules"]), "duplicate RulePack rule")
    all_ids: set[str] = set()
    per_category: dict[str, set[str]] = {}
    for category in N2_CATEGORIES:
        items = catalog.get(category, [])
        ids = [x.get("id") for x in items]
        _assert(all(isinstance(x, str) and x for x in ids), "N2 missing item ID")
        _assert(len(set(ids)) == len(ids), "N2 duplicate ID in " + category)
        _assert(not (all_ids & set(ids)), "N2 cross-category duplicate content ID")
        all_ids |= set(ids)
        per_category[category] = set()
        for item in items:
            if category == "entries":
                _assert(item.get("kind") == "axis_meaning", "wrong axis content kind")
                continue
            rule_id = item.get("rule_id")
            rule = rules.get(rule_id)
            _assert(rule is not None, "N2 orphan rule " + str(rule_id))
            _assert(rule_id not in per_category[category], "duplicate rule in category")
            per_category[category].add(rule_id)
            _assert(item.get("source_rule_text") == rule["text"] and
                    item.get("axis") == rule["axis"], "N2 source text/axis mismatch")
            if category == "rule_readings":
                _assert(item.get("kind") == "rule_reading" and
                        item.get("eligible_polarity") == rule["polarity"] and
                        item.get("evidence_type") == rule["type"], "N2 reading mismatch")
                _assert(isinstance(item.get("behavior"), str) and
                        bool(item["behavior"]), "N2 reading missing behavior")
                _assert(item.get("provenance", {}).get("review_status") in
                        ("unverified", "reviewed", "approved"), "N2 provenance status")
            elif category == "symbolic_explanations":
                _assert(item.get("kind") == "symbolic-explanation" and
                        "behavior" not in item and
                        item.get("display_policy") ==
                        "non-behavioral-metadata-only-not-personality-N2" and
                        item.get("source_support") ==
                        "original-unverified-rule-text-only",
                        "symbolic explanation cannot become behavioral")
            else:
                _assert(item.get("status") == "quarantined-from-N2-display"
                        and isinstance(item.get("reason"), str) and
                        item.get("original_editorial_reading") is not None,
                        "withheld reading not quarantined")
    _assert(not (per_category["rule_readings"] & per_category["symbolic_explanations"]),
            "ambiguous eligible behavioral versus symbolic reading")
    _assert(not (per_category["rule_readings"] & per_category["withheld_editorial_readings"]),
            "withheld reading overrides eligible reading")
    _assert(not (per_category["symbolic_explanations"] &
                 per_category["withheld_editorial_readings"]),
            "symbolic/withheld overlap")
    return {"catalog_version": catalog["catalog_version"], "catalog_digest": digest(catalog),
            "category_counts": {k: len(catalog.get(k, [])) for k in N2_CATEGORIES},
            "eligible_rule_ids": sorted(per_category["rule_readings"]),
            "symbolic_rule_ids": sorted(per_category["symbolic_explanations"]),
            "withheld_rule_ids": sorted(per_category["withheld_editorial_readings"])}


def load_locked_fixture(path: Path, expected_sha256: str, rulepack: dict) -> tuple[dict, dict]:
    _assert(path.is_file(), "N2 fixture absent")
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise N3ValidationError("invalid N2 fixture JSON") from exc
    report = verify_n2_catalog(catalog, rulepack, locked_digest=expected_sha256)
    return catalog, report


def classify_rule(rule_id: str, catalog: dict) -> str:
    """Never backfill quarantined content from earlier catalog versions."""
    for k, kind in (("withheld_editorial_readings", "withheld_editorial_reading"),
                    ("symbolic_explanations", "symbolic_explanation"),
                    ("rule_readings", "behavioral_rule_reading")):
        if any(x["rule_id"] == rule_id for x in catalog.get(k, [])):
            return kind
    return "original_atomic_only"

