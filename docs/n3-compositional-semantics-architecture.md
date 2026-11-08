# AstroBirthChart — N3: ארכיטקטורה מתוקנת למשמעות משולבת מבוססת מקור

**סטטוס: DESIGN ONLY · תיקון ARCH-01…ARCH-08 · דורש ביקורת ארכיטקטורה עצמאית חוזרת · אין אישור מימוש.**  
**תאריך:** 2026-11-08. **בסיס PR #30:** 95502df52ded50779359e17865d994c3245c0cb7.  
**תלויות:** PR #27 (HEAD בעת התכנון 7ca47f0ede8c4e0a7aca0ab9ce45944bdfbd4558), PR #29 (HEAD שנבדק 9a8896a4832f2ac78120268510f9de05641f41e3).  
**מקור דרישות:** ביקורת PR #30, תגובה 6718402065. **אופי הפעולה:** החלפה ותיקון של המפרט הקיים, לא פיתוח N3.

## 0. תזה, מצב מוכח והכרעת היתכנות

N3 הוא מנוע **הסקה סמלית מורשית־מקור**: משמעות משולבת מותרת רק כאשר תנאים במפה מתאימים להגדרת יחס, והמקור הפרשני מתיר את *היחס המסוים* ואת גבולות הניסוח. אין ראיה אמפירית לאישיות; רישוי מקור אסטרולוגי איננו רישוי סיבתי/מדעי. קריאת N2 אטומית אינה הופכת לטענת קשר גם אם היא מנוסחת היטב. הופעת R1 path, צמידות מילים, או coactivation ב־R2 אינן מקור ליחס.

**ממצאים מאומתים מקבצי המאגר:** RulePack schema 1, pack_version 0.2.0, כולל 96 כללים: 72 placement, 11 aspect, 9 house, 4 composite. ארבעתם enabled, review_status=unverified, modifier_only בעת ההתאמה, עם weight אפקטיבי 0. R1 אינו קולט modifier_only למועמדים, מוגבל ל־MAX_NODES=192 ו־MAX_PROOF_STATES=20000. N2 catalog ב־PR #27 הוא 0.2.0 / 26 rule_readings; בענף האח PR #29 הוא 0.3.0 / 86, כולן עריכתיות לא מאומתות; ארבעת כללי ה־composite ללא rule_reading בשני הענפים.

**תוצאת P0 ראשונית:** לכל ארבעת כללי ה־composite המקורות המשויכים ב־RulePack הם framework-only ואינם מאשרים פרטנית קשר. במהלך בדיקה נפרדת אותר *מועמד מקור היסטורי פרטני* ל־sun-aries-moon-taurus בספר Alan Leo, Astrology for All (1899), פרק XVIII, עמ' 62. טקסט מהדורה סרוקה ותעתיק זמינים (ראו סעיף 7). זו עדות טקסטואלית ספציפית מועמדת, **אך טרם הושלמו ביקורת מקור עצמאית, אימות מסגור/תנאים, השוואה דקדקנית למשמעות המותרת ואישור בודק**. לפיכך מספר מקרי gold חיוביים *מאושרים לפרסום* כעת: **0**. תכנון וניסויי Shadow יכולים להימשך; אין שינוי בדוח משתמש.

## 1. חוזה ארכיטקטורה והפרדת שני מסלולי האיתור — ARCH-01

~~~text
CHART + ORIGINAL RULEPACK(96) + EXACT RULEHITS
             |                         |
             |                         +--> Route B: ORIGINAL COMPOSITE RULEHITS
             |                                  (modifier_only; exact when.all)
             +--> R1 READ-ONLY --> Route A: R1 SELECTED PATHS
                                     (selected witnesses + alternatives)
             |                         |
             +----------- Candidate union / dedupe by (definition,bindings)
                                       |
                            EvidenceMatcher (exact; revalidate original facts)
                                       |
                       RelationDefinitionCatalog (no chart fields)
                                       |
                         SourceLicenseGate (independent of chart facts)
                                       |
                     RelationEvaluation (proof + all refusal reasons)
                                       |
                   N3 Plan --> Novelty/Entailment --> NarrativeClaim
                                       |
                           Shadow deterministic realizer (future)
~~~

**Route A — R1-selected:** לכל path שנבחר, שמור את סדר הצמתים, domain, המשתתפים, alternative_facts_by_axis, selected_witnesses_by_axis, proof_search.complete, הראיות והסטטוסים של כל חבר. צור candidates רק עבור RelationDefinitions שתנאי המשתתפים שלהן מתקיימים, בלי להסיק יחס מ־TRANSITIONS. מסלול R1 אינו תנאי הכרחי להפקת יחס.

**Route B — original composite:** סרוק *כל* RuleHits המקוריים מסוג composite (כולל modifier_only). אימת שוב מול RulePack: enabled, id, version/hash, when.all וכל סעיף placement קיים בדיוק במפה ונבדק באותו time_mode. דרוש התאמה של שני ה־related_rule_ids ובדיקה ישירה של העובדות המקוריות — לא רק התאמת axis, טקסט, או evidence_key. חבר למועמד הגדרת יחס מחקרית המבוססת על original_composite_rule_id ועל source anchors נפרדים; אם אין RelationDefinition מורשית, החזר candidate לא מורשה עם סיבה. **אין להוסיף את ה־composite כראיה אסטרונומית עצמאית**: הוא מצביע על שתי תצפיות הבסיס, לא על תצפית שמימית שלישית, ומשקלו האפקטיבי 0.

**מפת כיסוי לארבעת הכללים:** 
- sun-aries-moon-taurus: שמש/טלה + ירח/שור; יוזמה+יציבות, ללא R1 edge מתאים — Route B מחייב.
- mercury-virgo-saturn-capricorn: מרקורי/בתולה + שבתאי/גדי; חשיבה (עיבוד)+אחריות (ביצוע), ללא R1 cross-domain — Route B.
- venus-libra-mars-libra: ונוס/מאזניים + מאדים/מאזניים; שיתופיות→הרמוניה יכול להיות מסלול R1 בתנאי המפה, אך Route B עובד גם בלעדיו.
- sun-sagittarius-mercury-sagittarius: שמש/קשת + מרקורי/קשת; עצמאות (קשר)+גמישות (ביצוע), ללא R1 cross-domain — Route B.

**כללי union:** מפתחות מועמד הם (definition_id, semantic_definition_version, ordered_bindings_hash); במקרה של שתי דרכי איתור שמור discovery_routes=[r1_path,original_composite], raw_candidate_ids ו־RuleHits תואמים. לעולם אין להכפיל ראיות/ספירת עצמאות בגלל שני מסלולי איתור. כלל composite חסר אינו ראיה להעדר יחס אחר; RelationDefinitions ישירות יכולות להגדיר predicates נפרדים כאשר יש מקור מפורש מתאים.

## 2. שלושה חוזים עצמאיים, גרסאות וזהויות — ARCH-02

שלושה סוגי אובייקטים בלבד, ללא שדות בעלי תפקיד כפול. חוזה P1 יתמוך ב־JSON Schema 2020-12 ואימות סמנטי אחרי parsing. **כל additionalProperties=false**, אלא אם נפתחה גרסת schema חדשה. שדות id, hash, ref, status אינם ריקים; arrays של ids ממוינות וייחודיות. כל סטטוס רישוי נגזר ממקור וביקורת מאומתים, לא מדירוג כמותי.

