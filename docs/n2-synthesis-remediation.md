# N2 composition / path completeness follow-up to independent CHANGES REQUIRED

**PR #27 / Issue #28.** Baseline `d40b55ce3cf7730ff8ce4f554d0b92fb7c392592`.
**Disposition:** engineering implementation for independent re-review, **NOT self-accepted**.
No changes to R1, N1, R2, original 96 rules, astronomy or Release. 
Rule-conditioned behavioral extensions stay editorial **unverified**.

## Structured planning, before Hebrew realization

`src/astrochart/semantic_plan_n2.py` plans from exactly the R1-selected
ordered path and selected validated witness for EACH path member. The plan
includes `members` (position, original rule, evidence and meaning if present),
`coverage` (total, covered and missing position/axis), pairwise `distinctions`
(from original source-specific focus, context, distinction and limitation),
`supported_readings` (only an ordered perspective on R1's **hypothesis**),
`unsupported_links` (joint observed conduct, causation, reinforcement,
predicted result) and `new_cross_axis_assertion_supported=false`.

A structured ordered perspective is NOT a new third psychological proposition.
With the 26 current unverified rule readings, no independently verified source
authorizes such a third proposition; therefore N2 explicitly abstains rather
than fabricate a deeper link. This is an honest epistemic limitation.

## Fixes and safeguards

- **REV-02:** content plan separates individual meanings, context differences,
  interpretive order, limitations and unsupported combinations, BEFORE Hebrew.
  Complete path coverage is necessary to phrase a whole-path reading.
  Original R1-selected witness groups remain intact in the plan.
- **NEW-01 HIGH:** first/middle/last missing member tests and partial
  comparisons expose which of the full three R1 path slots are uncovered.
  Text states `השוואה חלקית בלבד` plus `2 מתוך 3`, exact missing axes.
- **NEW-02:** independent R1 witness count is different from covered meanings
  (max 3 curated) and actually illustrated daily-life examples (max 2);
  multi-evidence examples explicitly disclose coverage, with no "two patterns"
  claim standing in for three sources.
- **NEW-03:** multiple abstained paths are grouped in one report paragraph.
  The original `process-reading` claims remain in `semantics.claims` and
  `semantics.plan.processes`; the narrative records every skipped path in
  `abstained_processes` and within the grouped paragraph.
- **REV-04/06:** full/partial/abstained paths use different exposition
  structures. Meaningful differences include original settings and the
  specific limits of different selected rules. A compact realization is used
  when raw source provenance is long; full material stays in JSON.
  Human editorial judgments on readability and depth remain outstanding.
- **Previously accepted REV-01/03/05/07:** catalog remains 26/96; existing
  source/status validation, two-sided unresolved tensions and previous sealed
  12-case regression remain unmodified.

## Reproducibility, new acceptance and before/after

`tests/test_n2_semantic_plan.py` adds first/middle/last missing path
members, full path with different selected meanings, 1–4 independent evidence
groups and two abstained paths in one report.

The six original synthetic N1/N2 examples remain in
`qa-output/n2-comparison/`. The new
`scripts/n2_before_after.py` runs original code from audited baseline SHA
in an isolated local Git worktree and writes six **complete** baseline-vs-current
N2 Hebrew reports with their original provenance traces, together with
`qa-output/n2-before-after/full-before-after.md`.
No old sealed JPL samples are used to train or tune this comparison.

`scripts/n2_acceptance.py` writes independently calculated actual JPL
charts, new synthetic controls, claim/evidence lineage and a quantitative
safety audit into `qa-output/n2-acceptance/` (instrumentation seed
`2026110863`). After a grammar correction found in an earlier validation, a separate new
seed `2026110913` is reserved for final acceptance under
`qa-output/n2-final-acceptance/`. Each supplies complete N1/N2,
semantic-only and trace JSON outputs. Do not use the final set to tune N2.

The output `uncovered-rules-impact.json` enumerates **70/96** rules,
frequency in the new reports, occurrence among selected path witnesses,
missing-curated-meaning contribution, canonical text and editorial triage.
The simple text-pattern cue is explicitly only a **research queue**, not
an editorial approval or an added meaning. No original rule is edited.

## Remaining limits and independent review criteria

Even a full three-member path can support a **bounded comparison**, not
a verified statement of psychological co-occurrence. Since selected rules
are editorial unverified, richer cross-axis causal stories remain unsupported.
The static 26/96 coverage still forces under-explanation and abstention.
Metrics like 66/66 meaning signatures do not validate creativity; evaluate
full new passages, partial coverage, context distinctions, source fidelity,
different vs repeated Hebrew patterns, and omitted pathways independently.

The branch stays Draft. **Do not merge or release.** Reviewer must decide
ACCEPTED / ACCEPTED WITH FOLLOW-UPS / CHANGES REQUIRED separately.
