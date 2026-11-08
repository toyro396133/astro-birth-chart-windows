# AstroBirthChart — RCT-01: תכנון מנוע השוואת שעות לידה (Design only)

Status: PROPOSED / independent review required. Base: main @ `94e0829523ecc2bb5f15ef8cacfa990766b325c7` (2026-11-09). No implementation, merge, release, or N3 dependency.

## 1. Existing system and boundaries
Inspected `src/astrochart/{domain,engine,timeconv,chart_storage,ui}.py` on main. `Calculator.calculate(day,clock,zone_name,latitude,longitude,unknown_time=False)` computes local Skyfield DE440s planetary positions, Asc/MC, Whole Sign houses and aspects. `unknown_time=True` samples a civil day and explicitly omits angles/houses; it is **not** a rectification engine. `timeconv.valid_utc_instants` distinguishes ambiguous/nonexistent local times, and `local_to_utc` rejects both. `chart_storage` validates strict version-1 input and writes atomically; its schema must remain unchanged. PySide6 UI is RTL and currently owns a separate chart-file menu. `main` includes installer/updater logic; do not modify it in this design PR.

Architectural isolation: new optional `rectification/` domain/service + dialog, with no imports from N3, no changes to R1/N1/N2/N3 inference, no replacement of `Calculator.calculate`, no migration of existing chart records. Reuse ephemeris/time conversion through a small read-only adapter; N3 PR #30 is separate and must never be merged incidentally.

## 2. Inputs and contract
`RectificationRequestV1`: birth civil date, IANA timezone, latitude/longitude, optional city label, bounded local-time interval [start,end] (possibly crossing midnight), grid step minutes, event list, method/version, scoring profile and random seed for sensitivity analysis. Require date within engine-supported range, finite valid coordinates, explicit zone, start < end in a clearly defined UTC interval, maximum search window 48 hours, minimum step 1 minute, maximum 2881 candidates, maximum 100 life events, bounded strings and payload. Default coarse grid 15 minutes, optional refinement 1 minute around top clusters. User must explicitly acknowledge that events and results are interpretive, not scientific evidence.

Life events: `event_id`, event_type enum (relocation, education, career, relationship, family, health, other), event date or bounded date interval, optional time/zone, user-supplied short description, confidence (low/medium/high), significance (1–3), optional explicit unknown-date flag. No requirement to enter sensitive details; health/family examples should be optional, non-diagnostic. Reject events after current date only if explicitly presented as historical; allow hypothetical events only in a separate testing mode. Date precision and missing data propagate to scoring uncertainty; do not silently impute dates.

## 3. Candidate generation and astronomical semantics
Enumerate a deterministic half-open UTC instant interval derived from explicit local endpoints, converting each candidate back to labeled local wall time and offset. For DST folds include both distinct UTC instants and distinguish them in UI; nonexistent local times never become candidates. Invalid endpoint ambiguity requires explicit fold/offset selection. Cross-midnight and 23/25-hour days are tested. No arbitrary midnight midpoint substitution. Reuse `Calculator`/Skyfield DE440s and `ascendant_mc` for each candidate. Cache invariant birth-day planetary positions where justified only with an error bound; otherwise calculate exactly. Record Asc, MC, Whole Sign houses, bodies, aspects, input coordinates, UTC instant, offset, ephemeris identifier, tzdata version and method hash. If kernel missing, stop with actionable error. Existing unknown-time chart remains unchanged.

Event comparison is an **optional symbolic heuristic**, not a physical likelihood. Phase 1 must not claim validated predictive astrological links. Implement an explicit versioned rule catalog of candidate/event features, with each rule specifying mathematical calculation, activation window, rationale, weight, provenance, and epistemic status. If no reviewed event-feature rules exist, abstain from ranking rather than inventing coefficients. Any transits/progressions/solar arcs require a separate documented and reviewed rule contract; they are not silently assumed by this design.

## 4. Transparent score and abstention
For candidate c, event e and approved rule r: `a(c,e,r) in [0,1]` deterministic activation; `w_r >= 0` fixed, `q_e in [0,1]` declared confidence and `s_e in {1,2,3}`. Illustrative **structure only**:
`score(c)=sum_e(s_e*q_e*sum_r(w_r*a(c,e,r)))/sum_e(s_e*q_e*sum_r(w_r))` when denominator > 0. Publish all terms, rule IDs, matches, nonmatches, excluded events and denominators. Never interpret score as probability, certainty or true-hour estimate. Avoid double-counting correlated rules by grouping features and capping group contributions; freeze rule weights before evaluation. Empty, contradictory, imprecise or all-zero-evidence inputs => ABSTAIN. Report ranked *time windows/clusters*, ties, alternative candidates and score deltas, not a single definitive minute. Offer baseline flat/null score and leave-one-event-out results; a score that cannot beat baseline or depends on one event is explicitly unstable.