**RelationDefinition** (קטלוג, עצמאי ממפה): definition_id, schema_version, definition_revision, definition_hash, operator, direction, participant_specs (role, allowed rule_ids, required_atom fields, reading_policy), predicate_ast, evidence_policy, licensed_effects, prohibited_effects, source_anchors, provenance, relation_review, compatible_snapshot. אין בו chart_id, run_id, evidence_key, r1_node_id, selected_witnesses, טקסט פלט למפה או proof חישובי. מזהה definition נשאר יציב לתכלית מושגית; שינוי סמנטי או מקור מחייב revision חדש ו־hash חדש; מזהה לא ממוחזר ליחס אחר.

**RelationEvaluation** (מופע במפה/ריצה): evaluation_id, definition_id + definition_hash, snapshot_id, chart_fingerprint, run_id, candidate_id, discovery_routes, matched_rule_hits, bindings, alternatives, selected_witnesses, original_composite_match, dependency_proof, time_proof, conflict_proof, search, checks, decision, reasons, trace_digest. לא משכתב הגדרת מקור, אינו מעלה סטטוס ביקורת ואינו יוצר פסקה.

**NarrativeClaim** (פלט מורשה בלבד): claim_id, evaluation_id, licensed_effect_id, derived_predicate, evidence_refs, source_anchor_refs, semantic_delta, novelty_proof, limits, attribution, status, audience, realization_plan. חייב להישען על evaluation עם decision=RELATION_LICENSED; טענת השוואה אינה NarrativeClaim מסוג relation אלא ComparisonPlan נפרד. claim_id לא זהה ל־relation_id או evaluation_id.

**זהויות וחתימות:** canonical JSON עם מפתחות ממוינים, NFC לערכי טקסט, UTF-8, בלי floating point לא תקין; SHA-256 של bytes קנוניים. definition_id = מזהה קטלוג יציב מפוקח (למשל n3.rel.sun-aries-moon-taurus.complement), definition_hash = digest של *כל תוכן* ההגדרה כולל anchors/reviews. snapshot_id = digest של RulePack + N2 catalog + N3 relation catalog + ontology version + matcher/semantic contract versions. chart_fingerprint = digest של עובדות מפה מאומתות + time_mode, ללא שם/מזהה אישי. run_id מזהה הרצה חדש (גם אם אותה מפה) ומגובה ב־execution manifest; evaluation_id = SHA-256(snapshot_id, chart_fingerprint, run_id, definition_hash, ordered_bindings_hash, candidate_id). claim_id = SHA-256(evaluation_id, licensed_effect_id, derived_predicate, source_anchor_refs). אין להשתמש ב־profile_id כתחליף לזהות ריצה.

### 2.1 JSON Schema מחייב לתכנון (N3-contract-1)

זהו חוזה הייצוג המוצע. בדיקות הלוגיקה והעקיבות המפורטות בסעיפים הבאים הן תוספת נדרשת ל־JSON Schema, ולא הנחה שהסכימה לבדה מספיקה.

