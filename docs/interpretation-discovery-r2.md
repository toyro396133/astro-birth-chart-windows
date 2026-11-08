# AstroBirthChart R2 — Isolated experimental relation and structure discovery

**Status:** experimental / hypotheses only. **Source:** `main` at
`f9f30197b11a4fdf7e87f95f35279053375936a9`; original R1
`synthesis.py` and N1 remain untouched. No release or merge.

## Why a separate engine

R1 already constructs deterministic, source-traceable, *predeclared*
functional paths. This R2 module does **not** repeat R1's authored
`TRANSITIONS` ontology or train a language model. It compares many
independent R1 reports and tests whether otherwise unconnected axes recur
together. Association is **not** causality, psychological diagnosis,
empirical validation of astrology, or approval of a new interpretation rule.

### Data flow

```text
Existing interpret_chart -> synthesize -> immutable R1 reports
                                    |
                                    v
   discovery_r2.discover(train_cases, validation_cases)
     -> strict schema/profile/time/tension checks
     -> axis alternatives + underlying dependency roots
     -> joint root-disjoint proof search per candidate and report
     -> support + partial counterexamples + independence baseline
     -> Apriori combinations (expand only if all immediate subsets recur)
     -> compare to *observed* contiguous R1 composition paths
     -> candidate relation / dynamic recurring-structure hierarchy
     -> separate out-of-sample validation + full leaf-to-source traces
     -> R2 hypothesis JSON; never fed back into R1 or N1
```

## Interface

```python
from astrochart.discovery_r2 import discover

result = discover(
    [{"id": "synthetic-01", "synthesis": r1_result}, ...],
    [{"id": "holdout-01", "synthesis": other_r1_result}, ...],
    min_support=3, min_lift=1.25, min_precision=0.65,
)
```

Use **non-identifying** case IDs; no date/place of birth is needed.
No filesystem/network writes or installed model. Accepts *only* R1 schema 1,
same interpretation profile and rule pack across all input cases.
`result["schema_version"] == 1` is a *separate R2 envelope*, not an
extension of the R1 schema. `result["hypotheses"]` contains hypothesis
IDs, member axes, confidence-free recurrence metrics, selected full
R1 witnesses, roots, node IDs, source URLs, review statuses, partial
counterexample IDs, held-out measurements and parent hypothesis IDs.

All discovered edges begin and remain in `hypothesis` state. There is
**no approve/promote API**; approval would require a separate process and
change review. Do not pass these records into R1/N1 as verified readings.

## Novelty, generalization and controlled falsification

- **New pairwise relation:** undirected `unreviewed-coactivation` with
  jointly root-disjoint evidence in at least three distinct R1 reports,
  lift above independent baseline and enough observed symbolic precision.
  It makes no direction/causal claim. An already observed R1 path is
  explicitly excluded from the novel list.
- **Higher structure:** frequent sets of three or more axes, extended
  recursively without a fixed abstraction level count. Each accepted
  higher pattern links to discovered subsets; its combination is an
  *anonymous recurrent concept*, not a human-invented trait name.
  More specific combinations are at a greater depth; pair patterns are
  the more general common core.
- **Evidence:** R1 `available_facts` are searched anew for each set,
  instead of reusing a potentially incompatible axis-wide choice.
  Only one factual witness per axis, with disjoint physical roots across
  axes. Every selected witness carries `evidence_key`, source refs,
  review statuses, rule IDs and original R1 node ID.
- **Counterexamples:** when some but not all member axes appear in an
  eligible chart, record `missing-R1-coactivation`. This is NOT a
  label that the person lacks a psychological trait; unmatched rules
  do not establish negative evidence about a person.
- **Falsification and holdout:** input witnesses can be changed in
  controlled test cases and the new R1 output mined again. Validation
  cases are kept fully separate, do not influence training novelty or
  thresholds, and can show partial counterexamples or dependent evidence.
  Holdout summaries are descriptive, not calibrated likelihoods.
- **Deduplication:** repeated identical R1 payloads count only once.
  Identical train/validation payloads and repeated IDs are rejected.
  Distinct signatures are **not** proof of statistically independent
  people, especially for a small synthetic dataset.
