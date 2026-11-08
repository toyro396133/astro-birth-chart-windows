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