~~~json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:astro-birth-chart:n3:contracts:1",
  "oneOf": [
    {"$ref": "#/$defs/RelationDefinition"},
    {"$ref": "#/$defs/RelationEvaluation"},
    {"$ref": "#/$defs/NarrativeClaim"}
  ],
  "$defs": {
    "Hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "Id": {"type": "string", "minLength": 1, "maxLength": 256},
    "SourceAnchor": {
      "type": "object", "additionalProperties": false,
      "required": ["anchor_id","source_id","source_origin","title","edition","url",
        "location","excerpt","exact_claim_scope","support_kind","review_status",
        "reviewer_id","reviewed_at","review_revision","supported_effect_ids"],
      "properties": {
        "anchor_id": {"$ref": "#/$defs/Id"},
        "source_id": {"$ref": "#/$defs/Id"},
        "source_origin": {"enum": ["external_primary","external_secondary","internal_editorial"]},
        "title": {"type": "string", "minLength": 1},
        "edition": {"type": "string", "minLength": 1},
        "url": {"type": ["string","null"], "format": "uri"},
        "location": {"type": "string", "minLength": 1},
        "excerpt": {"type": "string"},
        "exact_claim_scope": {"type": "string", "minLength": 1},
        "support_kind": {"enum": ["explicit_attestation","explicit_attestation_candidate",
          "framework_only","editorial_synthesis","hypothesis","contradicting","rejected","none"]},
        "review_status": {"enum": ["unverified","under_review","reviewed","approved",
          "conflicting","rejected"]},
        "reviewer_id": {"type": ["string","null"]},
        "reviewed_at": {"type": ["string","null"], "format": "date-time"},
        "review_revision": {"type": "integer", "minimum": 0},
        "supported_effect_ids": {"type": "array", "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}}
      }
    },
    "ParticipantSpec": {
      "type": "object", "additionalProperties": false,
      "required": ["role","allowed_rule_ids","reading_policy","atom_constraints"],
      "properties": {
        "role": {"$ref": "#/$defs/Id"},
        "allowed_rule_ids": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}},
        "reading_policy": {"enum": ["n2_exact_required","original_atomic_allowed"]},
        "atom_constraints": {"$ref": "#/$defs/Predicate"}
      }
    },
    "Predicate": {
      "type": "object", "additionalProperties": false,
      "required": ["op","operands"],
      "properties": {
        "op": {"enum": ["all","any","not","rule_hit_exact","placement_exact",
          "aspect_exact","house_exact","polarity_exact","time_stable","atom_field_exact",
          "no_blocking_tension"]},
        "operands": {"type": "array", "items": {"oneOf": [
          {"$ref": "#/$defs/Predicate"},
          {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
        ]}}
      }
    },
    "Effect": {
      "type": "object", "additionalProperties": false,
      "required": ["effect_id","predicate","subject_role","object_role",
        "context","scope","boundary","source_anchor_ids"],
      "properties": {
        "effect_id": {"$ref": "#/$defs/Id"},
        "predicate": {"enum": ["qualified_in_context","restricted_by",
          "symbolic_contrast","symbolic_coordination","symbolic_complement"]},
        "subject_role": {"$ref": "#/$defs/Id"},
        "object_role": {"$ref": "#/$defs/Id"},
        "context": {"type": "string", "minLength": 1},
        "scope": {"type": "string", "minLength": 1},
        "boundary": {"type": "string", "minLength": 1},
        "source_anchor_ids": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}}
      }
    },
    "EvidenceBinding": {
      "type": "object", "additionalProperties": false,
      "required": ["role","rule_id","rule_hit_id","evidence_key","fact_keys",
        "dependency_roots","source_refs","rule_review_status","meaning_ref","origin"],
      "properties": {
        "role": {"$ref": "#/$defs/Id"},
        "rule_id": {"$ref": "#/$defs/Id"},
        "rule_hit_id": {"$ref": "#/$defs/Id"},
        "evidence_key": {"$ref": "#/$defs/Id"},
        "fact_keys": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}},
        "dependency_roots": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}},
        "source_refs": {"type": "array", "uniqueItems": true, "items": {"$ref": "#/$defs/Id"}},
        "rule_review_status": {"enum": ["unverified","reviewed","approved","conflicting","rejected"]},
        "meaning_ref": {"type": ["string","null"]},
        "origin": {"enum": ["r1_witness","direct_composite_component"]}
      }
    },
    "Check": {
      "type": "object", "additionalProperties": false,
      "required": ["name","status","reason","evidence_refs"],
      "properties": {
        "name": {"$ref": "#/$defs/Id"},
        "status": {"enum": ["pass","fail","unknown","not_applicable"]},
        "reason": {"type": "string"},
        "evidence_refs": {"type": "array", "uniqueItems": true, "items": {"$ref": "#/$defs/Id"}}
      }
    },
    "RelationDefinition": {
      "type": "object", "additionalProperties": false,
      "required": ["kind","schema_version","definition_id","definition_revision",
        "definition_hash","operator","direction","participant_specs","predicate_ast",
        "evidence_policy","licensed_effects","prohibited_effects","source_anchors",
        "provenance","relation_review","compatible_snapshot"],
      "properties": {
        "kind": {"const": "RelationDefinition"},
        "schema_version": {"const": "N3-contract-1"},
        "definition_id": {"$ref": "#/$defs/Id"},
        "definition_revision": {"type": "integer", "minimum": 1},
        "definition_hash": {"$ref": "#/$defs/Hash"},
        "operator": {"enum": ["qualifies","restricts","contrasts","coordinates","complements"]},
        "direction": {"enum": ["A_to_B","B_to_A","symmetric"]},
        "participant_specs": {"type": "array", "minItems": 2,
          "items": {"$ref": "#/$defs/ParticipantSpec"}},
        "predicate_ast": {"$ref": "#/$defs/Predicate"},
        "evidence_policy": {"type": "object", "additionalProperties": false,
          "required": ["independent_roots_required","time_policy","conflict_policy","proof_complete_required"],
          "properties": {
            "independent_roots_required": {"type": "boolean"},
            "time_policy": {"enum": ["known_only","stable_placements_allowed"]},
            "conflict_policy": {"enum": ["fail_on_material_conflict"]},
            "proof_complete_required": {"const": true}
          }},
        "licensed_effects": {"type": "array", "minItems": 1,
          "items": {"$ref": "#/$defs/Effect"}},
        "prohibited_effects": {"type": "array", "uniqueItems": true, "items": {"type": "string"}},
        "source_anchors": {"type": "array", "minItems": 1,
          "items": {"$ref": "#/$defs/SourceAnchor"}},
        "provenance": {"enum": ["human_curated","rule_text_bounded","experimental"]},
        "relation_review": {"type": "object", "additionalProperties": false,
          "required": ["status","reviewer_id","reviewed_at","review_revision"],
          "properties": {
            "status": {"enum": ["unverified","under_review","reviewed",
              "approved_for_symbolic_wording","conflicting","rejected"]},
            "reviewer_id": {"type": ["string","null"]},
            "reviewed_at": {"type": ["string","null"], "format": "date-time"},
            "review_revision": {"type": "integer", "minimum": 0}
          }},
        "compatible_snapshot": {"$ref": "#/$defs/Hash"}
      }
    },
    "RelationEvaluation": {
      "type": "object", "additionalProperties": false,
      "required": ["kind","schema_version","evaluation_id","definition_id",
        "definition_hash","snapshot_id","chart_fingerprint","run_id","candidate_id",
        "discovery_routes","matched_rule_hits","bindings","alternatives",
        "selected_witnesses","original_composite_match","dependency_proof",
        "time_proof","conflict_proof","search","checks","decision","reasons",
        "trace_digest"],
      "properties": {
        "kind": {"const": "RelationEvaluation"},
        "schema_version": {"const": "N3-contract-1"},
        "evaluation_id": {"$ref": "#/$defs/Hash"},
        "definition_id": {"$ref": "#/$defs/Id"},
        "definition_hash": {"$ref": "#/$defs/Hash"},
        "snapshot_id": {"$ref": "#/$defs/Hash"},
        "chart_fingerprint": {"$ref": "#/$defs/Hash"},
        "run_id": {"$ref": "#/$defs/Id"},
        "candidate_id": {"$ref": "#/$defs/Hash"},
        "discovery_routes": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"enum": ["r1_path","original_composite","direct_definition"]}},
        "matched_rule_hits": {"type": "array", "uniqueItems": true, "items": {"$ref": "#/$defs/Id"}},
        "bindings": {"type": "array", "items": {"$ref": "#/$defs/EvidenceBinding"}},
        "alternatives": {"type": "array", "items": {"$ref": "#/$defs/EvidenceBinding"}},
        "selected_witnesses": {"type": "array", "items": {"$ref": "#/$defs/EvidenceBinding"}},
        "original_composite_match": {"type": ["object","null"]},
        "dependency_proof": {"$ref": "#/$defs/Check"},
        "time_proof": {"$ref": "#/$defs/Check"},
        "conflict_proof": {"$ref": "#/$defs/Check"},
        "search": {"type": "object", "additionalProperties": false,
          "required": ["complete","visited","cap","truncated_reason","proof_digest"],
          "properties": {
            "complete": {"type": "boolean"},
            "visited": {"type": "integer", "minimum": 0},
            "cap": {"type": "integer", "minimum": 1},
            "truncated_reason": {"type": ["string","null"]},
            "proof_digest": {"$ref": "#/$defs/Hash"}
          }},
        "checks": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/Check"}},
        "decision": {"enum": ["RELATION_LICENSED","COMPARISON_ONLY","ABSTAIN",
          "NOT_APPLICABLE","QUARANTINE","INDETERMINATE","INVALID_INPUT"]},
        "reasons": {"type": "array", "uniqueItems": true, "items": {"type": "string"}},
        "trace_digest": {"$ref": "#/$defs/Hash"}
      }
    },
    "NarrativeClaim": {
      "type": "object", "additionalProperties": false,
      "required": ["kind","schema_version","claim_id","evaluation_id",
        "licensed_effect_id","derived_predicate","evidence_refs","source_anchor_refs",
        "semantic_delta","novelty_proof","limits","attribution","status","audience",
        "realization_plan"],
      "properties": {
        "kind": {"const": "NarrativeClaim"},
        "schema_version": {"const": "N3-contract-1"},
        "claim_id": {"$ref": "#/$defs/Hash"},
        "evaluation_id": {"$ref": "#/$defs/Hash"},
        "licensed_effect_id": {"$ref": "#/$defs/Id"},
        "derived_predicate": {"$ref": "#/$defs/Effect"},
        "evidence_refs": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}},
        "source_anchor_refs": {"type": "array", "minItems": 1, "uniqueItems": true,
          "items": {"$ref": "#/$defs/Id"}},
        "semantic_delta": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/Effect"}},
        "novelty_proof": {"$ref": "#/$defs/Check"},
        "limits": {"type": "array", "items": {"type": "string"}},
        "attribution": {"type": "string", "minLength": 1},
        "status": {"enum": ["licensed_symbolic","shadow_only"]},
        "audience": {"enum": ["shadow","reviewer","user"]},
        "realization_plan": {"type": "array", "items": {"enum": ["premise_A",
          "premise_B","documented_relation","scope","qualification","counterfactual"]}}
      }
    }
  }
}
~~~

