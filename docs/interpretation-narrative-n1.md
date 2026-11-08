# AstroBirthChart N1 — deterministic Hebrew narrative (first iteration)

## Scope

N1 is a **presentation/realization** layer over the approved R1 synthesis report.
It does not infer a new planetary position, rule, trait, functional transition,
context, confidence score or source approval. It runs locally in plain Python,
with no LLM, network, telemetry, generated assets or additional dependencies.

**Base:** `main` at AstroBirthChart v0.4.0 (R1 accepted and released).
**Implementation:** `src/astrochart/narrative.py`; GUI integration in
`src/astrochart/interpretation_dialog.py`.

## Pipeline

```
chart -> existing rules (96, unmodified) -> R1 synthesize() (unmodified)
     -> N1 compose_narrative(report) -> format_narrative()
     -> new read-only "קריאה רציפה (N1)" tab and copy action
```

N1 uses exactly the pre-existing R1 `summary.top_hypotheses`, matching
`nodes`, `rule_ids`, `source_refs`, statuses, and `time_mode`.
The prose puts maximal paths before standalone axes, omits axes already
explained by selected paths and preserves all unresolved tensions. It
presents up to 3 of the R1-ranked top paths and 4 standalone axes; unshown
hypothesis IDs are recorded and remain in R1's original tabs/JSON.

### Output contract

`compose_narrative(synthesis)` returns a versioned structured report:

- `sections[].paragraphs[].text` — user-facing Hebrew paragraphs.
- `paragraphs[].node_ids`, `rule_ids`, `source_refs`,
  `source_review_statuses`, `audit_status`, `provisional_time`
  — provenance carried from R1, rather than newly inferred.
- `displayed_hypothesis_ids` and `not_displayed_hypothesis_ids`
  — transparent view selection; this never deletes proof paths.
- `time_mode`, `warnings`, `source_engine_version`,
  `source_profile_id`, `source_rule_pack` — inherited context.

The existing structured model-ready JSON remains backward-compatible: a
new `narrative` key is added beside the unmodified `synthesis` data.
The old synthesis, interpretation, evidence and full proof tabs remain.

## Safeguards

- Every narrative *process* originates from a valid R1 hypothesis node with
  independent witnesses and rule IDs. It stays labeled **hypothesis**.
- Narrative text never labels editorial weight as likelihood or an
  empirical personality measurement.
- For estimated/unknown hours, the opening text and paragraph metadata
  retain the time caveat. No sample houses/aspects are introduced by N1.
- Contradictory evidence is presented explicitly as **unresolved**.
  No circumstances or person-specific explanations are invented.
- Empty reports produce an honest no-process message. N1 does not make up
  a higher-level inference when R1 found none.
- Re-running N1 on the same report is deterministic and does not mutate it.

## Verification

Focused: `python -m pytest -q tests/test_narrative.py`.

The existing Windows GUI acceptance (`tests/inspect_gui.py`) also checks
the read-only narrative tab, clipboard, structured JSON and real screenshots
(`narrative-known.png`, `narrative-unknown.png`).

## Limitations and future phases

N1 is a **rule-bound prose realizer**, not a fully capable Hebrew language
model. Style variation, complex discourse, user-selectable lengths, click-to-
inspect proof for each sentence, and natural wording derived from individual
rule texts remain follow-up candidates for N2/N3, separately reviewed.

N1 consumes R1 output only. The proposed R2 relationship discovery engine
remains a separate research task and is not implemented by N1. Its future
hypotheses must pass the same proof and quarantine safeguards.

The method remains symbolic/editorial; neither N1 nor R1 establishes that
astrological descriptions empirically predict individual personality.


## Correction after independent audit — N1-01 to N1-04

The findings in PR #25's independent audit are addressed within N1; R1,
astronomical calculations, the rule pack and release version are unchanged.

### N1-01: unresolved tensions retain both original evidence sides

Each tension paragraph now identifies the original R1 axis node and has
audit_status = unresolved. It carries the exact union of original rule IDs,
source URLs and review statuses. Its evidence_by_polarity value separates
positive and negative witnesses, rule IDs, source references, review statuses,
evidence keys and dependency roots. R1's shared_roots is retained.
If a supplied R1 tension conflicts with the witness groups on its axis,
N1 fails closed instead of emitting an unauditable contradiction.

### N1-02: functional explanation, not a list of labels

For each R1 path, N1 reads the existing path, domain, per-axis function
and selected independent witnesses. The Hebrew text describes the proposed
order of functional operations, notes why the intermediate operations matter
to the *proposed* sequence, and clearly states that links between functions
are model hypotheses, not person-specific observed behavior. The introduction
includes a short leading-process overview with the original process node's
same lineage. No transition, function, cause, context or fact is added by N1.

### N1-03: readable source-review statuses

A single source-status paragraph is computed from claims actually displayed
in the narrative. It distinguishes unverified, reviewed (not approved),
approved and conflicting sources when present. Approval of an individual
rule never promotes the hypothesis linking different rules. Routine repeated
R1 warnings remain unchanged in the structured warnings list, and are
summarized only once in the human-readable introduction and source disclosure.
Exceptional resource-bound warnings still appear explicitly.

### N1-04: standalone axis selection and exclusions

The renderer first uses R1's leading-axes order, then fills remaining slots
from the original R1 axis nodes in R1's descending-strength and alphabetical
tie-break order. At most four independently displayed axes may be shown, even
when the top five were covered by selected paths or have unresolved tensions.
The new displayed_axis_ids, not_displayed_axis_ids and excluded_axis_ids
fields explain what was shown, left over, or omitted due to process coverage
or tension. N1 never creates, reranks or alters the R1 nodes.

### Focused tests and actual output artifacts

The dedicated tests cover exact polarity-specific provenance, mixed source
statuses, four-axis fallback, supported functional transitions, overlapping
proof roots, time modes and deterministic replay.

Windows GUI QA exports four real R1-to-N1 rendering results:
- n1-known.txt — chart calculated with known birth hour.
- n1-estimated.txt — chart calculated in estimated-hour mode.
- n1-unknown.txt — chart calculated without a known hour.
- n1-contradictory-fixture.txt — actual R1/N1 algorithms running over a
  real known-hour chart with one intentionally synthetic opposing rule hit;
  this is a test fixture, not an inference about the person.

GUI screenshots include narrative-known.png, narrative-estimated.png and
narrative-unknown.png. narrative-long-scroll.png verifies scrolling,
selection and copy under repeated real report text; it is a layout stress
fixture, not a fourth independent semantic chart.
