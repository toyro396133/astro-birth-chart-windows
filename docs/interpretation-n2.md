# AstroBirthChart N2 — attributed personal Hebrew interpretation (experimental)

## Boundary

N2 is a **separate, offline, opt-in tab** downstream from the unchanged
interpretation rules and R1. N1 remains readable and the existing structured
`synthesis` and `narrative` objects are unchanged. R2 is independent and not
read here. No astronomical calculations, approval statuses, empirical character
predictions or new astrological rules are produced.

```
chart -> original 96 rules -> R1 -> N2 semantic claim graph
                                 -> paragraph planner -> Hebrew realizer
```

Source files: `src/astrochart/meaning_catalog_n2.json`,
`semantics_n2.py`, `narrative_n2.py`.
The catalog currently contains 13 explicit axis-meaning entries, exactly the
axes recognized by R1's `FUNCTIONS`. Its provenance is
`unverified` and it is **not** an approved rule source.
Every entry distinguishes an editorial definition, strength, challenge,
possible everyday example, and a possible recurrence across contexts.
This is not 13 ready-made report paragraphs: the model selects only eligible
R1 nodes, can combine existing R1 paths, and records attribution before the
realizer chooses discourse order.

## Data contract

`build_personality_model(synthesis, interpretation)` produces a versioned,
serializable `semantics` object with atomic `claims`, `plan` grouping,
time mode, catalog version, warnings, and explicit non-diagnostic flags.

Every *personality* claim has:
- original `node_ids` (R1), `rule_ids`, selected witness
  `evidence_keys`, dependency `evidence_roots`, `source_refs`,
  `source_review_statuses`, `provisional_time`, `audit_status`;
- original `meaning_ids` for editorial extensions;
- one classification: `existing_rule`, `editorial_extension`,
  `possible_behavior_example`, `synthesis_hypothesis`, or
  `unresolved_tension`; each comes with limitations.

Only `existing_rule` uses original rule text, matched on its selected R1
witness and rule ID. Editorial language never changes `unverified` or
`reviewed` to `approved`. Process examples are bound to **existing**
R1 path nodes and retain their hypothesis audit status. The directional
transition is explicitly described as hypothetical rather than a fact about
a person. Unresolved tensions carry separate positive/negative groups,
including their own rules, sources, roots and review statuses.

`compose_narrative_n2(semantics)` produces a distinct attributed
`narrative` structure; each rendered paragraph lists the exact contributing
claim IDs, R1 nodes, rule IDs, meaning IDs and source statuses. The local
`DeterministicHebrewRealizer` is a replaceable interface, not a third-party
model dependency. A later local generator must keep the verified semantic
plan/lineage and must not invent facts or new connections.

The existing GUI gains only an independent `פרשנות אישית (N2)` tab and
`העתק פרשנות אישית N2` button. The existing JSON adds
`personality_n2: {semantics, narrative}` beside the existing `narrative`
(N1) and `synthesis`. The meaning catalog is packaged in the frozen
Windows distribution.

## Editorial and uncertainty constraints

- Only axis nodes with valid independent positive R1 facts are interpreted;
  when unresolved opposite evidence exists, the axis paragraph is suppressed,
  and the opposing evidence is shown as a tension instead.
- N2 does not infer traits from unsupported isolated negative-only evidence.
- A multi-axis process requires the **existing R1 hypothesis node** and the
  exact independently selected proof witnesses. No new edge is mined.
- A lack of evidence results in a short explicit insufficiency message.
- `known`, `estimated` and `unknown` time status is inherited without
  recomputing natal houses, aspects or degrees. Uncertain-hour claims remain
  provisional, and the reader sees an explicit caveat.
- Scenarios represent what *might* occur in a generic situation. They never
  assert a person's actual profession, history, circumstances or milestones.
- Editorial selections are deliberately bounded (three primary axes, two
  secondary axes, two existing R1 paths). These presentation limits do not
  remove nodes or proofs from R1.
- Distinctive source-specific rule texts are shown only for selected R1
  witnesses. N2 does not claim the symbolic system is empirically predictive.

## Reproducible comparison and quality protocol

Run `python -m pytest -q tests/test_n2.py`, then
`python scripts/n2_comparison.py`. The script writes **complete**, paired
N1/N2 Hebrew narratives and exact JSON proof traces under
`qa-output/n2-comparison/` for six **synthetic test charts**:
A (known), B (meaningfully different source placements), A with an
irrelevant degree change, A estimated-hour, A unknown-hour, and a
synthetic opposing-rule fixture. These fixtures are for software tests,
not scientific validation.

For a Windows run, `tests/inspect_gui.py` captures the three native N2
screenshots, checks tab, copy and JSON behavior, and exports full Hebrew texts
for known/estimated/unknown conditions and the opposing fixture. The original
N1 screenshots and outputs remain.

Seven separate acceptance questions:
1. **N1 versus N2:** compare full narrative pairs; the presence of an everyday
   scene and meaningful strengths/limits matters, not character count.
2. **Different charts:** evaluate material differences in attitudes and
   concrete scenarios, not mere replacement of sign/body names.
3. **One changed fact:** expect a meaningful rule/axis/content difference for
   a significant source change and exactly equal output for a non-impacting
   same-sign degree change.
4. **Repetition:** find duplicate paragraphs, repeated claims, or boilerplate.
   The automated test rejects repeated exact paragraphs and duplicate claim IDs;
   semantic near-duplicates still require editorial reading.
5. **Traceability:** match each non-disclosure statement to original R1 nodes,
   witness groups, rules, editorial meaning and preserved statuses.
6. **Time/tension:** known/estimated/unknown, conflicting witnesses and empty
   evidence should never generate phantom contexts or fake exact chart facts.
7. **Human linguistic review:** have a separate reviewer judge each FULL
   paired report, blind to the engine name where possible, on clarity,
   naturalness, specificity to chart, explanatory depth, evidence fidelity,
   repetition, transitions, and non-diagnostic language (1–5 each). The test
   charts must not be limited to the cases used during development. Include
   reasons and line-level examples. **This human review is pending**, not a
   claim of having been performed.

### Remaining limitations (not acceptance claims)

The built-in editorial lexicon is initially only axis-level, not a
source-reviewed semantic analysis of all 96 individual rules. Original rule
text provides chart-specific content but some scenes will still be broadly
applicable to anyone with the same axis. R1 does not license an explanation
of *when* unresolved conflicts are resolved. Text length and grammar vary
modestly; this local deterministic realizer cannot match a capable Hebrew
language model in creative flexibility. Meaning units and examples should
receive independent semantic/linguistic review before adoption.

Draft PR only. Do not merge to main or publish a release before independent
engineering and linguistic acceptance.