**Cross-object validators מחייבים (fail closed):** (1) כל referenced id/hash קיים ב־snapshot חתום; (2) definition_hash אינו כולל את שדה עצמו ומחושב מ־canonical payload, ולא ניתן לשנותו בלי revision; (3) relation_review, מקור, תמיכת effect, reviewer וה־scope תואמים; (4) source_anchor מסוג none/framework_only אינו יכול לתמוך ב־licensed_effect; (5) לכל role נבחרה ראיה שלמה ואותה ראיה משתקפת ב־matched hits, alternative sets, lineage ו־comparison; (6) original_composite_match מאומת מול when.all ולא רק מול RuleHit; (7) check unknown או search.complete=false אינם שקולים ל־fail הוכח; (8) audience=user אסור לפני P4, הגדרת approved_for_symbolic_wording וגם החלטת מוצר; (9) claimed effect שווה ל־effect מותר לאחר binding, בלי מילים פרשניות חדשות; (10) הצהרת review ללא reviewer_id/time/revision תקינים נפסלת; (11) array של participants: roles ייחודיים, A/B מוגדרים, לכל effect roles קיימים; (12) type object ב־original_composite_match חייב לכלול composite_rule_id, exact_when_hash, component_rule_hit_ids, component_fact_keys, status ו־composite_is_independent_evidence=false, אחרת null. ביצועי P1 יהיו אחראים להחלפת object הגנרי הזה ב־$defs קשיח לפי חוזה זה.

## 3. שפת טענות, אופרטורים ובדיקת תוספת סמנטית — ARCH-04

**קלט:** (א) טענות אטומיות N2 קיימות ומזהי meaning_id או, עבור Route B בלבד, נוסח הכללים המקוריים כ־original_atomic ללא המצאת reading; (ב) עובדות RuleHits + fact keys ומעמד המקור לכל rule; (ג) RelationDefinition עם predicates, licensed_effects ומקור; (ד) evaluation של המפה, הוכחת התאמה, זמן ושורשים. **פלט:** אפקט טיפוסי, הוכחת מקור, delta מול איחוד הטענות, ניסוח סמלי מוגבל או הימנעות. הערכת מקור אינה תצפית שמימית.

**ייצוג אטום:** SemanticAtom = (subject/role, context, focus, scope, polarity, boundary, rule_id, meaning_id-or-original-text-ref, rule_review_status). לא מפיקים predicates אוטומטית על ידי NLP חופשי: מיפוי N2 לשפה זו מחייב מיפוי ידני מבוקר ו־versioned mapping; חוסר מיפוי = MISSING_MEANING או ORIGINAL_ATOMIC_ONLY. השפה אינה מסוגלת לטעון התרחשות ביוגרפית, קביעה קלינית, סיבתיות או ודאות.

**סמנטיקה טיפוסית של אופרטורים — לא תבניות צמדים:**

| operator | תנאים מחייבים | אפקט יחסי יחיד שמותר ליצור | מה אסור להסיק |
| --- | --- | --- | --- |
| qualifies(A,B) | מקור מאשר שב־context מסוים A מסייג את B; direction/scope מוצהרים | qualified_in_context(B,A,scope) | תכונה כללית חדשה, סיבתיות |
| restricts(A,B) | מקור מגדיר גבול מדויק, polarity ו־boundary | restricted_by(B,A,scope) | תדירות/חומרת התנהגות |
| contrasts(A,B) | מקור מזהה *ניגוד בין הסמלים הספציפיים* והקשר משותף | symbolic_contrast(A,B,context) | קונפליקט בחיי אדם |
| coordinates(A,B) | מקור דורש מפורשות תיאום בין תפקודים; התנאים המלאים מתקיימים | symbolic_coordination(A,B,context) | תיאום מוצלח בפועל |
| complements(A,B) | מקור מציין שמרכיב מסוים משלים חוסר ברכיב האחר | symbolic_complement(A,B,source-bounded-scope) | מהו החוסר הספציפי אם לא פורש במקור; הצלחה |

אין אופרטור causal_effect או temporal_order פעיל. איחוד של 3+ רכיבים אפשרי אם RelationDefinition עצמה מכילה תנאי מורשה רב־משתתפים, או אם תוצאת אפקט קודם מורשית במפורש כקלט עם source anchor נפרד; **אין לבצע שרשור אוטומטי** של שתי טענות כאילו הוכח הקשר שלישוני.

**מתמטיקה של רישוי:** יהי A אוסף ה־SemanticAtoms המתאימים למפה; D היא Definition; B היא binding מוכחת. הפונקציה apply(D,B,A) מותרת רק כאשר:
1. כל predicates על facts, polarity, time, independent roots, meaning fields וסייגי מקור מתקיימים, ו־search.complete=true.
2. יש עוגן מקור חיצוני פרטני שעבר ביקורת, המאשר *אותו* effect, direction, conditions, scope; סטטוס ההגדרה approved_for_symbolic_wording.
3. output_effect הוא איחוד של instantiation מדויק של licensed_effects בלבד; אין חיבור שדות טקסט חופשי למסקנה.
4. ההבדל Delta = closure(A + output_effect) minus closure(A) כולל predicate בינרית יחסית חדשה שלא הייתה באטומים, ב־N2 ComparisonPlan או ב־R1 authored path כהצהרה מאושרת. closure הוא **רק** substitution של מזהי roles, זהות קנונית, שוויון וקשרי scope שהוגדרו במפורש ב־definition; אין ידע עולם, אנלוגיות, או הכללה חופשית.
5. source entailment: לכל effect תואמים עוגן+טווח+excerpt מפורש; ההסקה נשמרת בגבולות המשפט המקורי מבחינת mode (symbolic), subject, direction, scope, modal strength ו־exceptions. כל שינוי משמעותי דורש ביקורת ולא ניתן להסיקו מסמיכות מילים.

**מבחן novelty תפעולי:** אפקט עם אותו tuple של predicate/roles/context/scope שכבר נמצא ב־closure(A) הוא PARAPHRASE_ONLY. אפקט חדש תחבירית אך בלתי מורשה הוא UNLICENSED_DELTA. אפקט מורשה שאינו ב־closure(A) הוא LICENSED_DELTA_CANDIDATE; מסמך ביקורת אנושי משלים בודק שהרכיב החדש ניכר בתוכן ולא רק באורך. המדד העיקרי = מספר distinct licensed relation predicates חדשים / מספר candidate relations תקינים; מדדים נלווים: recall על gold, false-positive על negatives, contradiction rate, counterfactual locality, provenance completeness, blinded human semantic improvement מול N2. אורך טקסט, BLEU וספירת שמות צירים אינם מדדי עומק.

**Realizer עתידי ללא LLM וטבלת צמדים:** לוקח semantic effects + roles + attribution + boundary ויוצר מבנה שיח כללי (רכיבים→יחס מתועד→היקף→סייג), עם כלי תחביר עברי דטרמיניסטי. כל מילה טוענתית חייבת להיות מוסברת על ידי predicate/anchor; תחביר אינו מוסיף premises. כשל בביקורת הפלט חוזר ל־COMPARISON_ONLY. אין טבלת משפטים ייעודית לכל צירוף.

## 4. התאמת ראיות והוכחה — ARCH-05

**החוזה:** CandidateGeneration → ExactMatch → SourceLicenseGate → RelationSpecificProof → NoveltyGate → Claim. שמור את כל הראיות המקוריות ואת ה־RuleHit IDs; לעולם אין לבחור hits[0] באופן שקט.

