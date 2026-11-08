# N2 independent audit remediation — REV-01 through REV-07

**Status:** implementation candidate for independent re-review; NOT ACCEPTED.
**Existing PR:** #27. **Review issue:** #28. **Original audited SHA:** `4dc1a3aad69c2f3674bd65f7586d11382d719676`.
**Base main:** `2962db7f27fec7c57f00fc0d9c11c9f987cba0f1`.
All interpretation claims remain **symbolic, editorial and non-diagnostic**. The new examples are **not** empirical psychological evidence.

## Boundary and integrity

Only N2 files, its Python tests, comparison scripts, documentation and CI
changed. The original 96 rule texts, their source and review status, R1's
synthesis/transition algorithm, N1, R2 and astronomical calculations remain
unchanged. The `personality_n2` JSON field remains backward compatible,
and the existing separate N2/N1/other GUI tabs and copy behaviors remain.

### REV-01 — Evidence-dependent semantics

- The `meaning_catalog_n2.json` catalog now contains 13 original axis
  entries and **26 specifically authored, unverified rule-level meanings**.
  Each rule reading records an exact original `rule_id` and unchanged
  `source_rule_text`, evidence type, focal concept, an explicitly
  hypothetical setting/behavior, a distinguishing emphasis, a limitation,
  and an editorial `unverified` status.
- The loader compares every editorial entry with the actual built-in
  rule text and rule metadata; it never changes or approves the rules.
- The semantic graph validates every selected independent R1 witness group
  against all original RuleHits and chooses eligible meanings by the exact
  rule ID and selected evidence. Distinct independent witnesses contribute
  distinct meaning units, up to the documented output limit.
- **Concrete contrast:** `mercury-sign-2` supports gradual thought and
  repeated examination; `mars-sign-2` supports persistence in *action*
  at a measured pace. These are not the same scenario. For responsibility,
  `saturn-sign-10` emphasizes long-horizon commitments and boundaries;
  `sun-house-10` emphasizes visible goals and structure, only for a known
  hour with a valid house.
- No curated reading means **abstention from a unique behavioral example**.
  The original rule quote can still be displayed separately for transparency.

### REV-02 — Content-based, bounded synthesis

- The original R1 path and selected independent witness group for **each
  component** are mandatory. Alternative valid R1 path witnesses from
  `available_facts` are supported without changing the R1 proof search.
- Every selected component is linked to its exact RuleHit and its distinct
  optional editorial reading.
- A process paragraph compares the *different sourced emphases* in those
  components. E.g., emotional need for continuity, steady effort in tasks
  and visibility of planned goals are not collapsed into a generic
  `and then` action sequence. The comparison is explicitly **not** proof
  of causality, a new cross-axis relation or an observed personality trait.
- When fewer than two distinct supported meanings are available, the
  process reports insufficient support for a concrete combination.
  This is an honest reduction in scope rather than an invented relationship.

### REV-03 — Meaning-level differential tests and new holdout

- `tests/test_n2_regressions.py` includes mandatory matched-axis scenarios,
  multi-witness comparison, R1 process with and without sufficient meaning,
  same-sign degree stability, known/unknown hour, tension display, source
  tampering and status-promotion tampering.
- `scripts/n2_comparison.py` still exports all six older N1/N2 pairs,
  preserving historical comparison.
- **New** `scripts/n2_holdout.py` produces 12 independently sampled,
  actual JPL DE440s calculated ten-body charts (new seed, dates, times and
  coordinates) and ten *separately prepared synthetic controls* including
  matched-axis/different-rule pairs, independent multi-witness pair,
  single meaningful change, irrelevant degree shift, estimated/unknown time.
  Every chart saves full N1/N2 Hebrew text, a `semantic-only.txt` file,
  and complete N2 claim/proof JSON. These are software verification inputs
  and should **not** be confused with a blind human validation sample.
- `semantic_only_n2` strips citations, raw rule quotes, URL, identifiers
  and fixed disclaimers, while comparing only semantic paragraphs.
- `holdout-metrics.json` contains per-chart semantic concept signatures,
  pairwise concept Jaccard, pairwise semantic-only text similarity,
  counts of exact re-used semantic paragraphs and separately defined
  meaning-unique/different pairs. None of these is a psychological score.

