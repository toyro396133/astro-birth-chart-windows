# AstroBirthChart — R0/R1 source map and compositional inference specification

**Scope:** first offline synthesis prototype; independent of wheel PR #8 and the original rules.
**Base:** main SHA 10ace63bd80fa358cfd22b5dd2c11857894c0c69 after PR #12.
**Design predecessor:** PR #13, docs/interpretation-synthesis-research-plan-20261108.md.
**Rule pack:** schema 1, version 0.2.0, 96 unchanged rules.
**Synthesis engine:** 0.1.0; profile western-tropical-whole-sign-r1.

This is a symbolic/editorial chart interpretation experiment, not an
empirically validated psychological assessment. Proof of deterministic
composition is not proof of a claim about a person.

## R0 — source/method map and competing choices

| Question | Source | Documented method | R1 decision and scope |
|---|---|---|---|
| Essential vs accidental dignity | [Skyscript glossary](https://www.skyscript.co.uk/glossary/dignities/), [Astrodienst](https://www.astro.com/astrowiki/en/Essential_Dignities) | Zodiacal dignity differs from prominence due to house, aspect or motion | Keep factor status separate from trait strength |
| Classical dignity point values | [Kerykeion v6](https://kerykeion.net/python-library/docs/v6/dignities), [Skyscript Lilly table](https://www.skyscript.co.uk/dig5.html) | Domicile +5, exaltation +4, detriment -5, fall -4; triplicity +3, term +2, face +1 under specified methods | Sign-only +5/+4/-5/-4 for seven traditional bodies, in factor_conditions **only**, not personality scoring |
| Sect, term, face | [Kerykeion v6](https://kerykeion.net/python-library/docs/v6/dignities) | Diurnal/nocturnal rulers, Egyptian bounds, Chaldean decans | Not computed; requires exact degree, sect and reviewed tables |
| Orbs and aspects | [Skyscript Orbs](https://direct.skyscript.co.uk/glossary/orbs/), [Skyscript Aspects](https://www.skyscript.co.uk/aspects.html) | Modern per-aspect and traditional planetary orbs differ | Keep existing aspect/orb computation and validation, no applying/separating assumption |
| House/zodiac policy | Existing domain code and PR #13 | Multiple tradition choices | Retain Western tropical + Whole Sign, no astronomy changes |
| Rule graph discovery | [AnyBURL](https://web.informatik.uni-mannheim.de/AnyBURL/), [PyClause](https://pyclause.readthedocs.io/en/latest/) | Path-rule induction, explanation and ranking | R2 only: R1 keeps explicit engineering transition edges |
| Inductive rule learning | [Popper](https://github.com/logic-and-learning-lab/Popper) | Positive/negative examples and background knowledge | Defer until a suitable labeled falsification dataset exists |
| Joint weighted reasoning | [PSL](https://psl.linqs.org/wiki/Rule-Specification.html) | Weighted soft conjunctions and constraints | Borrow transparent conjunction idea only: no PSL dependency, no probabilistic claim |
| Licensing | [Kerykeion PyPI](https://pypi.org/project/kerykeion/) | Kerykeion/libephemeris AGPL-3.0 | Reference documentation only. No third-party source copied or imported |

### Profile choices and limitations

- Zodiac: Western tropical; house system: Whole Sign. Other methods require separately reviewed profiles.
- Aspect/orb: preserve the existing astronomy and validated rule matcher, rather than silently adding alternative orbs, application/separation or dispositor rankings.
- Dignity: only sign-level classical domicile/exaltation/detriment/fall values; no triplicity, sect, term, face, retrograde or combustion policy. The partial score never multiplies a character trait.
- Rule weight: the existing editorial weight is preserved. Within each axis, witnesses using the same celestial observation are collapsed to **one maximum**. The score is editorial salience, not an empirical probability.
- Derived process strength: the weakest independent editorial witness (minimum), not an additive sum or an invented planetary coefficient. Each process also retains separate witness counts, source statuses and factor conditions.
- Audit: existing statuses unverified and reviewed are *not approved*. Newly derived functional relations always have status hypothesis, even when underlying editorial inputs have been reviewed.
- Context: a tension receives null context until a specific source-backed context rule is approved. Different chart-factor kinds cannot by themselves establish when a person's behavior changes.

## R1 — runtime algorithm, evidence dependence and inference graph

1. The old interpret_chart returns rule matches, unchanged, with chart evidence, polarity, reviewer status and evidence key. The astronomy stays under the old domain code.
2. Each witness is given a dependency closure: a placement uses its body's longitude; an aspect depends on both bodies' longitudes; a house depends on its body's longitude and the Ascendant. Custom shared evidence groups remain one group.
3. Deterministically choose disjoint highest-weight witnesses per axis; preserve overlapping witnesses as dependent facts, not independent votes. This guard works across **different** axes too.
4. Keep positive and counter witnesses distinct. An axis with opposition becomes an unresolved tension and cannot drive a positive new process. Never invent situational contexts.
5. A small explicitly authored engineering ontology assigns functional roles, domains and directed transitions (activation, maintenance, oversight; creation, analysis, reflection, expression; perception, coordination, balance).
6. A synthesis node is created only when every input axis was actually supported by independent chart observations. The new node records parent node IDs, the full set of leaf facts, original rule IDs, source links and review statuses.
7. Paths grow repeatedly while the actual graph supplies another compatible, independent witness. There is **no fixed number of abstraction levels**: parent paths must be shorter, so cycles and self-support are impossible. A 192-node resource cap guards CPU with an explicit warning if hit.
8. The new process is an **engineering hypothesis**, not a certified astrological rule. It never becomes a new source fact or a new rule in the 96-rule pack.
9. Render longer generalized processes first, then central axes, then detailed evidence; compute in the opposite direction, bottom-up.
10. The new output has its own schema 1, version 0.1.0 and separate method ID. No runtime network, model, training, dependency installation or source-rule mutation.

### Synthetic verification examples

Baseline: Sun 12.4° Aries, Mercury 5° Taurus, Saturn 16° Capricorn.
The original 96-rule engine produces separate positive axis signals:
initiative, persistence, responsibility. R1 can derive a new functional
process chain, initiative -> persistence -> responsibility, with complete
parent IDs and the actual three original rule IDs. There is no authored
finished placement-to-complex-trait rule for that chain.

Counterfactual: move Mercury from Taurus to Gemini, which removes its
persistence witness and the three-axis chain, while preserving initiative
and responsibility. An identical second Sun-Aries rule still counts only
once, even across different target axes.

Conflict test: inject opposite polarity on the same Sun Aries observation.
Both sides remain visible, the context stays unresolved, and chains using
that conflicted axis are blocked.

Unknown birth hour: the original matcher only admits sign-placements stable
through the possible interval. Noon sample positions cannot yield aspects
or house evidence. Derived conclusions remain provisional.

## Open engineering and research issues

- R1 composes actual evidence via a graph; it does **not learn new relation
  types**. The functional ontology and graph edges are engineering hypotheses
  requiring separate review. R2 may experiment with AnyBURL, Popper and
  counterexamples in a sandbox, without editing approved rules automatically.
- Greedy witness selection is deliberately conservative and may exclude a
  usable weaker but independent alternative. Exact set-packing or revised
  causal-dependency analysis is future work.
- A complete consistent astrological strength model is not implemented:
  house angularity, accurate sect/bounds, mutual receptions, aspect application,
  planetary motion and their interactions need a deliberate researched profile.
- No validated formula maps planetary dignity points to character-trait weights.
  Consequently partial sign dignity is descriptive factor context only.
- A user-feedback schema advertises choices A/B/both/neither/unknown, but
  collection and automatic learning are **disabled**. No birth data leaves the app.
- Derived relationship hypotheses do not claim scientific validity of
  astrology as a personality assessment.

## Verification commands

Focused: python -m pytest -q tests/test_synthesis.py
Full: python -m pytest -q (then existing Windows Actions gates)

Tests cover genuine multi-step novelty, counterfactuals, duplicated evidence,
cross-axis dependence, conflict with no invented context, cycle prevention,
unknown hour, dignity separation, deterministic results and regression
compatibility. The delivery PR should cite a real Actions run after it
completes, not merely report checks as passed before execution.
