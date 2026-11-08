# N3 P1 — R32 remediation and bounded contract amendment (2026-11-08)

**Status:** implementation in Draft PR #32 for independent re-review.
The mandatory, narrowly scoped `N3-id-derivation-2` amendment was also
committed directly to the normative architecture document in open PR #30
at `deca96f44376d5fcc946d6b66b652ae0c203c0f5`, subject to independent
architecture re-review. Neither PR has been merged.
N3 remains entirely offline and unwired to production/UI (`ENABLED=False`).
No N3 source registry is externally approved and there are **zero** licensed
positive gold cases.

## Findings and implementation

| Finding | Repair | Negative acceptance |
| --- | --- | --- |
| R32-01 Source trust-root self-pinning | `PINNED_APPROVED_SOURCE_REGISTRY_HASHES=frozenset()` is compiled outside incoming JSON and caller arguments; `source_eligible` also rehashes registry. All P1 relation licenses blocked. | An attacker marking anchor/reviewer approved and recomputing all hashes, including passing the same hash as `trusted_source_registry_hash`, never receives a license. |
| R32-02 Missing atomic verifier chain | `n3_admission.admit_n3_bundle` is the only P1 admission result API. Checks full schema, exact installed RulePack/N2/R1 ontology and versions, manifest, registries, definitions, catalog, snapshot, actual chart + original RuleHit parity, Evaluation ID/trace, bindings, both route proofs, source conditions, semantic AST, Plan and zero Claims. Other helpers are not licensing APIs. | Partial Evaluation, forged binding/trace, missing adapter or unapproved Claim rejected. |
| R32-03 Claim/Plan content integrity | Full-content SHA256 for `claim_id`/`plan_id` (excluding only the ID itself), binding trace/evaluation/adapted data and verified atom IDs. | Mutating claim evidence, semantic_delta, limits, attribution or plan trace/claim-state while retaining ID rejected. |
| R32-04 R1 provenance | `map_r1_witnesses` re-runs `synthesize(chart, verified_report)` and requires exact original R1 node equality, plus selected member/alternative review status, source, polarity, roots, details and identities matched with the recomputed adapter. | Forged selected witness, alternative, metadata, source and status rejected. |
| R32-05 Typed inference | AST recursively bans nested negation of positive role facts; exact role-specific RulePack.when constraints and selected verified bindings; source matching conditions interpreted using Kleene TRUE/FALSE/UNKNOWN (never licensing unless TRUE); no inferred equivalence/novelty. | Wrong role, wrong fact, hidden not(all(...)), false and unknown source guards fail closed. |
| R32-06 RulePack parity / roots | Original `_validated_pack(raw_rulepack)` compared to actual runtime `RulePack`, source file SHA256 pinned at admission; `independent_roots_required` enforced per definition. | Same version, changed source/when/text/status rejected. Dependent roots not counted as independent; overlap is structurally retained only when independence=false, still cannot license a relation without external source verification. |
| R32-07 N2 immutable admission | All four categories explicitly required; preserve behavioral/symbolic/quarantine semantics. Admission compares full N2 content with installed immutable catalog, CLI independently checks pinned PR29 commit and exact `git show` bytes. | Missing category, changed policy, self-repinned content or forged git HEAD rejected. |

## Deliberate N3-contract-2 ID amendment — REVIEW REQUIRED

The normative schema provides **no separate `content_digest` property**
and has `additionalProperties:false`. To make full integrity enforceable
without adding fields to the frozen JSON Schema, this implementation
extends the **derivation algorithm** of `plan_id` and `claim_id` to
`SHA256(canonical(object minus its own id))`. Previously documented identity
projections are insufficient: changes to `Plan.trace.adapter_trace_hash`,
`Plan.atomic_evidence_refs`, `Plan.relation_claim_state`, and to
`Claim.evidence_refs`, `Claim.semantic_delta`, `Claim.limits`, etc. could
leave the ID unchanged. The new derivation is intentionally stricter.

