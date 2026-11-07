# AstroBirthChart — Rule Interpretation Engine v1

## Scope and epistemic boundary

The astronomy is calculated by the preexisting JPL/Skyfield engine. The new
**symbolic** reading is an *editorial astrology rulebook*, **not** an
evidence-based personality assessment. Rules in v0.1.0 are a working
paraphrase of common modern Western astrological themes: **not yet checked
against individually cited authoritative primary texts**. They must not be
presented as classical quotations or as proven claims about a person.

No internet connection, LLM, network SDK, training pipeline, birth-data
upload or background process is added. No personally identifying data is
stored or logged by the interpretation engine.

## What is implemented

- ~48 starter patterns for solar/lunar/Mercury sign, selected aspects and
  selected Whole Sign houses, all on **western tropical** coordinates.
- Rule entries with stable \`id\`, \`type\`, \`when\`, \`axis\`, \`polarity\`,
  \`weight\`, Hebrew interpretive \`text\`, mandatory editorial \`source\`,
  and \`enabled\`.
- A versioned \`interpretation_rules.json\` pack; weighted, deterministic
  rule matches, supported and opposing signals per interpretive axis.
- Every generated statement carries the rule ID, actual computed chart
  evidence, author-provided source label and uncertainty flag.
- The report exposes a JSON structure for a future **local model**:
  computed facts, rule evidence, provenance and constraints.
- A native offline dialog provides tabs for summary, evidence and model-ready
  structure, with manual clipboard export.
- Same core functions support CLI/testing and UI; the visual component never
  recalculates positions.
- **No rule learns or changes itself**. Rule revisions require explicit
  authoring, versioning, review and tests. We deliberately do not train
  personality weights from user reactions.

## Rulepack format and safe development

Built-in: \`src/astrochart/interpretation_rules.json\`

Each active rule example:

\`\`\`json
{
  "id": "sun-sign-1",
  "enabled": true,
  "type": "placement",
  "when": {"body": "שמש", "sign": "טלה"},
  "axis": "יוזמה",
  "polarity": 1,
  "weight": 2.25,
  "text": "תיאור סמלי עברי של כלל ההצבה.",
  "source": "נוסח וגרסת מקור עריכתי, טעון בדיקת מקור"
}
\`\`\`

Other supported conditions:

- \`{"type":"aspect","when":{"pair":["שמש","ירח"],"kind":"ריבוע"}}\`
- \`{"type":"house","when":{"body":"שמש","house":1}}\`

Scores are **internal editorial rule weights**, not probabilities or measured
personality traits. Opposing polarity on a common axis yields an explicit
tension statement. Output is deterministic and traceable; it does not invent
traits to complete missing axes.

To evolve the rules without editing Python, write an **explicit** JSON overlay
with:

\`\`\`json
{
  "schema_version": 1,
  "base_pack_version": "0.1.0",
  "pack_version": "0.2.0",
  "rules": [
    {"id": "sun-sign-1", "enabled": false},
    {
      "id": "custom-communication-1",
      "enabled": true,
      "type": "placement",
      "when": {"body": "מרקורי", "sign": "תאומים"},
      "axis": "תקשורת",
      "polarity": 1,
      "weight": 1.25,
      "text": "כלל להדגשת תקשורת גמישה לפי המסגרת הסמלית.",
      "source": "ניסוי עריכתי מזוהה, גרסה 0.2.0"
    }
  ]
}
\`\`\`

Apply **only when deliberately requested** with
\`load_rulepack(overlay_path=Path("..."))\`. Overlays match the exact base
version, must bump their version, cannot run code or inject scripts, and
must state a new provenance when changing rule text/meaning. We do not auto-load
a file from users' home directories. Never silently take downloaded rules.

## Uncertain birth time

- If the hour is unknown, sign-based statements appear **only** if the body's
  sampled positions stay in a single sign across the day; the model payload
  records *all* candidates for an ambiguous body.
- No house or aspect personality statements are generated from midpoint
  placeholder values. No ascendant, MC or houses go into model payload.
- If an hour is approximate, house/aspect interpretation is withheld and the
  remaining sign statements are marked provisional.
- Warnings and rationale remain visible in both the report and structured
  context.

## Future model contract

\`model_input(chart, interpretation_report)\` is a data object, **not a
network request**. A model adapter must:

1. load only a user-selected *local* model with reviewed license and hashes;
2. consume computed chart facts and the list of rule evidence;
3. cite specific rule IDs for every personality claim and surface conflicts;
4. reproduce uncertainty limitations; fail closed on invented astronomical facts;
5. run the same known-hour/unknown-hour and contradiction benchmarks as v1.

## Models researched — 7 November 2026

- [Gtscoob86/astrology-sft-Q8_0-GGUF](https://huggingface.co/Gtscoob86/astrology-sft-Q8_0-GGUF):
  astrology fine-tune GGUF, 7B, Q8_0, ~7.7 GB. No established Hebrew
  evaluation, full-natal reliability or clear license disclosed in the
  accessible model card. **Not safe to redistribute without further checking.**
- [aungzaythant/gemma-4-E2B-astrology-v4](https://huggingface.co/aungzaythant/gemma-4-E2B-astrology-v4):
  4-bit model ~3.43 GB, model card describes mainly English/Burmese
  astrology narrative and explicitly lists occasional incorrect sign-planet
  associations. Model metadata labels license "gemma"; check full rights
  independently for redistribution. **Not assessed in Hebrew**.
- [aryaminus/astro](https://github.com/aryaminus/astro):
  is an agent-friendly deterministic astronomy/rules toolset, **not a
  pretrained personality interpretation model**. May inform *rule coverage*;
  no code copied.

**No model was downloaded or executed.** Numbers and capabilities above are
publisher-declared and need independent verification. Both models greatly
exceed the size of the current offline Windows installer. The default v1
release therefore contains only the lightweight rules engine.

## Acceptance gates

- schema, ID uniqueness, source attribution, input validation;
- deterministic outputs with evidence and contradictions, without diagnosing;
- no hour unknown -> no houses/aspect interpretation;
- overlay version match, rule disable/add/change with explicit provenance;
- GitHub Actions test suite including frozen EXE and Windows installer;
- graphical dialog and clipboard smoke tests.

Next editorial phase: define an authoritative tradition and collect cited
primary or licensed sources **rule by rule**, check translations, implement
a provenance registry, compare outputs against reviewed example charts, and
only then consider moving prototype rules to an approved rulebook.
