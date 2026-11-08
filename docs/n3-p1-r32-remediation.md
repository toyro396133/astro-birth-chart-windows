# N3 P1 — R32 remediation and bounded contract amendment (2026-11-08)

**Status:** implementation in Draft PR #32 for independent re-review. This
document does not revise, merge or supersede the approved architecture PR #30.
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
without adding fields to, or changing, architecture PR #30, this implementation
extends the **derivation algorithm** of `plan_id` and `claim_id` to
`SHA256(canonical(object minus its own id))`. Previously documented identity
projections are insufficient: changes to `Plan.trace.adapter_trace_hash`,
`Plan.atomic_evidence_refs`, `Plan.relation_claim_state`, and to
`Claim.evidence_refs`, `Claim.semantic_delta`, `Claim.limits`, etc. could
leave the ID unchanged. The new derivation is intentionally stricter.

**Compatibility and review implications:** No existing production N3 objects
or approved gold cases exist, and P1 cannot emit Claims. Any future persistent
object identifiers must use this derivation and a versioned migration if schema
or stored-ID semantics evolve. Independent architecture review must explicitly
approve this bounded change before considering P1 accepted. No silent fallback
to the old weak projection is permitted.

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