- **Conservative gates:** uncertain birth times, unresolved tensions and
  incomplete R1 proof searches are excluded from recurrence estimates,
  with explicit exclusion explanations. The R1 warning and contradiction
  objects are preserved in exclusions; no situational explanations
  invented. Unverified/reviewed R1 source statuses never become
  `approved`.
- **Resource bounds:** 512 cases per cohort, 32 input axes, 4096 candidate
  patterns, 20000 witness proof search states. If truncated, the warning
  declares non-exhaustiveness; a capped proof does not count as support.

## Real R1 experiment (synthetic astronomical configurations)

The script **runs the actual R1 rule interpreter and synthesis** on
12 synthetic configurations for training, one uncertain-time exclusion,
and 3 held-out configurations. Six training charts combine:
Sun Aries + Moon Cancer + Mercury Virgo; six controls use distinct
placements. Each uses varying Venus signs to avoid exact chart copies.
Holdout includes a normal chart, a controlled Mercury displacement and
a non-target control.

```bash
python -m pytest -q tests/test_discovery_r2.py
python scripts/run_r2_experiment.py --output r2-results.json
python -m pytest -q
```

The experiment prints an R1-vs-R2 comparison, the number of novel
candidates and held-out counterexamples. The optional JSON includes
full source traces. **Do not treat its synthetic examples as a real
population or claim an empirically validated personality predictor.**

## What R1 cannot, and R2 attempts

| Gate | R1 | R2 experimental |
|---|---|---|
| Predefined ordered functional compositions | Yes | Kept as historical baseline, not repackaged as novel |
| New cross-domain coactivation in corpus | No | Candidate only, if disjoint and recurring |
| Recurring combinations at several depths | Only authored transition paths | Data-driven frequent sets, no semantic label |
| Held-out symbolic counterexamples | Not a corpus evaluator | Separate validation with partial-exposure records |
| Root and source traceability | Yes | Reuse all original R1 leaves, with joint proof |
| Certify personality traits, causal links or astrology validity | No | No |
| Affect stable R1 or parallel N1 | N/A | **Never** |

## Integration boundary for future N1

N1 should keep using its current *unmodified R1 synthesis payload*.
A future owner-approved UI could expose a separate expandable
`r2_experiments` area clearly marked **not reviewed**, with the
`members`, `support_cases`, `validation`, `counterexamples` and
`source_review_statuses` fields. It must not weave R2 hypotheses into
ordinary readings or inflate R1 weight/rule counts.

## Limitations, open research

1. Repeated symbolic rule matches can correlate due to common rule
   inventory or sampled configurations; dependence between whole charts
   is not fully modeled.
2. This is frequent-pattern induction, not genuinely learned semantic
   relation typing, conceptual naming, causal discovery or a neural
   representation. It does *not* invent a defensible interpretation of
   why the axes co-occur.
3. Absence of a rule match is not a negative trait label. Reported
   `coactivation_precision` and lift are *descriptive toy-corpus metrics*.
4. Novelty is only relative to *paths observed in the supplied R1
   reports*: an authored R1 transition not instantiated in that corpus
   might be mislabeled as newly observed. A future reviewed, explicit
   ontology comparator is needed for stronger novelty.
5. The sample is small, synthetic and intentionally patterned. Require
   larger independent datasets, balanced cohorts, held-out evaluation,
   sensitivity analyses, cross-method checking and explicit source
   review before contemplating a product-facing claim.
6. Candidate/pruning and witness search have finite caps. Large
   corpora may be incomplete; warnings must be kept.
7. R2 produces no new approved rules, changing user-feedback schema,
   trained weights, telemetry, UI changes or Release.

## Change boundaries and verification

Changed/added in R2 only:
- `src/astrochart/discovery_r2.py`
- `tests/test_discovery_r2.py`
- `scripts/run_r2_experiment.py`
- `docs/interpretation-discovery-r2.md`

Unmodified: `src/astrochart/synthesis.py`, `src/astrochart/narrative.py`,
`src/astrochart/interpretation_dialog.py`, the 96 rules, astronomy,
Windows installer, release metadata and UI.

Tests include real R1 integration, novelty vs known R1 paths,
dependent-root obstruction, alternative witness rescue, duplicate
report obstruction, missing evidence and malformed input, dynamic
abstraction, controlled counterfactual, heldout partial counterexample,
uncertainty/contradictions, immutable inputs, version gate and determinism.
CI results should be recorded **after** real runs, not anticipated.