## 5. Stability, validity and falsification
Unit tests for grid determinism, UTC/local roundtrip, DST folds/gaps, midnight, high latitudes, invalid coordinates, finite scores, tie ordering, normalization and missing data. Metamorphic: permuting events leaves scores unchanged; duplicate events must not boost score; decreasing date precision must not increase certainty; small changes in grid, coordinates, event dates, weights and birth interval must not produce unreported sharp flips. Perform leave-one-event-out, bootstrap over events with fixed seed, alternative grid steps, and negative controls (shuffled event dates, synthetic events). Measure top-cluster overlap, rank correlation and score margin; set explicit thresholds in an independently reviewed fixture before claiming a stable ranking. No post-hoc tuning on the user's events. Tests must include synthetic fixtures with expected abstention. No scientific accuracy claims; observational validation would require independent preregistered datasets and comparisons to baselines.

## 6. Hebrew UX and accessibility
Optional dialog titled `השוואת שעות לידה אפשריות`, not `מציאת שעת הלידה`. Three steps: search interval and location; life-event input with optional details; results with sortable candidates, chart preview, rule-by-rule evidence, uncertainty and stability. RTL throughout; numerals/ISO dates/time-zone offsets remain readable in LTR spans; keyboard navigation, accessible labels, error focus, screen reader names, progress/cancel and responsive layout for 980x700. Computation in worker thread with cancellation, bounded memory and no GUI freeze. Warning visible before and after calculation: `ההשוואה מבוססת על כללים אסטרולוגיים פרשניים. אין הוכחה מדעית שהשיטה משחזרת את שעת הלידה האמיתית.` Never automatically overwrite known birth time or current chart.

## 7. Privacy, local persistence, security
Local-only by default, no network requests, analytics, cloud, LLM or event transmission. Separate opt-in `astro-rectification` JSON v1 (never embed life events in existing chart JSON v1); strict schema, max bytes, depth, field length and count; reject NaN/Inf, unknown fields, malicious paths, invalid time zones, duplicate IDs. Save atomically with fsync/replace and explicit user-selected path; no automatic save, no credentials, no event content in logs/crash traces. Export must redact descriptions by default, warn about sensitive life events, and allow explicit deletion. Recalculate from validated inputs on reopen; persist method/tzdata/ephemeris versions and flag changed outputs. Reject unsupported future schema without data loss. No pickle, eval, executable deserialization, unsafe HTML or arbitrary filesystem writes.

## 8. Delivery stages and acceptance gates
P0 (this PR): design-only, independent architecture/privacy/scientific-claims review, no runtime behavior changes.
P1: typed request/event validators, DST-safe candidate grid and deterministic tests, isolated module.
P2: independently reviewed versioned rule catalog + scoring and abstention, golden fixtures and adversarial stability tests; **no ranking if rules unapproved**.
P3: PySide6 Hebrew dialog, cancellable worker, local persistence and export, UI accessibility and privacy checks.
P4: Linux unit/integration, Windows packaged GUI smoke and file lifecycle, updater/installer and full/delta release regression, fresh install/uninstall, chart/N2/N3 separation and final integration verification.

Every stage needs tests and separate implementation PR(s), review comments addressed with HEAD-specific evidence, and explicit independent ACCEPTED before merge. Never merge on blockers; rebase on fresh main and inspect changed files to exclude N3. Final release requires genuine Windows installer testing and GUI evidence, not Linux-only simulation.

## 9. Design verification checklist
- [x] Read domain/engine/timeconv/chart_storage/ui from main; method and UI integration points identified.
- [x] Isolated from N3, existing chart schema and updater.
- [x] Defined input, candidate time semantics, event uncertainty, transparent score, abstention, robustness, Hebrew UI and privacy.
- [ ] Independent review and acceptance of rule catalog / scientific limitations.
- [ ] Runtime unit tests, Linux/Windows/GUI/release tests (implementation not started).
- [ ] Implementation authorization and downstream automation handoff.

## 10. Open decisions for independent reviewer
Rule evidence licensing and empirical status; exact candidate cap vs performance; DST boundary UX; event correlation groups; stability thresholds; acceptable minimum event count; report language and consent; compatibility with older saved files. Review must not turn interpretive score into validated probability.