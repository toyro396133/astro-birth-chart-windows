# AstroBirthChart — R2 research sandbox and independent audit corrections

**Status:** isolated Draft PR #26; no merge, release, UI change or promotion.
**Base:** `main` @ `f9f30197b11a4fdf7e87f95f35279053375936a9`.
**Audit:** [R2-01..R2-08 CHANGES REQUIRED](https://github.com/toyro396133/astro-birth-chart-windows/pull/26#issuecomment-6716973674).
**Boundaries:** Never modify `synthesis.py`, N1, the 96 rule JSON, astronomy or user-facing interpretation.

## The three distinct research claims

| Claim | What would establish it | Current result |
|---|---|---|
| 1. Recurrent symbolic feature combinations | Independent R1 witness roots within cases, repeated across more than one genuinely distinct evidence/template signature, reproducible checks | **Demonstrated only for designed synthetic patterns**, with source/proof caveats |
| 2. Relation type *not in* the R1 ontology | Full directed-ontology comparison **plus** independently inferred meaning, direction or tested relation semantics | **Not demonstrated**; crossing R1 domains is not itself a learned relation |
| 3. New conceptual generalization and downstream inference | Abstraction with independent semantics, held-out novel inference and explicit falsifiable targets | **Not demonstrated**; a larger frequent set is not a newly understood concept |

R2 output fields `semantic_relation_discovered=false` and
`conceptual_generalization_demonstrated=false` are intentional.
`level` is combination width minus two, *not* a semantic abstraction depth.

## API and architecture

```python
from astrochart.discovery_r2 import discover

out = discover(
    [{"id": "nonidentifying-case-id", "synthesis": r1_result,
      "source_id": "optional-source-group",
      "independent_record_id": "optional-deduplicated-source-record"}, ...],
    [{"id": "pre-split-holdout", "synthesis": heldout_result}, ...],
    min_support=3,
    min_lift=1.25,
    min_precision=0.65, # backward-compatible argument; now SYMBOLIC ratio
    min_unique_signatures=2,
)
```

The *separate R2 envelope* keeps R1 schema 1 input unchanged. Flow:

1. Parse/validate R1 evidence, profile, pack version, statuses, source refs,
   proof limits, time certainty, unresolved tensions and original rule IDs.
2. Compute three distinct identities: unmodified raw report SHA (audit only),
   canonical full-report **evidence** SHA (non-editorial), and per-candidate
   selected-witness **signature** and broader rule-based **template**.
   Decorative labels, headings, and presentation metadata do not mint
   new evidence. With no declared record identity, identical canonical
   evidence is excluded as a possible copy; with different explicit record
   identities, keep separate cases but never count one evidence pattern
   more than once for the diversity threshold. Declared identities are
   metadata, not externally verified evidence of distinct people.
3. For each candidate, re-run bounded, deterministic joint witness search
   across *all* R1 available alternatives, enforcing root disjointness
   within reports. Preserve leaf R1 node IDs, evidence keys, roots,
   source refs, source review statuses, rule IDs, all missing-source flags.
4. Enumerate all directed `FUNCTIONS`/`TRANSITIONS` R1 paths satisfying
   same-domain restriction and no cycles; compute stable SHA ontology ID.
   Classify each recurrent set as `observed-r1-path`,
   `authored-r1-path-not-observed`, or
   `not-derivable-as-directed-r1-path`. R1-authored but unseen paths
   are **not** novel hypotheses; neither are existing observed paths.
5. Recurrently mine candidate sets bottom-up via subset joins, only
   promote to *research hypothesis listings* when distinct evidence
   signatures and distinct rule templates meet independent gates,
   train-only symbolic ratio and marginal-frequency lift meet frozen
   thresholds, and no R2 witness search was truncated.
   Otherwise keep recurrence in a distinct `recurring_but_not_diverse_patterns`
   list with reason; never silently discard repeated but weak patterns.
6. Evaluate an explicitly pre-split held-out cohort. Support based on
   the same target witness signature as training is recorded under
   `reused_signature_cases`, never as new held-out support.
   The prespecified **toy symbolic** gate requires at least two new
   held-out support signatures, ratio >= the frozen training threshold,
   and complete witness search. A failed/empty/contaminated holdout is
   reported as a failure or **unproven**, not concealed.
7. Keep `search.candidate_enumeration_complete`,
   `search.witness_proof_search_complete`,
   `search.r1_input_search_complete`, and the conjunction
   `summary.search_complete` distinct; report all affected candidates
   and all excluded R1-limited cases. A resource-truncated search cannot
   establish a negative proof.

**Provenance**: status vocabulary is validated (unverified, reviewed,
approved, conflicting, rejected). Empty source refs/statuses remain visible
as `missing_provenance_axes`. An `unverified` source or missing source
does not become approved by repetition, even if a holdout gate passes.
Every R2 candidate begins and stays `hypothesis`; there is no write-back
to the rule pack or N1.

**Hypothesis identity** is `sha256([profile, source_rule_pack,
R1 ontology digest, members, R2 version])` (truncated for display).
Editorial changes do not change the ID; changing pack version or ontology
does. No new non-reviewed semantics are authored to ensure a passing test.

## Explicit metrics and evidence categories

`metrics` reports: `supporting_report_count`,
`distinct_evidence_signature_count`, `distinct_data_template_count`,
`declared_data_source_count`, and `source_independence_verified=false`
separately, plus counts of missing/unverified sources. Unknown source
independence is not silently treated as a new independent source.

Also recorded: full independent support, partial-axis exposure, absent
matching axes, fully observed but root-dependent evidence, R2 proof search
incomplete, and entire case excluded due to R1 uncertainty/contradiction/
resource cap. These categories must not be merged.

`symbolic_coactivation_ratio = full / (full + partial)` is a descriptive
conditional co-occurrence rate, **not predictive precision**. The numerator
and denominator are exposed; absent/dependent/incomplete/excluded cases do
not enter this particular denominator, but retain explicit counts.

`lift_over_independent_presence` compares full independent support to a
product of marginal axis presences. This comparison assumes a null model
of independent axis occurrences, which is **not generally valid for the
rule pack**. Neither metric measures personality, causality, probability
of an attribute, or source reliability.

A case-based 95% Wilson interval is included for transparent sampling
variability **conditional on independent Bernoulli cases**; duplicated
patterns invalidate this assumption. No population confidence claim
should be based on this interval.

## Required experiments (real R1 interpreter and synthetic chart facts)

Commands:

```bash
python -m pytest -q tests/test_discovery_r2.py
python scripts/run_r2_experiment.py --output r2-results.json
python scripts/run_r2_review_experiments.py --output r2-review-results.json
python -m pytest -q
```

R2-specific CI executes these in Linux **and** Windows, and retains both
full JSON results as artifacts. The existing Windows offline build
workflow is independent and must also pass before engineering acceptance.
Both experiments are CPU-only, offline, no network/model/dependency additions.

### Old original trial — corrected interpretation

The same R1 data are replayed: 13 input, 12 time-eligible reports and 3
held-out reports. Previously the same eight recurrent patterns were
announced as 8 hypotheses (6 pairs, 2 triplets), each with **six supporting
reports but only one selected-witness signature**, and the holdout positive
reused its original witness pattern.

**After correction:** the 8 combinations remain visible as
`recurring_but_not_diverse_patterns`, but 0 qualify as sufficiently
diverse research hypotheses. R1's 4 observed composition paths are
compared against **all 26 possible authored directed paths** (14
directed transitions), including unobserved ones. No Level 2/3 claim.

### New grouped protocol (not real-world independent validation)

`scripts/run_r2_review_experiments.py` freezes
`min_support=3, min_lift=1.25, min_symbolic_ratio=0.65,
min_unique_signatures=2, min_templates=2` before inspecting holdout.
The train/holdout evidence signatures are explicitly checked to be
disjoint before running the miner. All examples remain synthetically
constructed from original R1 placement matching, not a field population.

| ID | Probe | Expected interpretation |
|---|---|---|
| A | 30 editorial variants of same R1 evidence | 1 eligible anonymous report, 29 canonical duplicates, 0 hypotheses |
| B | Full R1 ontology including unseen authored paths | 26 possible directed paths, authored-but-unseen not novel |
| C | New witness-signature holdout plus partial/absent controls | Candidate can pass **predeclared symbolic** holdout gate; external generalization still unproven |
| D | Venus Aries -> Taurus change on a held-out witness | Triple joint proof disappears, without changing other independent facts |
| E | 1,200 seed=20261108 independent axis-column permutations | Marginal frequencies preserved, not roots/astronomical constraints or multiple-testing correction |
| F | Artificial `MAX_PROOF_STATES=1` | Search flagged incomplete; affected candidates recorded; no false negative |
| G | Lift/support/ratio sensitivity grid | Counts vary or remain stable and are documented; no retuning to rescue holdout |

A/B/D/E/F/G alone are not semantic learning. Passing C demonstrates
only an engineered generalization of symbolic coactivation over new
**selected rule signatures**. No independently sampled external
dataset, rule-source approval, semantic mechanism or causal target exists.
Thus `external_generalization_proven=false` remains mandatory.

## Review finding coverage

| Finding | Implemented control |
|---|---|
| R2-01 | Independent case counts, unique evidence signatures, distinct rule templates, declared source groups |
| R2-02 | Split by proof signatures prior to threshold selection; frozen holdout pass/fail protocol and negative controls |
| R2-03 | Complete authored R1 directed ontology, including domain and direction |
| R2-04 | Canonical evidence fingerprint ignoring editorial metadata; adversarial repeated-report tests |
| R2-05 | Descriptive ratio with explicit denominators, all case categories, Wilson caveat, seeded permutation, sensitivity |
| R2-06 | Three separate search-completeness gates, R1 cap and R2 train/holdout capped witness search |
| R2-07 | Reviewed status vocabulary validation, explicit missing/unverified source counts and no auto-promotion |
| R2-08 | Stable ID includes source-rule-pack version and full R1 ontology fingerprint |

## N1 interface and unresolved limitations

N1 **must continue to read only original R1 data**. R2 must remain
a separate read-only research output, never a personality/narrative
assertion. R1 and its original rule pack are neither changed nor trained.

Residual limitations: evidence signatures based on rule and underlying
fact keys can conceal dependencies shared across different *people*;
declared record/source IDs are not independently verified; an adversary
with fabricated evidence records can create artificial variety. The
small designed synthetic sample has selection bias, shared rule
inventory and correlated placements. The permutation baseline destroys
physical dependency constraints; Wilson intervals rely on questionable
independence. Neither novel causal mechanisms nor newly understood
concepts are learned. These are research blockers for Level 2 and 3,
not unit-test defects to mask with hand-authored semantic mappings.

**No automatic approval, main merge, UI promotion or Release.**