### REV-04 — Meaning-based variation

- A one-witness paragraph focuses on that rule's distinct emphasis and
  bounded scenario; a multi-witness paragraph compares *different*
  supported emphases and cautions against assuming they co-occur.
- Process paragraphs compare the actual R1-selected witnesses instead
  of concatenating actions with `ובהמשך`.
- Missing curated meaning is disclosed explicitly, never masked with a
  randomly selected scene. There is no external LLM, network dependence
  or random synonym scheduler.
- Semantic-only cross-chart near-duplicate and conceptual signature
  metrics are reported, including some expected repeats for semantically
  identical evidence. Near-duplicate linguistic acceptance still needs
  human judgment.

### REV-05 — Visible unresolved conflicts

- Tension paragraphs show both original **positive** and **negative**
  evidence lists: every RuleHit's evidence, rule ID, source URL, exact
  original text, and original review status.
- N2 keeps the two-sided JSON lineage unchanged and never claims a
  context that would resolve the tension. Inconsistent source metadata
  causes the tension to be omitted, not guessed.

### REV-06 — Hebrew and separation of prose from proof

- The deterministic realizer uses grammatical complete clauses, avoids
  `ייתכן גם נטייה` and a permanent definition/example/strength/challenge
  frame. Content-based structural variation depends on whether there are
  one, multiple, or zero curated witnesses, and on actual R1 path coverage.
- Each rendered paragraph now contains `semantic_text` (human explanation)
  and `evidence_text` (original proof and exact quotes). The existing
  `text` field contains both, for the unchanged Qt text view.
- We did **not** silently edit the original `saturn-sign-10` wording
  (`"לתיאור סמל"`): propose a separate owner-approved rule-catalog
  editorial correction after this N2 PR, with independent provenance review.
  N2's prose refers to the narrower, documented rule meaning without
  rewriting the original quote.

### REV-07 — Source integrity fail-closed

- The entire selected R1 evidence group must match the relevant RuleHits:
  rule IDs, evidence keys/details, source URLs, review statuses, polarity,
  and provisional time status. For built-in IDs, **source, exact rule
  text, original polarity, source URL and review status** must additionally
  match the unchanged canonical 96-rule pack.
- Tampering with either the RuleHit after R1 or with a claimed canonical
  `unverified -> approved` promotion even before R1 is rejected.
- Custom overlay IDs may appear as uncurated R1 evidence, but never gain
  the title of a reviewed built-in rule or an invented curated reading.
- No exact house/aspect is generated for unknown/estimated time.

## Reproducibility

Windows: `.github/workflows/windows-build.yml` now runs the full pytest
suite, original N1/N2 comparison, the 22-case holdout, actual GUI QA,
offline PyInstaller EXE, ZIP and Windows installer/upgrade/uninstall tests.
It uploads all reports and proof traces to `AstroBirthChart-GUI-QA`.

Linux: `.github/workflows/n2-linux.yml` runs full Python/Qt tests
(`QT_QPA_PLATFORM=offscreen`), pinned JPL ephemeris download, original
paired reports, and the independent 22-case holdout. It uploads artifacts
as `AstroBirthChart-N2-Linux-Holdout`.

A CI success is necessary **but not sufficient** for acceptance. A separate
reviewer must read *full* new N1/N2 comparisons, validate each reported
difference against actual rules, look for same-axis/repeated-meaning failures,
evaluate natural Hebrew and genuine chart specificity, and file a reasoned
`ACCEPTED`, `ACCEPTED WITH FOLLOW-UPS` or `CHANGES REQUIRED`
on PR #27. Do not merge or publish a release beforehand.

## Known limitations remaining

The other 70 of 96 original rules do not yet have a dedicated reviewed
behavioral meaning. N2 responds conservatively for those witnesses.
The 26 curated entries have **unverified editorial** status; "reviewed"
source rule status is not inherited by editorial behavior examples.
Purely deterministic, limited Hebrew realization cannot guarantee profound
synthetic insight; comparisons distinguish documented emphases but do not
prove interactions. Real JPL charts are independent heldout *inputs*, not
empirical evidence for astrology. Human blind language review remains open.