**Compatibility and review implications:** No existing production N3 objects
or approved gold cases exist, and P1 cannot emit Claims. Any future persistent
object identifiers must use this derivation and a versioned migration if schema
or stored-ID semantics evolve. The formal change is recorded in
[PR #30 normative contract (N3-id-derivation-2)](https://github.com/toyro396133/astro-birth-chart-windows/pull/30)
with explicit NFC/UTF-8 canonicalization, full-object SHA256, stable array
order, versioning, cross-reference and migration requirements. Independent
architecture review must accept the amendment before P1 is considered final.
No silent fallback to the old weak projection is permitted.

## Trust and privacy

- The trusted external approval allowlist is intentionally **empty**. A
  self-declared `approved` field or caller-provided `trusted_source_registry_hash`
  cannot authorize any effect.
- P1 performs no user-facing output and no network requests. Git is invoked
  **only in build-time local fixture admission**, to compare a pinned commit's
  bytes to the candidate fixture. Birth/chart PII is not sent anywhere.
- Semantic term equality, source entailment, novelty, historical source
  certification and positive gold signoff remain separate human gates.
- The original RulePack, astronomical calculations, R1/N1/N2/R2 and original
  JSON Schema are unchanged. The P1 source adapter is read-only.
- Both routes are evaluated independently. A bounded R1 search is not a veto
  against independently proven composite evidence. However neither route can
  yield `RELATION_LICENSED` in P1.

## Explicitly postponed *production-only* hardening

PKI; private-key lifecycle; remote signing server; multi-user source-review
workflow; production operational roles/permissions; organization audit controls.
These are **not** substitutes for any P1 integrity check, and their deferral
does not grant source authorization.

## Re-review gate

Demand a final CI run on the reported SHA: adversarial Linux P1 suite, full
Windows regression (including GUI smoke, frozen EXE, release ZIP, installer,
installation/upgrade/uninstallation), and PR diff confirming no existing
engine/UI changes. Keep PR #32 **Draft** and do not merge/release/start P2.


## Second independent review — R32-08, R32-09 and R32-10 (P1-only)

The reviewer declared R32-01…07 **CLOSED** and found three new defects.
These fixes are additive to the prior trusted-source, adapter, schema,
RulePack and N2 checks; no original engines, ephemerides or GUI were edited.

### R32-08 — reasons must follow verified evidence

- \`n3_contracts._verify_decision_reasons\` independently derives the
  supported P1 reason predicates instead of accepting self-signed reason
  assertions. \`verify_plan\` always recomputes relation and source states,
  compares them with any supplied status arguments, and checks route-specific
  blocking attribution and original reason priority.
- \`MATERIAL_TENSION\` requires original \`synthesize\` tension involving a
  decisive proof axis and a failing/unknown conflict check.
  \`UNCERTAIN_TIME\` requires a non-known time mode, a provisional *selected*
  RuleHit and a nonpassing time check. \`DEPENDENT_ROOTS\` requires the source
  policy to demand independence, a nonpassing dependency check and exhaustive
  failure of independently disjoint role assignments among authenticated
  candidate bindings (subject to a fail-closed resource bound), not merely
  overlap among unused alternatives.
- \`INCOMPLETE_SEARCH\` requires a verified truncated R1 route, never a claimed
  metadata status. \`NO_RELATION_SOURCE\` derives from the separate pinned
  trusted review root and must appear as a *blocking* decisive-route reason in
  \`COMPARISON_ONLY\` without source authorization. R1 incomplete is
  nonblocking when an independently verified B route is decisive.
- Unsupported reason codes in a P1 admission **fail closed**; SHA256 is not a
  substitute for an independently established predicate. All reason evidence
  references, when supplied, must refer to known authenticated RuleHit IDs.
- Adversarial tests re-seal \`reasons\`, \`primary_reason\` and \`plan_id\`
  together, and attempt invented material tension, uncertain time, dependent
  roots, incomplete search and missing true source reason.

### R32-09 — a genuinely capped R1 path can have no output node

- \`n3_admission.verify_r1_route\` reruns original
  \`synthesis.synthesize(chart, report)\` and examines its top-level
  \`summary.proof_search_limited_paths\`; a caller cannot inject the list.
- For \`candidate/incomplete/unknown\` with no R1 node, admission requires a
  role-relevant \`r1_limited_path\` appearing in that freshly calculated
  limit list. The path must have **no emitted R1 synthesis node**; it is also
  rechecked via the original \`_base_features\` and \`_choose_path_proof\`
  against exact \`visited\`, \`MAX_PROOF_STATES\` and a chart/path-bound
  \`trace_hash\`. Bogus cap/path/visit values are rejected.
- Declaring \`not_candidate\` is forbidden if relevant source-computed limited
  paths exist. A separately proven original composite Route B is never
  vetoed merely because R1 has no selected path.
- The full admission test uses the real original algorithm under a
  deliberately restricted **test-only** path-search budget while normal
  base-feature computation remains unmodified; the R1 node is actually absent,
  while original composite B is proven. The result is
  \`COMPARISON_ONLY/NO_RELATION_SOURCE\` with nonblocking
  \`INCOMPLETE_SEARCH\` on A.

### R32-10 — semantic witnesses must be decisive-route proof members

- \`admit_n3_bundle\` compares the complete set of selected semantic witness
  IDs with the authenticated \`selected_binding_ids\` of
  \`Plan.trace.selected_decisive_route\`. \`verify_plan\` rechecks the same
  invariant and checks canonical selection count.
- Both \`evaluate_bound_predicate\` and \`source_conditions_state\` now
  resolve facts strictly from that decisive route's selected binding IDs;
  missing/ambiguous route selection is fail-closed.
- Positive test: genuine observed Mercury alternative remains available
  without altering the comparison of selected Sun/Moon evidence. Adversarial
  tests: append authentic extra witness, replace a selected witness, select a
  foreign-route witness or select the genuine unchosen alternative, recompute
  IDs, and confirm rejection.

### Preserved boundaries

The original \`synthesis.py\`, original interpretation RulePack, N1/N2/R1/R2,
astro/ephemeris calculations and GUI remain byte-for-byte untouched in PR #32.
\`ENABLED=False\`; the independent source-approval allowlist is empty;
positive approved gold remains zero; no claim is issued to users. PR #32 and
PR #30 remain under independent review; no Merge/Release/P2.