1. **ExactMatch:** match טיפוסי של when.body+sign; composite.when.all (כל clauses); when.pair+kind עם recheck של orb וזוויות מול המיקומים; when.house עם time_mode וה־ascendant; polarity וזיהוי evidence_group. אין matching על פי axis בלבד. השווה chart provenance, rule text hash ו־source_detail.scope ל־manifest. כלל שמחושב כ־modifier הוא edge editorial בלבד, ולא root חדש.
2. **Alternative bindings:** לכל role צרף כל witness_group ואת כל ה־rule_hit members תחת evidence_key, עם rules/text/status/source_url/polarity. חיפוש דטרמיניסטי על כל חלופות הראיה המורשות; סדר canonical לפי (rule_id, evidence_key, fact_key) לא לפי ציונים. ב־Route A selected_witnesses_by_axis אינו מוחלף אלא אם נפתח relation-specific search נפרד עם trace; ב־Route B בחר את שני component facts של composite ישירות. שמור גם rejected alternatives והסיבה.
3. **Independence:** roots במודל R1 מתפשטים מ־placement→body, aspect→שני bodies, house→body+angle, composite→union of component roots. אל תספור composite בנפרד. כאשר האפקט מחייב *שתי ראיות בלתי תלויות* יש לדרוש disjoint roots בין roles ולהציג proof. כאשר המקור מתאר *מפורשות צירוף שתי תצפיות של אותם שורשים* (למשל אותו גוף ב־placement/aspect), כפילות השורשים אינה מניעה בהכרח source-attributed exact composite — אבל אסור להציג זאת כשתי עדויות עצמאיות או לטעון לחיזוק סטטיסטי. הגדרה מפורשת evidence_policy קובעת זאת, ולא ויתור רנדומלי.
4. **Time certainty:** known / estimated / unknown. היעדר שעת לידה חוסם aspect/house כשחוזה interpretation._match חוסם; placement מותר רק אם sign יציב בכל הדגימות כאשר approximate, או רחוק מסף 1° לפי כלל estimated במימוש הבסיס. אין להסתמך על מעלה מדויקת או שעה שנוח להניח. time_proof מתעד ranges, sample hash, כל עילת אי־ודאות.
5. **Conflict:** בדוק tension בין evidence polarities במפה, contradiction בין source anchors, שינוי סטטוס מקור, וכן alternative explanations. השאר ראיות משני הצדדים. אין להכריע לפי משקל עריכתי/ספירת מופעים. מקור conflicting או rejected חוסם את היחס התלוי בו, גם אם אחד האטומים עדיין מוצג.
6. **Resource guard:** MAX_PROOF_STATES=20000 ו־MAX_NODES=192 הם caps של R1, לא הוכחות שליליות. לכל proof יש complete:boolean *חובה* (אין default=true), visited/cap/truncated_reason; relation-specific bounded search מחזיר INDETERMINATE + INCOMPLETE_SEARCH אם לא הסתיים. Negative result חוקי רק אחרי exhaustive search בתחום המוגדר. מי שאינו יודע אם חיפוש הושלם אינו טוען no_relation.

**טבלת מקרי קצה:**

| מצב | תגובה | נשמר ב־trace |
| --- | --- | --- |
| חלופות רבות לציר | חיפוש מלא/תחום מוגדר, ללא קידום הראשון | כל קבוצות החלופות, sorting, chosen, failed |
| roots משותפים | חסימת אי־תלות אם נדרשת; composite direct יכול להישאר exact-match, ללא כפל עדות | union roots, policy, overlap |
| composite modifier_only | exact match עצמאי מ־R1; אין משקל נוסף | rule_id, when.all, related_rule_ids, two original facts |
| שעה לא ודאית | מאמת sign stability; חוסם מסקנות על house/aspect | time_mode, samples, edge margins |
| סתירת ראיות/מקורות | אין להכריע ביחס בעייתי; האטומים נשמרים | conflicting IDs, statuses, provenance |
| cap או search truncated | INDETERMINATE, לא NOT_APPLICABLE | complete=false, cap, visited, reason |
| חסר N2 rule_reading ב־Route B | מותר להשתמש *רק* בטקסט אטומי המקורי בהגדרה שמאשרת original_atomic_allowed; אין לייצר meaning_id מדומה | null meaning_ref, reading policy |
| כלל מקור קיים אך אין יחס מתועד | COMPARISON_ONLY או ABSTAIN, לא NarrativeClaim | candidate, no_relation_source |

## 5. רישוי והכרעת מקורות — ARCH-03

**SourceAnchor** איננו RuleHit. מקור פרשני מחייב source_id, מהדורה, כתובת/עותק, עמוד/סעיף/טווח, excerpt רלוונטי ומוגבל, שפת הטקסט, תאריך גישה (ב־audit manifest), exact_claim_scope, support_kind, supported_effect_ids, תנאים, reviewer_id, reviewed_at, review_revision ו־hash. review_status של כלל מקור ושל כל anchor ושל RelationDefinition הן שלוש עובדות שונות. מעמד authored rule אינו אישור של קשר.

**מטריצת הרישוי:**

| סוג ראיה ליחס | מה מוכח | האם מתיר Claim משתמש? |
| --- | --- | --- |
| external explicit_attestation + excerpt exact + reviewed and approved relation | מקור מסוים מתאר יחס מסוים בגבולות מסוימים | רק לאחר כל gates ואישור מוצר ב־P4 |
| explicit_attestation_candidate או unverified | אותר טקסט פרטני, אך ביקורת היחס לא הושלמה | לא; research/shadow בלבד |
| framework_only | רק רקע על גוף/מיקום כללי; scope אינו מכסה צירוף | לא |
| editorial_synthesis | ניסוח פנימי של 96 הכללים, כולל composite | לא, גם כשה־RuleHit matched |
| hypothesis / R2 | תדירות/דפוס במחקר; אין מקור תוכן | לא |
| conflicting / rejected / none | העדר רישיון או סתירה מהותית | לא, עם reason ו־audit |

**תהליך ביקורת מקור אנושי:** איתור primary edition ותעתיק, אימות page/section + צילום מקור אם אפשר, זיהוי טענה יחסית מפורשת, קידוד tuple (roles, direction, predicate, scope, modal), רישום exclusions ו־wording ceiling, בדיקת מקור נוסף/סתירות, החלטת בודק שונה מן המחבר, review_revision, timestamp וחתימה. החלטת reviewed אינה approved. שינוי נוסח rule, מהדורה, anchor, source scope, meaning_id או effect מבטל אישור ישן ב־digest cascade; אין מכניזם של grandfathering. excerpt של framework אינו יכול להפוך לאישור implicit.

## 6. ביקורת ארבעת כללי ה־composite — ממצאי P0

הטבלה מציגה את ה־**original RulePack 0.2.0** בדיוק כמסגרת בדיקה; אינה משנה את ה־RulePack. "מקור קיים" הוא source_detail; "נוסח קשר" הוא נוסח עריכתי *מתוך הקוד*, לא ציטוט מן המקור החיצוני.

| rule_id; תנאי when.all; related IDs | נוסח פנימי מקוצר / יחס מוצע | מקור חיצוני קיים ומיקום | scope והיקף תמיכה | סטטוס / החלטה |
| --- | --- | --- | --- | --- |
| **sun-aries-moon-taurus**; שמש=טלה, ירח=שור; sun-sign-1 + moon-sign-2 | שני קצבים "דורשים תיאום" | Astrodienst Astrowiki — Planets, §Astrology; https://www.astro.com/astrowiki/en/Planets | general planetary framework only; placement-specific claim not established. **אין excerpt פרטני תומך ב־coordination** | rule unverified; anchor framework_only; **לא מורשה**. מקור היסטורי חדש נבחן בנפרד למטה |
| **mercury-virgo-saturn-capricorn**; מרקורי=בתולה, שבתאי=גדי; mercury-sign-6 + saturn-sign-10 | אפשרות לשילוב בדיקת פרטים ותכנון | Astrodienst Astrowiki — Mercury, §Interpretation; https://www.astro.com/astrowiki/en/Mercury | general framework; composite/aspect/house synthesis. **אין excerpt פרטני מאמת** | rule unverified; anchor framework_only; **לא מורשה** |
| **venus-libra-mars-libra**; ונוס=מאזניים, מאדים=מאזניים; venus-sign-7 + mars-sign-7 | בחירה אסתטית ופעולה מחושבת סביב איזון | Astrodienst Astrowiki — Venus, §Interpretation; https://www.astro.com/astrowiki/en/Venus | general framework; composite/aspect/house synthesis. **אין excerpt פרטני מאמת** | rule unverified; anchor framework_only; **לא מורשה** |
| **sun-sagittarius-mercury-sagittarius**; שמש=קשת, מרקורי=קשת; sun-sign-9 + mercury-sign-9 | מבט רחב בשני תפקודים | Astrodienst Astrowiki — Planets, §Astrology; https://www.astro.com/astrowiki/en/Planets | general planetary framework only; placement-specific claim not established. **אין excerpt פרטני מאמת** | rule unverified; anchor framework_only; **לא מורשה** |

**מגבלת אימות:** עמודי Astrodienst נעצרו בסביבת המחקר בחלקם במסך בדיקת דפדפן/timeout. לא ניתן לטעון שבוצעה בדיקה מלאה של נוסח העמודים. הטענה שהם framework-only נשענת על source_detail.scope שנשמר ב־RulePack, ולא על ציטוט מדומיין. האימות של 4/4 כאן הוא בדיקת התאמת רשומות הקוד וסוג התמיכה המוצהר, לא אישור חיצוני של תוכנם.

### 6.1 מקור פרטני נוסף שהתגלה — לא מחליף את השדה המקורי

**Candidate N3-SRC-AL-1899-p62**: Alan Leo, *Astrology for All*, מהדורת 1899, Chapter XVIII, "The Sun in Aries and Moon in Taurus", printed page 62. 
- סריקת מהדורה: https://iapsop.com/ssoc/1899__leo___astrology_for_all.pdf ; OCR מציג כותרת ופסקה בעמ' 62. תעתיק נגיש: https://umbrielastrology.com/library/alan-leo-sun-moon-combinations.html# (Chapter XVIII, [p. 62]).
- excerpt צר: **"the Moon in Taurus supplying what the Sun in Aries usually lacks."** טקסט באותו מיקום מתאר צירוף צד מעשי עם דחף שמשי, ומבדיל בין הרכיבים; הוא **אינו** אומר שבכל מפה האדם משיג תיאום מוצלח.
- source_origin=external_primary (עותק סרוק), support_kind=explicit_attestation_candidate, exact_claim_scope=Sun in Aries AND Moon in Taurus, possible operator=complements, direction=Moon component complements Sun component; reviewer_id=null, review_status=under_review, reviewed_at=null, review_revision=0. **אין supported_effect_ids מאושרים.**
- דרוש אימות תמונה/מהדורה בידי בודק בלתי תלוי, קידוד מדויק של משמעות "supplying" לעומת "coordination", בירור exclusions, חתימה על effect סמלי מוגבל והשוואה לכלל המקורי. בשלב זה המקור **אינו מאשר את הנוסח הפנימי "דורשים תיאום"**, אינו מעדכן RulePack וה־RelationDefinition תישאר Shadow. ניסיון לצפות בסריקה בממשק נעצר במגבלת גודל PDF; התאמת הטקסט אומתה ב־OCR ובתעתיק, אך visual primary verification עוד פתוחה.
- זו הוכחה ראשונית שיש טקסט חיצוני **המתייחס מפורשות לשני תנאי המיקום** וליחס ביניהם; לא הוכחה שיש כבר gold מאושר למנוע. אין לדרוש התאמת aspect או orb: הספר מתייחס לזוג signs, לא בהכרח להיבט זוויתי.

## 7. PoC, טענה מותרת/אסורה ומבחני נגד — ARCH-07

**Fixture סינתטי בלבד; אינו מפת אדם אמיתית:** Sun=Aries, Moon=Taurus, חישובי placement מאומתים, שני RuleHits source-bound מסוג placement, composite modifier-only sun-aries-moon-taurus תואם ב־Route B, R1 path אינו קיים. נשמרים original fact_keys placement:שמש:טלה ו־placement:ירח:שור, roots body:שמש ו־body:ירח. מצב זמן known או stable-under-samples. אין לייחס מצב approved ל־source rule, reading או relation.

**רכיבים בנפרד:** sun-sign-1 מתאר יוזמה/פתיחת מהלך; moon-sign-2 מתאר רציפות/יציבות. שתי הקריאות הסמליות אינן קובעות מנגנון משולב, התנהגות, או רמת הצלחה. אלה טקסטים מקוריים/קריאות עריכתיות; אין להפיק משמעות N2 חסרה לכלל composite.

**הבדל יחסי פוטנציאלי לפי Alan Leo:** לא רק "יוזמה וגם רציפות", אלא יחס source-attributed שבו הרכיב הירחי *מתואר במקור כמשלים* היבט חסר ברכיב השמשי. זו תוספת בינרית מסוג symbolic_complement שאינה קיימת כטענה עצמאית באיחוד האטומים. **היא כרגע candidate Shadow בלבד**: אין לומר למשתמש שהיחס מאושר, או להגדיר מה בדיוק "חסר" אם המקור אינו מפרט. אין לייחס לטקסט ההיסטורי אישור לטענה הפנימית "הקצבים דורשים תיאום" בלי ביקורת scope נפרדת.

**מותר כעת:** N2 comparison שקופה, למשל "כלל שמש בטלה מתייחס לפתיחת מהלך, וכלל ירח בשור מתייחס לרציפות; אין כאן בסיס מאושר לקבוע כיצד האחד משנה את האחר". ב־reviewer-only ניתן להראות candidate: "במקור היסטורי מוגדר נמצא תיאור של השלמה סמלית, ממתין לביקורת".  
**אסור כעת:** "הירח מווסת תמיד את היוזמה", "צירוף זה משפר ויסות", "האדם מצליח בגלל איזון", "המקור מוכיח את אישיותו", או משפט relation כלשהו בדוח משתמש.

**Counterfactuals מחייבים:**
- ירח משתנה לשלט תאומים: moon-sign-2 ו־composite match מתבטלים; sun-sign-1 נשמר; relation candidate נעלם. אין "החלפת שם" אוטומטית.
- שמש איננה בטלה אך קיימת ראיה אחרת לציר יוזמה (לדוגמה jupiter-sign-1 מתוך PR #29): גם אם צירי יוזמה+יציבות קיימים, when.all שקרי והצירוף המקורי אינו מופעל.
- שעה לא ידועה עם sign stable: placement יכול להישאר; aspect/house תלויי שעה אינם מסופחים.
- הסרת source anchor/שינוי scope ל־framework_only: אותן ראיות שמימיות ממשיכות להתאים; **רק רישוי הטענה הבינרית מתבטל**.
- שינוי status ל־conflicting/rejected, duplication של body roots, או cap בחיפוש: הפלט הוא BLOCKED/INDETERMINATE עם trace; קריאות האטומים התקינות אינן נמחקות.

**בדיקת היתכנות:** exact-match + counterfactual demonstrable בהגדרת fixture; external explicit textual candidate identified, אך **0 approved positive gold cases**. לכן P1–P3 יישארו Shadow, P4 יחסום כל claim חדש.

## 8. מכונת החלטות, precedence והימנעות — ARCH-08

החלטה היא על **relation evaluation**, לא על כל פסקת N2. לכל candidate מוחזקים כל checks (pass/fail/unknown) וכל reasons, גם כאשר ה־primary_reason נבחר לפי סדר; אין מחיקה של האטומים. Negative relation מותר רק לאחר בדיקת תנאים סופית וחיפוש שהושלם. אין המרה של UNKNOWN ל־FALSE.

**סדר הכרעה דטרמיניסטי:**

| קדימות | condition / reason | decision והשלכה |
| ---: | --- | --- |
| 0 | INVALID_SCHEMA, SNAPSHOT_MISMATCH, PROVENANCE_MISMATCH, BAD_ID | INVALID_INPUT; אין claim, אין שימוש במידע לא חתום |
| 1 | UNCERTAIN_TIME affecting predicate / missing reliable chart fact | INDETERMINATE (UNCERTAIN_TIME); אפשר להשאיר האטומים שאושרו בנפרד |
| 2 | INCOMPLETE_SEARCH, PROOF_UNKNOWN, RESOURCE_CAP | INDETERMINATE; **לא** NOT_APPLICABLE, אין מסקנה שלילית |
| 3 | UNMATCHED_CONDITIONS after exhaustive exact match | NOT_APPLICABLE; אין relation claim, ייתכנו קריאות אטומיות |
| 4 | CONFLICTING_SOURCES, REJECTED_SOURCE, MATERIAL_TENSION | ABSTAIN/QUARANTINE; אין relation claim |
| 5 | DEPENDENT_ROOTS when policy requires independence | ABSTAIN (DEPENDENT_ROOTS); אין claim מחזק או כפל ראיות |
| 6 | MISSING_READING / MISSING_ATOM_MAPPING when n2_exact_required | COMPARISON_ONLY or ABSTAIN (MISSING_READING); original_atomic_allowed אינו reading מומצא |
| 7 | NO_RELATION_SOURCE, FRAMEWORK_ONLY, EDITORIAL_ONLY, UNVERIFIED_RELATION | COMPARISON_ONLY / QUARANTINE; בלי טענה יחסית |
| 8 | UNLICENSED_DELTA, PARAPHRASE_ONLY, SOURCE_SCOPE_EXCEEDED | COMPARISON_ONLY או ABSTAIN (no novelty / no license) |
| 9 | כל התנאים, הראיות, המקור והחידוש עברו | RELATION_LICENSED במישור התכנון; audience=shadow עד gate של P4 |

**סדר תפעולי:** בדיקות רלוונטיות נאספות עד כמה שניתן גם אם primary fail מוקדם; סדר הקדימות קובע מה מוצג בראש, אך reasons[] מציג את כולן. בלוק יחסי אינו מסיר atom/contrast התואם N2. failed proof search שומר why_not_proved; no relation source שומר source candidates, provenance ו־review status; comparison תופק ממסלול N2 הקיים בלבד או מתיאור רכיבים מדויק, לא מאפקט N3 פסול. אפילו RELATION_LICENSED בהקשר Shadow אינו מגדיל audience בעצמו.

~~~json
{
  "decision": "COMPARISON_ONLY",
  "primary_reason": "NO_RELATION_SOURCE",
  "reasons": ["NO_RELATION_SOURCE", "UNVERIFIED_RELATION"],
  "relation_claims": [],
  "retained_atomic_rule_ids": ["sun-sign-1", "moon-sign-2"],
  "trace": {
    "candidate_route": "original_composite",
    "original_composite_rule_id": "sun-aries-moon-taurus",
    "source_candidate": "N3-SRC-AL-1899-p62",
    "source_status": "under_review",
    "proof_search_complete": true
  }
}
~~~

האובייקט לעיל הוא **DecisionPlan** הסברתי מחוץ לשלוש הסכמות העיקריות; הסכימה המלאה ב־P1 תכלול במפורש גם primary_reason, retained_atomic_rule_ids ו־trace במעטפת N3Plan. אין להחדיר שדות אלה לתוך RelationDefinition.

## 9. גרסאות, קליטה מ־PR #29 ואיסור כפילות — ARCH-06

המקור האחד ל־96 הכללים נשאר **src/astrochart/interpretation_rules.json**, schema=1, pack_version=0.2.0, 96 רשומות. N2 catalog אחד הוא **src/astrochart/meaning_catalog_n2.json**, גרסת 0.2.0 בענף בסיס PR #27 ו־0.3.0 ב־PR #29, עם 86/96 extensions. RelationDefinition catalog עתידי יהיה קובץ **נפרד של *יחסים***, ללא שכפול rule records/reading records. יחסי N3 מחזיקים reference ל־rule_id ו־meaning_id, לא עותקים שניתנים לעריכה.

**Contract manifest:** fields required: rulepack_schema_version, rulepack_version, original_rule_ids_hash, original_rule_texts_when_source_scope_hash, n2_catalog_schema_version, n2_catalog_version, n2_catalog_digest, meaning_id_rule_id_text_scope_digest, n2_semantic_version, r1_ontology_version, relation_catalog_schema_version, relation_catalog_digest, validator_version, source_review_registry_digest. כל digest canonical JSON לפי סעיף 2; גם presence/counted rules 96/86/4 הוא validation, לא תחליף ל־digest. שינוי status/source scope/review מאפס תוצאת רישוי שתלויה בו.

**הליך:** N3 design ב־PR #30 **אינו** מעתיק ידנית את 60 ההרחבות מ־PR #29 ואינו משכתב/עוקף קובץ N2. ב־P1 יוכנס adapter קריאה בלבד לסנאפשוט **אחד**, רק אחרי ש־PR #29 נקלט באופן תקין לענף האינטגרציה בהרשאה נפרדת, או באמצעות fixture חתום מחוץ ל־production בענף ניסוי. 86/96 הם יעד תאימות, לא מצב קיים בתוך PR #30. אימות אטומי על startup: references, rule_id→exact text+when+scope, reading_id→rule_id, catalogue digest, ontology digest; כל mismatch דוחה את snapshot כולו, בלי fallback שקט ל־26 או "מיזוג" 26+60 בזיכרון. ארבעת composite נשארים ללא rule_reading; השימוש ב־original_atomic_allowed מבוקר כמתואר.

**מדיניות תלות:** עד קליטת PR #29 ניתן לתכנן ולבדוק 26/96 עם manifest מדויק, ובנפרד לבדוק fixture של 86/96 במחקר. אין לשנות PR #29 במשימה זו; אין לשנות R1, N1, N2, R2 או 96 כללי המקור.

## 10. תוכנית עתידית P0–P4: כניסה, תוצר, בדיקות וקבלה

| שלב | תנאי כניסה | תוצר מבוקש לאחר אישור עתידי | בדיקות ושער קבלה עצמאי |
| --- | --- | --- | --- |
| **P0 — Knowledge/source audit** | מפרט N3 מתוקן, 96 original rules בלתי משתנים, הרשאת מחקר בלבד | registry ל־4 composite עם when/all, exact excerpt/scope/status, source candidate Alan Leo, contradictions, reviewer checklist | 4/4 מתועדים; אין framework-only כ־approved; מקור היסטורי נבדק מן הסריקה בידי בודק; feasibility status מדויק: 0 approved gold עד אישור |
| **P1 — Contracts/validators** | חתימת מפרט בביקורת עצמאית ואישור מוצר לתשתית ניסויית; manifest מאומת | JSON Schemas ניתנות להרצה, immutable relation definitions, evaluation/claims, review registry, version adapter | fail-closed לכל required/hash/status/source/meaning mismatch; 3 identities נפרדים; round trip deterministic; 86/96 נקלטים רק מסנאפשוט חתום |
| **P2 — Matcher (Shadow)** | P1 עבר, RuleHits+R1+N2 fixtures חתומים; סיווג מקורות לפחות preliminary | dual candidate routes, relation-specific proof, exact-match, audit+counterfactual harness | 4/4 composites מזוהים גם בלי R1; 3+ participants; all alternatives, roots/time/conflict/caps; 100% trace; אפס claims לא מורשים |
| **P3 — Semantic composition (Shadow)** | P2 עבר; לפחות synthetic gold with explicitly licensed fixture; תוכנית השוואה ל־N2 | typed operators+closure/entailment+novelty+realizer דטרמיניסטי + N3Plan | paired N2/N3, ablations, negative controls, blinded review; semantic delta > 0 רק כאשר license קיים; ללא source approved — synthetic tests בלבד, **0 user claims** |
| **P4 — Read-only integration** | P0–P3 עברו; לפחות gold positive *אמיתי ומאושר*; ביקורת תוכן והנדסה; אישור בעל מוצר נפרד | feature flag כבוי כברירת מחדל, UI/export distinct N3 claims, provenance + limitations | Linux/Windows E2E, GUI/EXE/PDF/PNG/no regression; golden counterfactuals; source revocation tests; R2 quarantined; אין Release/merge בלי הרשאה |

**מדיניות מעבר:** גם אם P1–P3 הצליחו על דוגמאות סינתטיות בלבד, הן נשארות Shadow ואינן מאשרות P4. פרסום relation claim מחייב case חיובי אמיתי מאושר ב־P0, כיסוי של מקור/תנאים בתוכן claim, וקבלת בעל מוצר. אין חובה להריץ GUI/EXE ב־P0; שלבי אינטגרציה מחייבים זאת.

## 11. בדיקות מפרט מחייבות ו־acceptance matrix

- **T-01…T-04:** לכל composite exact when.all יוצר Route B candidate ללא R1; status unverified; modifier weight=0; related RuleHits verified.
- **T-05:** במקרה שיש גם R1 path, union אינו סופר עדות שלישית ושומר שני discovery routes.
- **T-06…T-09:** replacement of one sign, alternative axis evidence, aspect same sign without valid orb, house under unknown time ⇒ אין false match.
- **T-10…T-13:** עצמאות roots, composite union of roots, selected/alternative witness audit, 3+ participants relation-specific proof.
- **T-14…T-16:** cap=20000, MAX_NODES=192, missing complete marker ⇒ INDETERMINATE/INVALID ולא negative.
- **T-17…T-20:** rule_status approved but relation source framework_only; external source unverified; conflicting/rejected; revocation ⇒ 0 relational claims.
- **T-21…T-24:** null N2 reading for composite; wrong meaning_id; catalog 0.2 vs 0.3 incompatible; changed source scope while text unchanged ⇒ fail-closed with preserved atoms.
- **T-25…T-29:** all five operators: allowed effect exactly equals bound licensed_effect; scope widening, role reversal, empirical assertion, added causal verb ⇒ blocked.
- **T-30…T-33:** paraphrase/duplicated relation yields zero novel delta; new relation without source yields blocked; paired one-fact perturbation deletes only dependent claim; blinded reviewers can identify why N3 adds bounded information.
- **T-34…T-36:** audit determinism, privacy-safe chart_fingerprint, run/evaluation/claim IDs stable under identical defined inputs; claim revocation on source change.
- **T-37:** no changes to R1/N1/N2/R2/RulePack, no network/LLM runtime, no N3 user output before P4.

**דוגמאות gold:** gold-positive סינתטי עם מקור בדיקה מפורש שמאשר operator/conditions/term boundaries (לא מקור אמיתי), plus negative gold שמחקה exactly framework_only, missing meaning, dependent roots, contradiction, uncertain time, incomplete search. מקרה Alan Leo הוא *historical-source candidate*, לא positive approved gold; יש להשוות את מקורו לצילום העמוד ולרשום verdict עצמאי לפני העלאה.

## 12. חסמים, החלטות בעל מוצר וגבולות ביצוע

**חסמים פתוחים:** (1) החלטת reviewer עצמאית לגבי פרק XVIII עמ' 62, ושאלת מה בדיוק מתיר מקור ההשלמה; (2) ביקורת מקורות חיצוניים נוספת ליתר 3 composite; (3) מיפוי semantic atoms ל־86 קריאות N2 בביקורת; (4) final schema P1 ל־original_composite_match ול־N3Plan validation וגרסאות hash; (5) בניית gold set שאינו מכריח אישור באמצעות ניסוח מחדש; (6) קליטת PR #29 באופן מתואם בלבד לאחר אישור בעל מוצר.

**החלטות בעל מוצר נדרשות לפני מימוש:** אישור ארכיטקטורה אחרי ביקורת בלתי תלויה; האם להקדיש P0 לאימות מקור ספרותי היסטורי ולפי אילו קריטריונים; אישור מסגרת טענות symbolic בלבד; הרשאה לכל חבילת P1–P4 בנפרד והחלטת פרסום מפורשת. ללא מקור פרטני מאושר, היעד הוא **comparison/abstention, not synthetic meaning invention**.

**גבולות מחייבים כעת:** מסמך בלבד. לא מיישמים N3, לא משנים R1/N1/N2/R2, לא מעדכנים 96 כללים, לא משנים PR #29, לא מוסיפים LLM, לא מציגים claims למשתמש, לא ממזגים ל־main ולא מפרסמים Release. אין אישור עצמי: הביקורת העצמאית הבאה חייבת להחליט מחדש.

---
**שורת הכרעה תכנונית:** ארכיטקטורה אופרטיבית יכולה לגזור תוספת סמנטית *רק* מהפעלת יחס טיפוסי שעוגן המקור והראיות נותנים לו רישיון, עם novelty+entailment ו־proof נשמרים. הימנעות מדויקת והצגת האטומים הנפרדים היא תוצאה תקינה, לא כשל של המנוע.
