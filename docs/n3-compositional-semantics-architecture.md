# AstroBirthChart — N3: ארכיטקטורה מתוקנת למשמעות משולבת מבוססת מקור

**סטטוס: DESIGN ONLY · תיקון ARCH-01…ARCH-08 · דורש ביקורת ארכיטקטורה עצמאית חוזרת · אין אישור מימוש.**  
**תאריך:** 2026-11-08. **בסיס PR #30:** 95502df52ded50779359e17865d994c3245c0cb7.  
**תלויות:** PR #27 (HEAD בעת התכנון 7ca47f0ede8c4e0a7aca0ab9ce45944bdfbd4558), PR #29 (HEAD שנבדק 9a8896a4832f2ac78120268510f9de05641f41e3).  
**מקור דרישות:** ביקורת PR #30, תגובה 6718402065. **אופי הפעולה:** החלפה ותיקון של המפרט הקיים, לא פיתוח N3.

## 0. תזה, מצב מוכח והכרעת היתכנות

N3 הוא מנוע **הסקה סמלית מורשית־מקור**: משמעות משולבת מותרת רק כאשר תנאים במפה מתאימים להגדרת יחס, והמקור הפרשני מתיר את *היחס המסוים* ואת גבולות הניסוח. אין ראיה אמפירית לאישיות; רישוי מקור אסטרולוגי איננו רישוי סיבתי/מדעי. קריאת N2 אטומית אינה הופכת לטענת קשר גם אם היא מנוסחת היטב. הופעת R1 path, צמידות מילים, או coactivation ב־R2 אינן מקור ליחס.

**ממצאים מאומתים מקבצי המאגר:** RulePack schema 1, pack_version 0.2.0, כולל 96 כללים: 72 placement, 11 aspect, 9 house, 4 composite. ארבעתם enabled, review_status=unverified, modifier_only בעת ההתאמה, עם weight אפקטיבי 0. R1 אינו קולט modifier_only למועמדים, מוגבל ל־MAX_NODES=192 ו־MAX_PROOF_STATES=20000. N2 catalog ב־PR #27 הוא 0.2.0 עם 26 rule_readings; בענף האח PR #29 ב־HEAD aea7fe31ab2107e70787163965de142b4242b6de הוא 0.3.1 עם 77 rule_readings, 6 symbolic_explanations ו־3 withheld_editorial_readings. אין 86 הרחבות התנהגותיות פעילות; ארבעת כללי ה־composite חסרי rule_reading. יש לנעול מחדש את PR #29 בכל admission עתידי.

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


**Route-scoped completion (מחייב):** אם R1 Route A נקטע או proof_search.complete=false, יש לרשום רק את A כ־INDETERMINATE. Route B מבצע בדיקת original composite independently ולפיכך יכול להיות fully proven; אין "incomplete-search" גלובלי שחוסם Claim שמותר על B, בכפוף לשער source/meaning נפרד. במקרה שהקשר תלוי מפורשות בתנאי A עצמו, חובה להראות זאת ב־Predicate וב־proof, ואז אין להסתפק ב־B.

## 2. חוזי נתונים, מזהים ו־DAG חתימות — B1 / ARCH-02

**נורמטיבי:** N3-contract-2 מחליף את N3-contract-1. שלוש הישויות נשמרות: RelationDefinition (גלובלי), RelationEvaluation (מפה/ריצה), NarrativeClaim (טענה); נוסף N3Plan מאומת להכרעה ו־UpstreamManifest ו־RelationCatalog למניעת mismatch. לכל schema: additionalProperties=false, שדות required, enums, typed arrays ו־cross-validators לפי סעיפים 3–9. ב־JSON Schema נבדק המבנה; דרוש גם validator דטרמיניסטי של האינוואריאנטים בין מסמכים. כל שדה שחסר או unknown ⇒ fail-closed.

### 2.1 סדר חישוב חתימות — גרף מכוון ללא מעגלים

~~~text
RulePack digest + N2 catalog digest and category/policy digests
         + R1 ontology digest + versions of R1/N2/adapter/AST contracts
                                   |
                                   v
                 compatible_upstream_hash
                                   |
      review registry anchors ---> | <--- controlled term registry digest
      [anchor_hash before definition_hash, no snapshot links]
                                   |
                                   v
       canonical RelationDefinition payload minus definition_hash
              (compatible_upstream_hash fixed)
                                   |
                                   v
                 definition_hashes sorted by definition_id
                                   |
                                   v
           RelationCatalog catalog_digest [definition hashes
              + term_registry_hash + source_registry_hash]
                                   |
                                   v
             snapshot_id = SHA256(canonical(
              compatible_upstream_hash, catalog_digest,
              execution_contract_version))
                                   |
              chart_fingerprint + run_id + bindings
                                   v
                 evaluation_id -> claim_id / plan_id
~~~

הגדרות אינן מכילות snapshot_id, relation_catalog_digest או evaluation_id; בפרט השדה הישן \`compatible_snapshot\` **אסור** ונפסל על ידי additionalProperties=false. \`compatible_upstream_hash\` מבוסס רק על קלט שמעל N3: כללים מקוריים, קטלוג N2, קטגוריות ומדיניות התצוגה שלו, אונטולוגיית R1 וגרסאות הממשקים. \`term_registry_hash\` ו־\`anchor_hash\` מחושבים לפני ההגדרה; הם אינם מחזיקים הפניה חוזרת להגדרה/לקטלוג. \`definition_hash = SHA256(canonical(definition minus definition_hash))\`; \`catalog_digest = SHA256(canonical(catalog minus catalog_digest, including ordered definitions and term/source registry digests))\`; \`snapshot_id = SHA256(canonical({compatible_upstream_hash,catalog_digest,execution_contract_version}))\`. הגדר גרסאות/serialization canonical UTF-8 + Unicode NFC, sorted map keys, stable array order כמוגדר לכל שדה; reject אם נדרש sort שלא נעשה או כפילויות. אין hashing של חתימה בתוך עצמה.

**רשומות מרשם תוכן:** `TermRegistry` כולל TermEntry עם term_id, הגדרה קנונית, קבוצת שקילות, aliases וחתימת בודק; רק terms מאושרים רשאים להזין Effect בפלט. `SourceReviewRegistry` כולל SourceAnchor עם anchor_hash וסטטוס עצמאי. `RelationCatalog` מכיל `term_registry_hash` ו־`source_registry_hash` בנוסף להגדרות; שני המרשמים מחושבים לפני ההגדרות ו**אינם מצביעים בחזרה** ל־RelationCatalog. החתימות שלהם מחושבות על canonical registry minus registry_hash, וכל הגדרה חייבת להצביע על אותם anchors ו־term IDs שבתמונת המרשמים. `compatible_upstream_hash` של UpstreamManifest מחושב בלי שדה compatible_upstream_hash עצמו ובלי שום רכיב N3.

**קביעות מזהים:** definition_id יציב למושג, definition_revision משתנה בכל שינוי משמעות, definition_hash מזהה תוכן וביקורת. snapshot_id מזהה סט כולל של תוכן/ממשקים, אך **לא מופיע בשום אובייקט המשמש לחישובו**. chart_fingerprint נגזר מעובדות מפה מאומתות, פרופיל חישוב ו־time_mode, ללא PII; run_id ייחודי להרצה ונרשם ב־manifest גם כאשר אותה מפה מחושבת שוב. evaluation_id = SHA256(canonical({snapshot_id,chart_fingerprint,run_id,definition_hash,ordered_bindings_hash,candidate_id})); claim_id = SHA256(canonical(NarrativeClaim minus claim_id)); plan_id = SHA256(canonical(N3Plan minus plan_id)). identical frozen input => identical digest; run_id שונה => מזהה הערכה שונה.

**תיקון נורמטיבי מחייב — N3-id-derivation-2 (P1, 2026-11-08):** שני המזהים `NarrativeClaim.claim_id` ו־`N3Plan.plan_id` הם **כתובות תוכן מלאות**, לא projection חלקי. אלגוריתם החישוב הוא בדיוק `SHA-256(canonical_bytes(object_without_own_id))`: מתחילים מאובייקט JSON העומד בסכמת N3-contract-2, מסירים **אך ורק** את שדה המזהה העצמי `claim_id` או `plan_id` (אין להשמיט `null` או שדות אחרים), מבצעים Unicode NFC לכל ערכי המחרוזת ולשמות המפתחות, דוחים מפתחות המתנגשים לאחר הנרמול, ממיינים מפתחות של כל מפת JSON בסדר לקסיקוגרפי, משמרים את סדר המערכים הקנוני שהחוזה דורש, משתמשים בקידוד UTF-8 ללא escaping כפוי של Unicode וללא whitespace (`sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False`), ואז מחשבים SHA-256 ומציגים 64 ספרות hex קטנות. ערכי NaN/Infinity אסורים. `evaluation_id` נשאר לפי נגזרתו הנפרדת של N3-contract-2; claim עשוי להצביע על evaluation, ותוכנית עשויה להצביע על claim IDs, אך לא להפך — **אין מחזור תלות**. גרסת המבנה וה־JSON Schema נשארת `N3-contract-2` עם 34 `$defs`; גרסת אלגוריתם גזירת המזהים היא **`N3-id-derivation-2`**. אין להשתמש בנוסחת projection הישנה גם אם נוצר ממנה digest בן 64 תווים.

**תאימות, אחסון ו־replay:** שינוי כל שדה מהותי (including `Plan.trace`, `atomic_evidence_refs`, `relation_claim_state`, `Claim.evidence_refs`, `semantic_delta`, `limits`, `attribution`, `audience`) יוצר מזהה תוכן חדש. `definition_id` נשאר מזהה מושגי יציב נפרד; אין לטעות ולייחס יציבות כזו ל־`claim_id`/`plan_id`. כל שומר, מעבד, export, restore, replay או reference עתידי חייב להכריז על `N3-id-derivation-2`, לאמת מחדש את hash, ולמנוע ערבוב מזהים מגרסאות שונות. אם בעתיד קיימים אובייקטים מגזירה קודמת, יש לייצר migration עם mapping מפורש ישן→חדש, עדכון הפניות ואימות מלא, ללא acceptance שקט. נכון ל־P1 אין אובייקטי N3 בייצור או positive gold, ולכן אין מיגרציה בפועל. תיקון זה נועד לסגור R32-03, אושר הנדסית בביקורת החוזרת של PR #32, והוא מקושר ל־[מימוש ונימוק מפורטים ב־PR #32](https://github.com/toyro396133/astro-birth-chart-windows/pull/32) ול־`docs/n3-p1-r32-remediation.md` בענף PR #32. **ביקורת עצמאית על נספח נורמטיבי זה עדיין נדרשת; אין באישור ההנדסי אישור מיזוג או הפעלה.**

**בדיקות B1:** topological sort לכל ששת השלבים; snapshot→definition edge אסור; byte-for-byte repeat determinism; שינוי שדה יחיד בנוסח N2 / category policy / source anchor / definition חייב לבטל hash downstream; דחייה אטומית של definition.compatible_upstream_hash≠manifest ו־snapshot שנגזר מרכיבים אחרים; "hash" כ־64 תווים אינו מספיק, חובה recomputation והשוואה.

### 2.2 JSON Schema 2020-12 — גרסה נורמטיבית מתוקנת

~~~json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:astro-birth-chart:n3:contracts:2",
  "oneOf": [
    {
      "$ref": "#/$defs/UpstreamManifest"
    },
    {
      "$ref": "#/$defs/RelationDefinition"
    },
    {
      "$ref": "#/$defs/RelationCatalog"
    },
    {
      "$ref": "#/$defs/RelationEvaluation"
    },
    {
      "$ref": "#/$defs/NarrativeClaim"
    },
    {
      "$ref": "#/$defs/N3Plan"
    },
    {
      "$ref": "#/$defs/TermRegistry"
    },
    {
      "$ref": "#/$defs/SourceReviewRegistry"
    }
  ],
  "$defs": {
    "Hash": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$"
    },
    "Id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256
    },
    "TermId": {
      "type": "string",
      "pattern": "^n3\\.(scope|context|boundary|focus|concept)\\.[a-z0-9][a-z0-9.-]*$"
    },
    "SourceLocation": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "chapter",
        "printed_page",
        "section",
        "line_start",
        "line_end",
        "scan_page_index"
      ],
      "properties": {
        "chapter": {
          "type": [
            "string",
            "null"
          ]
        },
        "printed_page": {
          "type": [
            "string",
            "null"
          ]
        },
        "section": {
          "type": [
            "string",
            "null"
          ]
        },
        "line_start": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        },
        "line_end": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        },
        "scan_page_index": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        }
      }
    },
    "Predicate": {
      "oneOf": [
        {
          "$ref": "#/$defs/All"
        },
        {
          "$ref": "#/$defs/Any"
        },
        {
          "$ref": "#/$defs/Not"
        },
        {
          "$ref": "#/$defs/RuleHitExact"
        },
        {
          "$ref": "#/$defs/PlacementExact"
        },
        {
          "$ref": "#/$defs/AspectExact"
        },
        {
          "$ref": "#/$defs/HouseExact"
        },
        {
          "$ref": "#/$defs/PolarityExact"
        },
        {
          "$ref": "#/$defs/TimeStable"
        },
        {
          "$ref": "#/$defs/AtomTermEquals"
        },
        {
          "$ref": "#/$defs/NoBlockingTension"
        }
      ]
    },
    "All": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "args"
      ],
      "properties": {
        "op": {
          "const": "all"
        },
        "args": {
          "type": "array",
          "minItems": 2,
          "items": {
            "$ref": "#/$defs/Predicate"
          }
        }
      }
    },
    "Any": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "args"
      ],
      "properties": {
        "op": {
          "const": "any"
        },
        "args": {
          "type": "array",
          "minItems": 2,
          "items": {
            "$ref": "#/$defs/Predicate"
          }
        }
      }
    },
    "Not": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "arg"
      ],
      "properties": {
        "op": {
          "const": "not"
        },
        "arg": {
          "$ref": "#/$defs/Predicate"
        }
      }
    },
    "RuleHitExact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role",
        "rule_id"
      ],
      "properties": {
        "op": {
          "const": "rule_hit_exact"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "rule_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        }
      }
    },
    "PlacementExact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role",
        "body",
        "sign"
      ],
      "properties": {
        "op": {
          "const": "placement_exact"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "body": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "sign": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        }
      }
    },
    "AspectExact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role",
        "body_a",
        "body_b",
        "aspect_kind"
      ],
      "properties": {
        "op": {
          "const": "aspect_exact"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "body_a": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "body_b": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "aspect_kind": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        }
      }
    },
    "HouseExact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role",
        "body",
        "house"
      ],
      "properties": {
        "op": {
          "const": "house_exact"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "body": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "house": {
          "type": "integer",
          "minimum": 1,
          "maximum": 12
        }
      }
    },
    "PolarityExact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role",
        "value"
      ],
      "properties": {
        "op": {
          "const": "polarity_exact"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "value": {
          "enum": [
            -1,
            1
          ]
        }
      }
    },
    "TimeStable": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role"
      ],
      "properties": {
        "op": {
          "const": "time_stable"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        }
      }
    },
    "AtomTermEquals": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "role",
        "field",
        "term_id"
      ],
      "properties": {
        "op": {
          "const": "atom_term_equals"
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "field": {
          "enum": [
            "focus",
            "context",
            "scope",
            "boundary"
          ]
        },
        "term_id": {
          "$ref": "#/$defs/TermId"
        }
      }
    },
    "NoBlockingTension": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "op",
        "roles"
      ],
      "properties": {
        "op": {
          "const": "no_blocking_tension"
        },
        "roles": {
          "type": "array",
          "minItems": 2,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        }
      }
    },
    "SourceAnchor": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "anchor_id",
        "anchor_hash",
        "source_id",
        "source_origin",
        "source_version",
        "title",
        "edition",
        "url",
        "location",
        "language",
        "accessed_at",
        "excerpt",
        "scope_id",
        "matching_conditions",
        "support_kind",
        "review_status",
        "source_text_verification",
        "visual_verification",
        "reviewer_id",
        "reviewed_at",
        "review_revision",
        "supported_effect_ids"
      ],
      "properties": {
        "anchor_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "anchor_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "source_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "source_origin": {
          "enum": [
            "external_primary",
            "external_secondary",
            "internal_editorial"
          ]
        },
        "source_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "title": {
          "type": "string",
          "minLength": 1
        },
        "edition": {
          "type": "string",
          "minLength": 1
        },
        "url": {
          "type": [
            "string",
            "null"
          ]
        },
        "location": {
          "$ref": "#/$defs/SourceLocation"
        },
        "language": {
          "type": "string",
          "pattern": "^[a-z]{2,3}(-[A-Za-z0-9]+)*$"
        },
        "accessed_at": {
          "type": "string",
          "format": "date-time"
        },
        "excerpt": {
          "type": "string"
        },
        "scope_id": {
          "$ref": "#/$defs/TermId"
        },
        "matching_conditions": {
          "$ref": "#/$defs/Predicate"
        },
        "support_kind": {
          "enum": [
            "explicit_attestation",
            "explicit_attestation_candidate",
            "framework_only",
            "editorial_synthesis",
            "hypothesis",
            "contradicting",
            "rejected",
            "none"
          ]
        },
        "review_status": {
          "enum": [
            "unverified",
            "under_review",
            "reviewed",
            "approved",
            "conflicting",
            "rejected"
          ]
        },
        "source_text_verification": {
          "enum": [
            "not_checked",
            "text_indexed",
            "primary_text_checked"
          ]
        },
        "visual_verification": {
          "enum": [
            "pending",
            "verified",
            "not_applicable"
          ]
        },
        "reviewer_id": {
          "type": [
            "string",
            "null"
          ]
        },
        "reviewed_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time"
        },
        "review_revision": {
          "type": "integer",
          "minimum": 0
        },
        "supported_effect_ids": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        }
      }
    },
    "ParticipantSpec": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "role",
        "allowed_rule_ids",
        "reading_policy",
        "atom_constraints"
      ],
      "properties": {
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "allowed_rule_ids": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "reading_policy": {
          "enum": [
            "n2_exact_required",
            "original_atomic_allowed"
          ]
        },
        "atom_constraints": {
          "$ref": "#/$defs/Predicate"
        }
      }
    },
    "Effect": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "effect_id",
        "predicate",
        "subject_role",
        "object_role",
        "context_id",
        "scope_id",
        "boundary_ids",
        "source_anchor_ids",
        "modal_strength"
      ],
      "properties": {
        "effect_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "predicate": {
          "enum": [
            "qualified_in_context",
            "restricted_by",
            "symbolic_contrast",
            "symbolic_coordination",
            "symbolic_complement"
          ]
        },
        "subject_role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "object_role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "context_id": {
          "$ref": "#/$defs/TermId"
        },
        "scope_id": {
          "$ref": "#/$defs/TermId"
        },
        "boundary_ids": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "$ref": "#/$defs/TermId"
          }
        },
        "source_anchor_ids": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "modal_strength": {
          "const": "source_attributed_symbolic_possible"
        }
      }
    },
    "EvidenceBinding": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "role",
        "rule_id",
        "rule_hit_id",
        "evidence_key",
        "fact_keys",
        "witness_group_id",
        "alternative_set_id",
        "dependency_roots",
        "source_refs",
        "rule_review_status",
        "meaning_ref",
        "content_category",
        "origin"
      ],
      "properties": {
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "rule_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "rule_hit_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "evidence_key": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "fact_keys": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "witness_group_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "alternative_set_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "dependency_roots": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "source_refs": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "rule_review_status": {
          "enum": [
            "unverified",
            "reviewed",
            "approved",
            "conflicting",
            "rejected"
          ]
        },
        "meaning_ref": {
          "type": [
            "string",
            "null"
          ]
        },
        "content_category": {
          "enum": [
            "behavioral_rule_reading",
            "symbolic_explanation",
            "withheld_editorial_reading",
            "original_atomic_only"
          ]
        },
        "origin": {
          "enum": [
            "r1_witness",
            "direct_composite_component"
          ]
        }
      }
    },
    "Check": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "name",
        "status",
        "reason",
        "evidence_refs"
      ],
      "properties": {
        "name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "status": {
          "enum": [
            "pass",
            "fail",
            "unknown",
            "not_applicable"
          ]
        },
        "reason": {
          "type": "string"
        },
        "evidence_refs": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        }
      }
    },
    "CompositeMatch": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "composite_rule_id",
        "exact_when_hash",
        "component_rule_hit_ids",
        "component_fact_keys",
        "component_dependency_roots",
        "related_rule_ids",
        "rule_review_status",
        "composite_is_independent_evidence"
      ],
      "properties": {
        "composite_rule_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "exact_when_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "component_rule_hit_ids": {
          "type": "array",
          "minItems": 2,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "component_fact_keys": {
          "type": "array",
          "minItems": 2,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "component_dependency_roots": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "related_rule_ids": {
          "type": "array",
          "minItems": 2,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "rule_review_status": {
          "enum": [
            "unverified",
            "reviewed",
            "approved",
            "conflicting",
            "rejected"
          ]
        },
        "composite_is_independent_evidence": {
          "const": false
        }
      }
    },
    "RouteProof": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "route",
        "candidate_state",
        "search_state",
        "search_complete",
        "visited",
        "cap",
        "proof_result",
        "selected_binding_ids",
        "alternative_set_ids",
        "source_fact_refs",
        "failure_reasons",
        "trace_hash"
      ],
      "properties": {
        "route": {
          "enum": [
            "r1_path",
            "original_composite"
          ]
        },
        "candidate_state": {
          "enum": [
            "candidate",
            "not_candidate",
            "not_executed"
          ]
        },
        "search_state": {
          "enum": [
            "complete",
            "incomplete",
            "not_applicable"
          ]
        },
        "search_complete": {
          "type": [
            "boolean",
            "null"
          ]
        },
        "visited": {
          "type": "integer",
          "minimum": 0
        },
        "cap": {
          "type": "integer",
          "minimum": 0
        },
        "proof_result": {
          "enum": [
            "proven",
            "unmatched",
            "blocked",
            "unknown",
            "not_candidate"
          ]
        },
        "selected_binding_ids": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "alternative_set_ids": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "source_fact_refs": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "failure_reasons": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "$ref": "#/$defs/ReasonCode"
          }
        },
        "trace_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      }
    },
    "ReasonCode": {
      "enum": [
        "NONE",
        "INVALID_SCHEMA",
        "SNAPSHOT_MISMATCH",
        "PROVENANCE_MISMATCH",
        "BAD_ID",
        "UNCERTAIN_TIME",
        "INCOMPLETE_SEARCH",
        "PROOF_UNKNOWN",
        "RESOURCE_CAP",
        "UNMATCHED_CONDITIONS",
        "CONFLICTING_SOURCES",
        "REJECTED_SOURCE",
        "MATERIAL_TENSION",
        "DEPENDENT_ROOTS",
        "MISSING_READING",
        "MISSING_ATOM_MAPPING",
        "NO_RELATION_SOURCE",
        "FRAMEWORK_ONLY",
        "EDITORIAL_ONLY",
        "UNVERIFIED_RELATION",
        "UNLICENSED_DELTA",
        "PARAPHRASE_ONLY",
        "SOURCE_SCOPE_EXCEEDED",
        "OPERATOR_EFFECT_MISMATCH",
        "CANDIDATE_NOT_FOUND"
      ]
    },
    "ReasonRecord": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "code",
        "route",
        "blocking",
        "evidence_refs"
      ],
      "properties": {
        "code": {
          "$ref": "#/$defs/ReasonCode"
        },
        "route": {
          "enum": [
            "r1_path",
            "original_composite",
            "global"
          ]
        },
        "blocking": {
          "type": "boolean"
        },
        "evidence_refs": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        }
      }
    },
    "RelationDefinition": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "definition_id",
        "definition_revision",
        "definition_hash",
        "compatible_upstream_hash",
        "term_registry_hash",
        "operator",
        "direction",
        "participant_specs",
        "predicate_ast",
        "evidence_policy",
        "licensed_effects",
        "prohibited_effects",
        "source_anchors",
        "provenance",
        "relation_review"
      ],
      "properties": {
        "kind": {
          "const": "RelationDefinition"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "definition_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "definition_revision": {
          "type": "integer",
          "minimum": 1
        },
        "definition_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "compatible_upstream_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "term_registry_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "operator": {
          "enum": [
            "qualifies",
            "restricts",
            "contrasts",
            "coordinates",
            "complements"
          ]
        },
        "direction": {
          "enum": [
            "A_to_B",
            "B_to_A",
            "symmetric"
          ]
        },
        "participant_specs": {
          "type": "array",
          "minItems": 2,
          "items": {
            "$ref": "#/$defs/ParticipantSpec"
          }
        },
        "predicate_ast": {
          "$ref": "#/$defs/Predicate"
        },
        "evidence_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "independent_roots_required",
            "time_policy",
            "conflict_policy",
            "proof_complete_required"
          ],
          "properties": {
            "independent_roots_required": {
              "type": "boolean"
            },
            "time_policy": {
              "enum": [
                "known_only",
                "stable_placements_allowed"
              ]
            },
            "conflict_policy": {
              "const": "fail_on_material_conflict"
            },
            "proof_complete_required": {
              "const": true
            }
          }
        },
        "licensed_effects": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "#/$defs/Effect"
          }
        },
        "prohibited_effects": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1
          }
        },
        "source_anchors": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "#/$defs/SourceAnchor"
          }
        },
        "provenance": {
          "enum": [
            "human_curated",
            "rule_text_bounded",
            "experimental"
          ]
        },
        "relation_review": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "status",
            "reviewer_id",
            "reviewed_at",
            "review_revision"
          ],
          "properties": {
            "status": {
              "enum": [
                "unverified",
                "under_review",
                "reviewed",
                "approved_for_symbolic_wording",
                "conflicting",
                "rejected"
              ]
            },
            "reviewer_id": {
              "type": [
                "string",
                "null"
              ]
            },
            "reviewed_at": {
              "type": [
                "string",
                "null"
              ],
              "format": "date-time"
            },
            "review_revision": {
              "type": "integer",
              "minimum": 0
            }
          }
        }
      }
    },
    "RelationCatalog": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "catalog_version",
        "compatible_upstream_hash",
        "term_registry_hash",
        "source_registry_hash",
        "definitions",
        "catalog_digest"
      ],
      "properties": {
        "kind": {
          "const": "RelationCatalog"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "catalog_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "compatible_upstream_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "term_registry_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "definitions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/RelationDefinition"
          }
        },
        "catalog_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "source_registry_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      }
    },
    "UpstreamManifest": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "rulepack_digest",
        "rulepack_version",
        "rulepack_schema_version",
        "n2_catalog_digest",
        "n2_catalog_version",
        "n2_catalog_schema_version",
        "n2_category_digests",
        "n2_category_policies_digest",
        "ontology_digest",
        "r1_contract_version",
        "n2_contract_version",
        "adapter_contract_version",
        "predicate_contract_version",
        "compatible_upstream_hash"
      ],
      "properties": {
        "kind": {
          "const": "UpstreamManifest"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "rulepack_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "rulepack_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "rulepack_schema_version": {
          "type": "integer",
          "minimum": 1
        },
        "n2_catalog_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "n2_catalog_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "n2_catalog_schema_version": {
          "type": "integer",
          "minimum": 1
        },
        "n2_category_digests": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "rule_readings",
            "symbolic_explanations",
            "withheld_editorial_readings",
            "entries"
          ],
          "properties": {
            "rule_readings": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            "symbolic_explanations": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            "withheld_editorial_readings": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            "entries": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            }
          }
        },
        "n2_category_policies_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "ontology_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "r1_contract_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "n2_contract_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "adapter_contract_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "predicate_contract_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "compatible_upstream_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      }
    },
    "RelationEvaluation": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "evaluation_id",
        "definition_id",
        "definition_hash",
        "snapshot_id",
        "chart_fingerprint",
        "run_id",
        "candidate_id",
        "discovery_routes",
        "matched_rule_hits",
        "bindings",
        "alternatives",
        "selected_witnesses",
        "original_composite_match",
        "dependency_proof",
        "time_proof",
        "conflict_proof",
        "route_proofs",
        "source_license_check",
        "novelty_check",
        "checks",
        "trace_digest"
      ],
      "properties": {
        "kind": {
          "const": "RelationEvaluation"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "evaluation_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "definition_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "definition_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "snapshot_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "chart_fingerprint": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "candidate_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "discovery_routes": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "enum": [
              "r1_path",
              "original_composite"
            ]
          }
        },
        "matched_rule_hits": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "bindings": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/EvidenceBinding"
          }
        },
        "alternatives": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/EvidenceBinding"
          }
        },
        "selected_witnesses": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/EvidenceBinding"
          }
        },
        "original_composite_match": {
          "oneOf": [
            {
              "$ref": "#/$defs/CompositeMatch"
            },
            {
              "type": "null"
            }
          ]
        },
        "dependency_proof": {
          "$ref": "#/$defs/Check"
        },
        "time_proof": {
          "$ref": "#/$defs/Check"
        },
        "conflict_proof": {
          "$ref": "#/$defs/Check"
        },
        "route_proofs": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": {
            "$ref": "#/$defs/RouteProof"
          }
        },
        "source_license_check": {
          "$ref": "#/$defs/Check"
        },
        "novelty_check": {
          "$ref": "#/$defs/Check"
        },
        "checks": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "#/$defs/Check"
          }
        },
        "trace_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      }
    },
    "NarrativeClaim": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "claim_id",
        "evaluation_id",
        "licensed_effect_id",
        "derived_predicate",
        "evidence_refs",
        "source_anchor_refs",
        "semantic_delta",
        "novelty_proof",
        "limits",
        "attribution",
        "status",
        "audience",
        "realization_plan"
      ],
      "properties": {
        "kind": {
          "const": "NarrativeClaim"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "claim_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "evaluation_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "licensed_effect_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "derived_predicate": {
          "$ref": "#/$defs/Effect"
        },
        "evidence_refs": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "source_anchor_refs": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "semantic_delta": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "#/$defs/Effect"
          }
        },
        "novelty_proof": {
          "$ref": "#/$defs/Check"
        },
        "limits": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1
          }
        },
        "attribution": {
          "type": "string",
          "minLength": 1
        },
        "status": {
          "enum": [
            "licensed_symbolic",
            "shadow_only"
          ]
        },
        "audience": {
          "enum": [
            "shadow",
            "reviewer",
            "user"
          ]
        },
        "realization_plan": {
          "type": "array",
          "items": {
            "enum": [
              "premise_A",
              "premise_B",
              "documented_relation",
              "scope",
              "qualification",
              "counterfactual"
            ]
          }
        }
      }
    },
    "N3Plan": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "plan_id",
        "snapshot_id",
        "definition_id",
        "evaluation_id",
        "decision",
        "primary_reason",
        "reasons",
        "retained_atomic_rule_ids",
        "comparison_state",
        "relation_claim_state",
        "relation_claim_ids",
        "route_proofs",
        "trace"
      ],
      "properties": {
        "kind": {
          "const": "N3Plan"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "plan_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "snapshot_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "definition_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "evaluation_id": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "decision": {
          "enum": [
            "RELATION_LICENSED",
            "COMPARISON_ONLY",
            "ABSTAIN",
            "NOT_APPLICABLE",
            "QUARANTINE",
            "INDETERMINATE",
            "INVALID_INPUT"
          ]
        },
        "primary_reason": {
          "$ref": "#/$defs/ReasonCode"
        },
        "reasons": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ReasonRecord"
          }
        },
        "retained_atomic_rule_ids": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "comparison_state": {
          "enum": [
            "available",
            "withheld",
            "unavailable"
          ]
        },
        "relation_claim_state": {
          "enum": [
            "licensed_shadow",
            "blocked",
            "not_applicable",
            "indeterminate"
          ]
        },
        "relation_claim_ids": {
          "type": "array",
          "minItems": 0,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          }
        },
        "route_proofs": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": {
            "$ref": "#/$defs/RouteProof"
          }
        },
        "trace": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "source_snapshot_hash",
            "adapter_trace_hash",
            "evaluation_trace_hash",
            "selected_decisive_route",
            "atomic_evidence_refs"
          ],
          "properties": {
            "source_snapshot_hash": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            "adapter_trace_hash": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            "evaluation_trace_hash": {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            "selected_decisive_route": {
              "enum": [
                "r1_path",
                "original_composite",
                "none"
              ]
            },
            "atomic_evidence_refs": {
              "type": "array",
              "minItems": 0,
              "uniqueItems": true,
              "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256
              }
            }
          }
        }
      }
    },
    "TermEntry": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "term_id",
        "term_kind",
        "canonical_definition",
        "synonym_ids",
        "equivalence_cluster_id",
        "review_status",
        "reviewer_id",
        "reviewed_at",
        "revision"
      ],
      "properties": {
        "term_id": {
          "$ref": "#/$defs/TermId"
        },
        "term_kind": {
          "enum": [
            "scope",
            "context",
            "boundary",
            "focus",
            "concept"
          ]
        },
        "canonical_definition": {
          "type": "string",
          "minLength": 1
        },
        "synonym_ids": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "$ref": "#/$defs/TermId"
          }
        },
        "equivalence_cluster_id": {
          "type": [
            "string",
            "null"
          ]
        },
        "review_status": {
          "enum": [
            "unverified",
            "under_review",
            "approved",
            "rejected"
          ]
        },
        "reviewer_id": {
          "type": [
            "string",
            "null"
          ]
        },
        "reviewed_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time"
        },
        "revision": {
          "type": "integer",
          "minimum": 1
        }
      }
    },
    "TermRegistry": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "registry_version",
        "registry_hash",
        "entries"
      ],
      "properties": {
        "kind": {
          "const": "TermRegistry"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "registry_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "registry_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "entries": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TermEntry"
          }
        }
      }
    },
    "SourceReviewRegistry": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "schema_version",
        "registry_version",
        "registry_hash",
        "anchors"
      ],
      "properties": {
        "kind": {
          "const": "SourceReviewRegistry"
        },
        "schema_version": {
          "const": "N3-contract-2"
        },
        "registry_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "registry_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "anchors": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/SourceAnchor"
          }
        }
      }
    }
  }
}
~~~

**תקפות מעבר ל־JSON Schema (חובה בכל admission):**
1. Validate relation operator ↔ כל licensed_effect לפי מפת סעיף 3; גם SourceAnchor.supported_effect_ids ↔ effect_id וטווח מתאים. אין Effect שבעליו חסר source anchor מאושר.
2. Invariants של זהויות: אין התנגשות ids, אין עריכה שקטה של definition_revision, digest מחושב מחדש (כולל review statuses), references קיימות בתוך snapshot חתום יחיד. שמירת categorical N2 provenance לכל reading.
3. \`participant_specs\` roles ייחודיים; עבור כל role קיים proof חיובי מחייב ב־predicate_ast שאינו תחת not/any ואינו מוגבל ל־axis name. \`not\` מותר רק כ־negative guard, לא כתחליף ל־proof. \`any\` חייב לשמור כל role mandatory בחוץ.
4. Source location line_end≥line_start, language תקינה, accessed_at מתועד, anchor_hash מחושב בלי anchor_hash; review approved מחייב reviewer_id, reviewed_at, visual verification לפי מדיניות source type, source license ו־separate relation approval.
5. \`CompositeMatch\` תואם בדיוק RulePack.when.all ו־related_rule_ids; \`fact_keys\` נגזרים מן המפה, לא מן הכותרת או מהתיאור. \`search_complete\` NULL רק כאשר route not_candidate/not_executed; TRUE/FALSE ב־candidate. כל RouteProof route יופיע פעם אחת (A,B).
6. \`NarrativeClaim\` דורש N3Plan RELATION_LICENSED ו־evaluation.source_license_check=pass, novelty_check=pass, proof complete ב־route decisive, effect מוכח ומאושר, ו־audience=user רק אחרי אישור P4; רשומת \`N3Plan\` חייבת להצביע על Claim IDs קיימים.
7. \`N3Plan.primary_reason\` חייב להתאים למצב evidence *במסלול המכריע*, לא למצב route אחר; mapping decision/relation_claim_state/reasons/retained atoms לפי סעיף 8.
8. \`SourceAnchor\` הוא תיעוד תוכן מחקרי: חתימה/סטטוס מאומתים ב־registry נפרד מאישור RelationDefinition. מחרוזות excerpt אינן הסקת תוכן אוטומטית.

## 3. דקדוק AST והכרעת תוספת משמעות — B3 / ARCH-04

### 3.1 טיפוסים וארגומנטים

\`Predicate\` הוא typed discriminated union ב־N3-contract-2, ללא \`operands\` שרירותיים. דקדוק הבסיס:

~~~text
P ::= all([P,P,...])        # >=2, Kleene 3-valued conjunction
    | any([P,P,...])        # >=2, Kleene 3-valued disjunction
    | not(P)                # 1, רק guard של היעדר/שלילה ממוקדת
    | rule_hit_exact(role:Id, rule_id:Id)
    | placement_exact(role:Id, body:Id, sign:Id)
    | aspect_exact(role:Id, body_a:Id, body_b:Id, aspect_kind:Id)
    | house_exact(role:Id, body:Id, house:1..12)
    | polarity_exact(role:Id, value:-1|1)
    | time_stable(role:Id)
    | atom_term_equals(role:Id, field:focus|context|scope|boundary, term_id:TermId)
    | no_blocking_tension(roles:unique[Id] of length >=2)
~~~

**סמנטיקה:** תוצאת כל leaf היא TRUE/FALSE/UNKNOWN, עם trace ל־RuleHit/observed fact. \`all\` מחזיר FALSE אם אחד FALSE; TRUE אם כולם TRUE; אחרת UNKNOWN. \`any\` TRUE אם יש TRUE; FALSE רק אם כולם FALSE *וכל חיפושי הראיות הרלוונטיים מלאים*; אחרת UNKNOWN. \`not(TRUE)=FALSE\`, \`not(FALSE)=TRUE\` רק אחרי complete search לגבי עובדת השלילה; \`not(UNKNOWN)=UNKNOWN\`. חוסר נתון אינו הכחשה. אין closed-world assumption ביחס לשעת לידה/ראיה חסרה/חיפוש חלקי.

**כל־המשתתפים:** השורש של predicate_ast חייב להיות \`all\`, ויש בו עבור *כל* participant role לפחות \`rule_hit_exact\` תואם ואימות placement/aspect/house רלוונטי בענף חיובי שאינו מוקף ב־any/not; \`any\` רשאי לבחור *חלופות לאותו role* בלבד אחרי שמוכח קיומו, ואין לו רשות להחליף/להשמיט role נדרש. \`not\` רשאי רק לשלול forbidden fact מוגדר או tension כאשר בוצעה סריקה שלמה; טענת \`not(rule_hit_exact)\` אינה מקור רישוי חיובי. שינוי AST מחייב revision + hash, ו־P1 validator נדרש לבצע structural AST well-typedness + role coverage + depth/node caps + 3-valued evaluation.

**סוגי leaf:** \`rule_hit_exact\` נקשר ל־ID מדויק בתוך RulePack; placement/aspect/house נקשרים לעובדות מחושבות ו־when של כלל (לא לשמות צירים בלבד); \`aspect_exact\` כולל pair canonical ו־orb verified דרך matcher קיים; \`time_stable\` אמת רק אם כל דגימות הזמן משמרות את העובדה הנתמכת; \`atom_term_equals\` מקבל TermId מתוך vocab חתום ומיפוי מבוקר; \`no_blocking_tension\` דורש בדיקת סתירות מלאה עבור roles.

### 3.2 מפת operator → Effect (אימות קשיח)

| RelationDefinition.operator | Effect.predicate היחיד המותר | כיוון ומגבלות |
| --- | --- | --- |
| qualifies | qualified_in_context | Subject=A מסייג Object=B; context/scope מדויקים במקור |
| restricts | restricted_by | Subject=A מצמצם Object=B, boundary_ids מתועדים |
| contrasts | symbolic_contrast | A/B בתנאי מקור מפורש; אין הסקת קונפליקט אישי |
| coordinates | symbolic_coordination | A/B מתוארים בתיאום סמלי מפורש בלבד; אין תוצאה בפועל |
| complements | symbolic_complement | A משלים B בגבולות המקור, א־סימטרי אם כך נכתב |

אימות מחייב \`Effect.subject_role/object_role\` מתוך participant_specs ובהתאם ל־direction, אין orientation swap בלי מקור נוסף, ואין \`symbolic_complement\` מתוך \`coordinates\` ולהיפך. שני role IDs חייבים להיות שונים; בריבוי משתתפים כל licensed effect מציין בדיוק מי הוכח ואיזו השפעה מותרת; שרשור effects אינו אוטומטי. \`context_id/scope_id/boundary_ids\` נבדקים מול controlled \`TermRegistry\` בגרסה חתומה (namespace n3.context/scope/boundary/focus/concept); IDs שאינם קיימים או שלא עברו semantic review אסורים. \`modal_strength\` נעול ל־source_attributed_symbolic_possible; אין clinical/causal/empirical operator.

### 3.3 Novelty / entailment שאינו רק JSON difference

Baseline הכרחי \`B\` = (1) כל האטומים/מיפויי meanings של N2 המותרים במפה — עם מקורם, (2) כל נוסחי RulePack האקטיביים, (3) כל טענות original composite או N1 modifier שמופיעות כבר בנוסח עריכתי, גם אם מקורם framework-only, (4) comparison/distinctions של N2 ו־R1 authored paths **רק לעניין כפל טקסט**, לא כהוכחות מקור. מיפוי טקסטים למושגי TermRegistry מבוקר־אדם; טקסט original composite שאינו מאומת **נכנס לבסיס החידוש** כדי להימנע מייחוס חידוש מדומה, אך אינו מקור שמכשיר מסקנה.

מנגנון מתוכנן: \`licensed_effect = instantiate(RelationDefinition.licensed_effects, verified_binding)\`; \`closure(B)\` = שקילות מוכרעת של מונחי scope/focus/role/relations ב־TermRegistry + חוקי substitution מוצהרים בלבד. \`Delta = closure(B ∪ licensed_effect) - closure(B)\`. אם tuple relation חדש רק תחבירית וה־source statement כבר קיים ב־composite, התוצאה \`PARAPHRASE_ONLY\`; אם effect חדש אבל לא נתמך בעוגן source → \`UNLICENSED_DELTA\`; אם structured deduction אינה מוכיחה equivalence/entailment/source scope → \`HUMAN_REVIEW_REQUIRED\` (ב־N3Plan: COMPARISON_ONLY/QUARANTINE) ולא "licensed" אוטומטי.

**שער ביקורת אנושי נפרד:** בודק תוכן עצמאי מאשר (א) source excerpt וסעיף, (ב) source→predicate entailment, כיוון, scope, conditional, modality, (ג) שקילות מול baseline טקסטואלי (כולל composite), (ד) novelty רעיוני אמיתי, (ה) עברית ומגבלות. החלטה נשמרת כ־signed review revision בתוך definition/anchor; שינוי vocab, baseline, excerpt או reviewer approval מבטל digest. מדד הצלחה: novel **licensed** relation predicates מול N2/RulePack baseline והבחנה אנושית עיוורת, לא ספירת מילים, JSON שונה או משפטים מורכבים. בלי אישור מקור/יחס: Shadow או Comparison בלבד.

## 4. חוזה EvidenceAdapter קריאה בלבד — B4 / ARCH-05

**אין שינוי ל־interpretation.py, R1 או N2.** \`RuleHit\` קיים כולל \`rule_id,axis,polarity,weight,text,evidence,source,provisional,review_status,evidence_key,source_url,modifier_only\`; הוא **אינו** מכיל \`rule_hit_id\` או \`fact_keys\`. לכן N3-P1 יגדיר \`EvidenceAdapterV1\` חיצוני, read-only, שבודק כל Raw RuleHit מול RulePack ומפת העובדות המחושבת ואינו מוסיף שדות בחזרה למקור. לא מסתמכים על תיאורי Hebrew evidence/עיגולי longitude כדי להמציא facts.

### 4.1 נגזרת עובדות מקוריות

1. קבע snapshot חתום ו־chart_fingerprint ממפת עובדות מחושבת + chart calculation profile + time_mode (בלי PII). קרא \`RulePack[rule_id]\`; דרוש type, when, axis, polarity, exact original text, source_url, review_status, modifier_only, weight policy תואמים ל־Raw RuleHit. mismatch ⇒ PROVENANCE_MISMATCH ולא silent repair.
2. לפי סוג \`rule.when\`, קרא מחדש read-only את אותם תנאים שה־matcher המקורי מפעיל; בעובדה יציבה: \`placement:{body}:{sign}\`; \`aspect:{sorted(body_a,body_b).join(':')}:{aspect_kind}\` עם orb/angles rechecked; \`house:{body}:{house}\` עם time gate; \`composite\`: **רשימת** כל component placement fact keys מתוך \`when.all\`, ולא string מורכב כראיה שלישית. יש לאמת הקבלה ל־legacy \`composite:+\` evidence_key generated (כאשר אין evidence_group override) ולזהות override רק כ־group label, לא fact.
3. \`fact_keys\` הם רשימת facts מקורית ממוינת וייחודית; composite מחייב >=2 components, \`related_rule_ids\` תואמים ל־when.all לכל rule מתאים ו־\`CompositeMatch.component_fact_keys\` שווים להם בדיוק. \`dependency_roots\`: placement→body:{body}; aspect→שני body roots; house→body+angle:ascendant; composite→union roots של components. ראיות חופפות נשארות חופפות, בלי ספירה עצמאית.
4. \`fact_identity_digest = SHA256(canonical({chart_fingerprint,rulepack_digest,rule_id,when_canonical,fact_keys,time_mode}))\`; \`rule_hit_id = SHA256(canonical({fact_identity_digest,raw_rule_hit_exact_fields}))\`. ה־raw exact fields כוללים את כל ה־12 שדות ש־RuleHit פולט, כולל \`evidence_key\`, \`provisional\`, ו־\`weight\`; עיבוד טקסט canonical NFC, floats כ־canonical decimal אחרי בדיקת finite. כך אותו chart+pack+hit מניב מזהה זהה; אם שני raw hits זהים בתוך אותה ריצה — **reject duplicate** (אין ordinal מומצא).
5. \`witness_group_id = SHA256(canonical({chart_fingerprint,axis,polarity,raw_evidence_key,sorted(rule_hit_ids)}))\`; השדות \`evidence_key\` ו־\`fact_keys\` נשארים נפרדים; שינוי membership משנה group ID. \`alternative_set_id = SHA256(canonical({snapshot_id,route,definition_id,role,sorted(witness_group_ids)}))\`. בדיקת רשימת כל ה־members לכל group וכל חלופה ושמירת rejected proof reasons היא חובה. אין להתבסס על \`hits[0]\` של N2.
6. Route A: בצע read-only מיפוי \`R1.selected_witnesses_by_axis\` ו־\`alternative_facts_by_axis\` ל־groups שנגזרו וננעלו; אי־התאמה בין selected evidence_key ו־full member provenance ⇒ fail-closed. Route B: מיפוי שני component raw RuleHits לפי \`related_rule_ids\`, \`when.all\`, chart facts ו־source review; \`CompositeMatch.composite_is_independent_evidence=false\`. שמור legacy modifier RuleHit כמקור rule authoring/provenance, **לא** כ־root נוסף.
7. כל deriving step יוצר trace: input content digest, verification checks, rule_id, original canonical predicate, matched raw hit fields digest, fact_keys, roots, witness_group_id, all alternatives, audit order; stable hash reproducibility וניקוי PII. chart changes update chart_fingerprint ולכן IDs לא ניתנים למחזור על מפה חדשה.

### 4.2 ראיות חלקיות והוכחות לפי מסלול

לכל RelationEvaluation יש **שני RouteProof**: אחד לכל \`r1_path\` ואחד ל־\`original_composite\`. אם מסלול כלל אינו רלוונטי: candidate_state=not_candidate, search_state=not_applicable, search_complete=null, proof_result=not_candidate, visited=0. למסלול מועמד search_complete הוא true/false בלבד; false+visited cap => proof_result=unknown, failure_reason INCOMPLETE_SEARCH. הוכחת Route B נערכת מחדש מרכיבי \`when.all\`; היא אינה מותנית ב־R1 proof_search.complete, גם אם יש נתון R1 חסר/מוגבל. מסלול R1 שנקטע **אינו רשאי לדרוס Route B מלא**. זמן לא ודאי וסתירה ייבדקו ביחס לראיות שבחר כל route, ולסייגי המקור.

**היעדר ראיה:** RuleHit חסר, עובדה שמשתנה בדגימות, alternative שנבחרה בלי proof, או roots לא מורשים ⇒ check fail/unknown מפורש. מוכנות להצגת אטומים תקינים בנפרד נשמרת. אם כל החיפושים הרלוונטיים נקטעו אין negative claim; אם Route B הוכח והיחס מורשה ניתן להכריע לפיו גם כאשר Route A incomplete (תנאי N3Plan בסעיף 8).

## 5. SourceAnchor, רישוי מקור ובקרת תוכן — השלמת ARCH-03

\`SourceAnchor\` כעת כולל schema מלאה של \`SourceLocation\` (chapter, printed_page, section, line_start/end, scan_page_index; null רק כשלא ידוע ומדווח), \`language\`, \`accessed_at\`, \`source_version\`, \`anchor_hash\`, \`matching_conditions\` typed AST, \`scope_id\` מבוקר, מקור/מהדורה/כתובת, excerpt מוגבל, support_kind, review_status, source_text_verification, visual_verification, reviewer_id/time/revision ו־supported_effect_ids. ל־SourceAnchor חתימה עצמאית \`anchor_hash = SHA256(canonical(anchor excluding anchor_hash))\`; מקור יכול להיות תחת ביקורת גם אם definition לא אושרה ולהפך.

**שער כפול:** (א) Source review: קיום מקור פרטני, חיתוך excerpt בסעיף אמיתי, בדיקת תנאים ו־scope, אימות טקסט/צילום, reviewer+timestamp; (ב) Relation meaning review: האם העוגן מתיר בדיוק effect, כיוון, modality, limits, registry term semantics. \`reviewed\` אינו \`approved\`, וגם \`approved\` של מקור אינו \`approved_for_symbolic_wording\` של יחס. עד אישור שני השערים אין User Claim; statuses conflicting/rejected/framework_only/editorial/under_review חסומים.

| support_kind | שימוש מותר | חסם |
| --- | --- | --- |
| explicit_attestation + review_status=approved + licensed effect checked | אפשר להעריך את היחס בצירוף review עצמאי מאושר | עדיין כפוף P4/owner |
| explicit_attestation_candidate / under_review | רשומת מחקר, reviewer-only/shadow | אין Claim משתמש |
| framework_only / editorial_synthesis / hypothesis | תיאור מקור כללי/עריכתי/מחקרי | אין סמכות להסיק relation |
| contradicting / rejected / none | trace ו־abstention | אין claim |

**מקרה Alan Leo, תחת P0 בלבד:** printed page 62, Chapter XVIII, "The Sun in Aries and Moon in Taurus"; \`complements\` אפשרי רק כ־\`explicit_attestation_candidate\` מוגבל ליחס סמלי א־סימטרי; \`coordinates\` אינו מאושר מן המקור שנבדק, ואינו מאשר "שני קצבים שדורשים תיאום". source_text_verification=text_indexed; visual_verification=pending, reviewer_id=null, review_status=under_review; relation_review.status=under_review. צילום חזותי לא אומת; הספר נושא imprint year 1899 ו־actual publication year עדיין disputed (1900 candidate), עד ביבליוגרפיה עצמאית. אין מקור חיובי שאושר: **0 approved positive gold**. רק בודק עצמאי יוכל לעדכן סטטוסים; מסמך זה אינו אישור תוכן. אין המצאת מקורות נוספים, ו־P0 נפרד דורש אישור בעל מוצר.

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

**Candidate N3-SRC-AL-1899-p62**: Alan Leo, *Astrology for All*, imprint year 1899 (actual publication year disputed; 1900 candidate), Chapter XVIII, "The Sun in Aries and Moon in Taurus", printed page 62. מקור במעמד under_review בלבד; complements כיחס סמלי מועמד, coordinates אינו מאושר. 
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

## 8. N3Plan מכונה מאומתת והכרעות לפי מסלול — B5 / ARCH-01/08

במקום DecisionPlan לא־מאומת יש \`N3Plan\` נורמטיבי ב־N3-contract-2. הישות מכילה \`decision\`, \`primary_reason\`, \`reasons[]\` מטיפוס ReasonRecord (code+route+blocking+evidence_refs), \`retained_atomic_rule_ids\`, \`comparison_state\`, \`relation_claim_state\`, \`relation_claim_ids\`, \`route_proofs\` לשני המסלולים ו־\`trace\` חתום. בדיקה סמנטית מחייבת decision→claim state→proof status→source license→novelty, ולא רק סוגי JSON.

### 8.1 אלגוריתם הכרעה מפורש

**קדימות גלובלית:** INVALID_SCHEMA/SNAPSHOT_MISMATCH/PROVENANCE_MISMATCH/BAD_ID ⇒ INVALID_INPUT; פגיעה ברישוי מקור גלובלי (CONFLICTING_SOURCES/REJECTED_SOURCE) ⇒ QUARANTINE או ABSTAIN. לאחר validation, כל route מחושב **לבד**:
1. \`candidate_state=not_candidate\` + exhaustive exact match ⇒ NOT_APPLICABLE למסלול הזה, לא סיבת כישלון למסלול אחר.
2. \`candidate_state=candidate\`, \`search_complete=false\` או proof unknown ⇒ מסלול INDETERMINATE; אין להכריז no relation על סמך התוצאה.
3. \`search_complete=true\`, \`proof_result=proven\` ⇒ route eligible (בכפוף לתנאים, roots, time, tensions, source, meaning, novelty). ב־Route B ההוכחה **עצמאית** מ־R1, אינה נשענת על \`selected_witnesses_by_axis\`.
4. דרג routes eligible קנונית לפי \`original_composite\` ואז \`r1_path\` כששניהם מפיקים אותו effect; שמור שניהם ב־trace. Route A incomplete לא חסם את Route B proven.
5. לכל route proven, החלת gates: UNCERTAIN_TIME/DEPENDENT_ROOTS/MATERIAL_TENSION → ABSTAIN עבור אותו proof; MISSING_READING → COMPARISON_ONLY/ABSTAIN בהתאם ל־policy; NO_RELATION_SOURCE/FRAMEWORK_ONLY/EDITORIAL_ONLY/UNVERIFIED_RELATION → COMPARISON_ONLY/QUARANTINE; PARAPHRASE_ONLY/UNLICENSED_DELTA/SOURCE_SCOPE_EXCEEDED/OPERATOR_EFFECT_MISMATCH → COMPARISON_ONLY/ABSTAIN; רק כל passes ⇒ RELATION_LICENSED (audience shadow עד P4).
6. **אם אף route eligible לא השלים, ולפחות route רלוונטי אחד INDETERMINATE** ⇒ N3Plan INDETERMINATE. **אם Route B proven וה־source לא מורשה**, החלטת plan על B תהיה COMPARISON_ONLY/QUARANTINE, גם אם Route A incomplete; ראיית A מקבלת reason \`blocking=false\` בלבד.
7. אם שני routes מוכחים אבל מובילים ל־effects מנוגדים, material conflict מסומן ואינו נבחר לפי "כמה ראיות"; החסם אינו פוגע בקריאות האטומיות התקינות. אם routes מוכחים לאותו effect, dedupe ואין כפילות ראיה.

**Priority מקומי (רק ל־decisive route):** invalid > source contradiction > time uncertainty > incomplete proof > unmatched conditions > material tension > independent roots violation > missing required reading/atom mapping > absent/unapproved source > operator/scope/novelty violation > license passes. \`primary_reason\` הוא code של העילה החוסמת הגבוהה ביותר על route שהכריע (או NONE כאשר licensed). \`reasons[]\` שומר את כולן, כולל diagnostic nonblocking של route אחר; sorted by (route priority, blocking desc, code), primary חייב להתקיים ברשומות כאשר אינו NONE. COMPLETED Route B אינו inherit incomplete from Route A. כל output מסמן במפורש comparison_state, relation_claim_state ואילו אטומים תקינים נשמרו.

**כללי consistency לדוגמה:** 
- \`RELATION_LICENSED\` מחייב source_license_check=pass, novelty_check=pass, decisive route proven+complete, \`relation_claim_state=licensed_shadow\`, claim_ids nonempty and verified; primary_reason=NONE (רק במצב Shadow לפני P4).
- \`COMPARISON_ONLY\` מחייב 0 relation_claim_ids, \`relation_claim_state=blocked\`, comparison_state=available, source/meaning/effect reason תואם.
- \`INDETERMINATE\` מחייב route candidate incomplete/unknown *שלא הוכרע בידי מסלול מלא אחר*, ללא relation claim, reason INCOMPLETE_SEARCH/PROOF_UNKNOWN/UNCERTAIN_TIME.
- \`NOT_APPLICABLE\` מחייב שני routes שלא סיפקו candidate לאחר חיפוש ראיות רלוונטי שהושלם או not_applicable; false negative אסור.
- \`INVALID_INPUT\` מחייב validation error; retained atoms רק אם אומתו עצמאית ולא נפגעו מ־snapshot mismatch.
- \`ABSTAIN\` ו־\`QUARANTINE\` אינם הופכים מקור לא מאושר למורשה; N2 atoms מוגבלים נשמרים לפי gate המקורי.

### 8.2 דוגמאות JSON מאומתות מבנית

**VALID, מקור לא מאושר: Route B proven; R1 truncated** — נבחרה השוואה, לא הסתמכות על חיפוש R1 החלקי:

~~~json
{
  "kind": "N3Plan",
  "schema_version": "N3-contract-2",
  "plan_id": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
  "snapshot_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "definition_id": "n3.rel.sun-aries-moon-taurus.complement",
  "evaluation_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "decision": "COMPARISON_ONLY",
  "primary_reason": "NO_RELATION_SOURCE",
  "reasons": [
    {
      "code": "NO_RELATION_SOURCE",
      "route": "original_composite",
      "blocking": true,
      "evidence_refs": []
    },
    {
      "code": "INCOMPLETE_SEARCH",
      "route": "r1_path",
      "blocking": false,
      "evidence_refs": []
    }
  ],
  "retained_atomic_rule_ids": [
    "moon-sign-2",
    "sun-sign-1"
  ],
  "comparison_state": "available",
  "relation_claim_state": "blocked",
  "relation_claim_ids": [],
  "route_proofs": [
    {
      "route": "r1_path",
      "candidate_state": "candidate",
      "search_state": "incomplete",
      "search_complete": false,
      "visited": 20000,
      "cap": 20000,
      "proof_result": "unknown",
      "selected_binding_ids": [],
      "alternative_set_ids": [],
      "source_fact_refs": [],
      "failure_reasons": [
        "INCOMPLETE_SEARCH"
      ],
      "trace_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    },
    {
      "route": "original_composite",
      "candidate_state": "candidate",
      "search_state": "complete",
      "search_complete": true,
      "visited": 2,
      "cap": 20000,
      "proof_result": "proven",
      "selected_binding_ids": [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ],
      "alternative_set_ids": [],
      "source_fact_refs": [
        "placement:שמש:טלה",
        "placement:ירח:שור"
      ],
      "failure_reasons": [],
      "trace_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    }
  ],
  "trace": {
    "source_snapshot_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "adapter_trace_hash": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "evaluation_trace_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "selected_decisive_route": "original_composite",
    "atomic_evidence_refs": [
      "placement:שמש:טלה",
      "placement:ירח:שור"
    ]
  }
}
~~~

**INVALID SEMANTIC DECISION** — JSON כשלעצמו עומד בטיפוסים, אך אותה ראיה עם \`NO_RELATION_SOURCE\` אינה יכולה להניב \`RELATION_LICENSED\`. validator חוצה־אובייקטים חייב לדחות:

~~~json
{
  "kind": "N3Plan",
  "schema_version": "N3-contract-2",
  "plan_id": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "snapshot_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "definition_id": "n3.rel.sun-aries-moon-taurus.complement",
  "evaluation_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "decision": "RELATION_LICENSED",
  "primary_reason": "NO_RELATION_SOURCE",
  "reasons": [
    {
      "code": "NO_RELATION_SOURCE",
      "route": "original_composite",
      "blocking": true,
      "evidence_refs": []
    },
    {
      "code": "INCOMPLETE_SEARCH",
      "route": "r1_path",
      "blocking": false,
      "evidence_refs": []
    }
  ],
  "retained_atomic_rule_ids": [
    "moon-sign-2",
    "sun-sign-1"
  ],
  "comparison_state": "available",
  "relation_claim_state": "licensed_shadow",
  "relation_claim_ids": [
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
  ],
  "route_proofs": [
    {
      "route": "r1_path",
      "candidate_state": "candidate",
      "search_state": "incomplete",
      "search_complete": false,
      "visited": 20000,
      "cap": 20000,
      "proof_result": "unknown",
      "selected_binding_ids": [],
      "alternative_set_ids": [],
      "source_fact_refs": [],
      "failure_reasons": [
        "INCOMPLETE_SEARCH"
      ],
      "trace_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    },
    {
      "route": "original_composite",
      "candidate_state": "candidate",
      "search_state": "complete",
      "search_complete": true,
      "visited": 2,
      "cap": 20000,
      "proof_result": "proven",
      "selected_binding_ids": [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      ],
      "alternative_set_ids": [],
      "source_fact_refs": [
        "placement:שמש:טלה",
        "placement:ירח:שור"
      ],
      "failure_reasons": [],
      "trace_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    }
  ],
  "trace": {
    "source_snapshot_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "adapter_trace_hash": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "evaluation_trace_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "selected_decisive_route": "original_composite",
    "atomic_evidence_refs": [
      "placement:שמש:טלה",
      "placement:ירח:שור"
    ]
  }
}
~~~

**INVALID AST** — \`any\` עם ארגומנט יחיד ו־\`not\` ללא arg חוקי חייבים להידחות על ידי JSON Schema:

~~~json
{"op":"any","args":[{"op":"time_stable","role":"A"}]}
~~~

**INVALID Effect** — RelationDefinition.operator=coordinates עם Effect.predicate=symbolic_complement נכשל ב־operator/effect cross validator, גם אם Effect JSON תקין בפני עצמו. דוגמת bare effect בעלת predicate חלופי לא מהווה היתר.

**תנאי test:** validation ב־P1 חייב לחשב מחדש signature IDs ולהראות שאין "קידום" בגלל חיפוש חלקי או מקור לא מאומת. דוגמאות עם hash תבניתי (a…f) הן fixture תחבירי בלבד, **לא חתימות אמיתיות** ולא objects שניתן לטעון למאגר production; כשמפעילים hash validator תרחיש זה נכשל במכוון עד החלפתן בחתימות שנגזרו בפועל.

## 9. חוזה PR #29 / N2 content categories ו־snapshot admission — B2 / ARCH-06

**קריאת GitHub מאומתת בתאריך 2026-11-08:** PR #29 היה ב־HEAD \`aea7fe31ab2107e70787163965de142b4242b6de\` בעת התיקון (ה־HEAD עשוי להתעדכן שוב); \`meaning_catalog_n2.json\`: schema_version=1, catalog_version=\`0.3.1\`, \`entries=13\`, \`rule_readings=77\`, \`symbolic_explanations=6\`, \`withheld_editorial_readings=3\`. קודם בגרסת בסיס PR #27: catalog \`0.2.0\` עם \`rule_readings=26\`. המספר 86 משקף סך רשומות 77+6+3 בתמונת 0.3.1, **לא** 86 הרחבות פעילות. SHA הקטלוג של תמונת האימות: \`6138abf94b8eb8a0490d04f05fb52d095a382bf5\` (Git blob SHA; אינו תחליף ל־SHA256 של canonical bytes).

**טיפוסי תוכן נפרדים:**
- \`rule_readings\`: \`kind=rule_reading\`, מקור טקסט מקורי תואם, focus/setting/behavior/distinction/limit; קטגוריה \`behavioral_rule_reading\`, סטטוס \`unverified\`, רק כאשר מדיניות N2 מרשה בהקשר ותנאי rule/polarity תואמים. אינם מקור אישור ליחס N3.
- \`symbolic_explanations\`: \`kind=symbolic-explanation\`, \`source_support=original-unverified-rule-text-only\`, \`display_policy=non-behavioral-metadata-only-not-personality-N2\`. קטגוריה \`symbolic_explanation\`; **metadata symbolic** ללא behavior/diagnosis ואינו הופך אוטומטית ל־SemanticAtom התנהגותי.
- \`withheld_editorial_readings\`: \`status=quarantined-from-N2-display\` עם reason, original_editorial_reading, original source text. קטגוריה \`withheld_editorial_reading\`; לעולם אין לצרף ל־NarrativeClaim או להשלים ממנו missing N2 reading, גם כאשר כלל המקור matched.
- \`entries\`: axis meanings של R1, **לא** רישיון לקישור semantic_relation. מקור RulePack 96 כללים לא משתנה.

**UpstreamManifest admissibility, ללא ספירת תוכן קשיחה:** בקרת schema_version, catalog_version + SHA256 canonical מלא, חותמות נפרדות של ארבע קטגוריות (\`entries\`, \`rule_readings\`, \`symbolic_explanations\`, \`withheld_editorial_readings\`) + digest מדיניות \`rule_reading_policy\` ומדיניות display מפורשת בכל רשומה. אמת ID uniqueness, disjoint eligible rule_id across categories, exact source_rule_text מול RulePack, type/axis/polarity, provenance.review_status, license policy; withheld רשומות גוברות על גרסאות פירוש ישנות (no fallback to older active). אין merge של category arrays בזיכרון בין ענפים. \`compatible_upstream_hash\` נגזר מ־UpstreamManifest **בלי קטלוג N3**, לפי סעיף 2; manifest header מחויב ל־versions + content digest, לא count קבוע.

**Branch drift protocol:** לפני כל P1 test / runtime admission / release: fetch PR #29 HEAD מחדש ולקרוא את קובץ JSON מאותו commit (לא להסתמך על PR body/README או על HEAD ידני ישן); אם SHA התחלף, עצור admission, צור immutable manifest חדש, פתח impact report על שינויים בקטגוריות/IDs/source text/status/display policies, rerun cross-catalog validation וגילוי בעיות; קבל חתימה חדשה רק לאחר בקרת תוכן. בעת test היסטורי רשום במפורש \`upstream_ref_type=locked_fixture\` ו־HEAD, ולא טען שזו הגרסה העדכנית. במוצר, snapshot בלתי תואם נדחה אטומית (אין fallback 26/77 או 77+6+3 כאילו כולם readings).

**אין שינוי ב־PR #29**, אין העתקה ידנית של הקטלוג, אין RulePack כפול ואין שינוי R1/N1/N2/R2. N3 מתייחס ל־source-of-truth דרך read-only adapter וחוזה חתימות.

## 10. תוכנית עתידית P0–P4: תנאי כניסה ותנאי קבלה

| שלב | תנאי כניסה | תוצר עתידי | בדיקות/קבלה |
| --- | --- | --- | --- |
| **P0 — Knowledge/source audit** | אישור בעל מוצר למחקר מקורות נפרד; המפרט בלבד | צילום עמוד/הכרעה ב־Alan Leo, תיעוד 4 composite, הפרדה source/relation review | visual primary check + בודק עצמאי; complements candidate בלבד עד חתימה; coordinates לא מאושר; 0 gold positive approved עד אישור |
| **P1 — Contracts/validators** | ביקורת חוזרת עצמאית המאשרת B1–B5 **ואישור בעל מוצר מפורש נפרד** | N3-contract-2, UpstreamManifest, TermRegistry, EvidenceAdapter, N3Plan validators | DAG acyclic, repeat deterministic, fail-closed snapshot/AST/effect/ID/route decision; אין מימוש לפני האישורים |
| **P2 — Matcher (Shadow)** | P1 מאושר ועומד בבדיקות; frozen N2 snapshot מכל קטגוריה | dual-route matcher, proof/alternatives/trace | 4/4 composite ב־Route B; R1 incomplete לא חוסם B proven; independent/uncertain/conflicting/capped cases |
| **P3 — Semantic composition (Shadow)** | P2 עבר, synthetic licensed fixtures ו־baseline עם RulePack original composite/N2 | typed effects, entailment, novelty, human review | N2-vs-N3 paired, no false novelty from text paraphrase, source scope, blinded judges, 0 user claims ללא approved gold |
| **P4 — Read-only integration** | approved real positive gold, content + engineering review, owner approval | disabled-by-default feature flag, scoped symbolic claims | Linux/Windows E2E, GUI/EXE/export regression, source revocation and no-R2 approval, no merge/release אוטומטי |

**P0 ניתן לבצע כמחקר נפרד רק באישור בעל מוצר; P1–P4 אינם מאושרים למימוש**. Schema validation מקומית של מסמך אינה אישור מפורש לעבור שלב.

## 11. אימות מסמך ובדיקות קבלה ל־B1–B5

| Test | ציפייה |
| --- | --- |
| B1-01 topological DAG | RulePack/N2/ontology/interfaces→upstream→definition→relation catalog→snapshot→evaluation/claim; אין cycle |
| B1-02 deterministic | canonical replay זהה ⇒ אותם hashes; שינוי source/reading/category policy ⇒ invalidated downstream |
| B1-03 mismatch | compatible_upstream_hash, definition_hash, catalog_digest או snapshot_id שגוי ⇒ reject atomic |
| B2-01 current structure | ב־0.3.1 ממוינות 77 behavioral, 6 symbolic, 3 withheld, בלי hard-coded acceptance counts |
| B2-02 new HEAD | שינוי PR #29 HEAD או schema/categories/policy מחייב re-pin+review; no silent fallback |
| B3-01 AST | any עם בן יחיד, not ללא arg, unknown leaf/field, negated mandatory role ⇒ reject |
| B3-02 operator | coordinates→symbolic_complement / scope ID missing / direction swap ⇒ reject |
| B3-03 novelty | relation שכבר הוזכר ב־original composite אינו "חדש" בגלל JSON key שונה |
| B3-04 human | unknown semantic equivalence/entailment ⇒ human gate, not licensed |
| B4-01 identity | RuleHit המקורי (ללא rule_hit_id) יוצר ID דטרמיניסטי מהמקור; repeat stable |
| B4-02 composite | 2 original fact keys + union of roots; no third fact, no duplicated witness count |
| B4-03 alternatives | every original grouped member retained; no silent hits[0] or alternative swap |
| B5-01 envelope | schema for DecisionPlan=N3Plan; primary_reason/reasons/atomic/comparison/relation/trace required |
| B5-02 partial | R1 incomplete, B independently complete ⇒ B eligible; A warning nonblocking |
| B5-03 all incomplete | INDETERMINATE, never negative exhaustion claim |
| B5-04 forbidden decision | no source + RELATION_LICENSED rejected despite syntactically valid JSON |
| Source-01 | language/location/access date/anchor_hash/matching_conditions required and cross-reviewed |
| Source-02 | Alan Leo under_review, visual pending, complements candidate; coordinates blocked; gold=0 |

**סוג הבדיקה כיום:** המפרט מכיל JSON Schema מבנית ודוגמאות, שייבדקו בניתוח JSON, refs, required keys והדגמת פסילות מבניות. לא נוצרו Python validators / מנוע N3 במסגרת המשימה. בדיקת entailment האנושית ו־visual primary source מחייבות עבודה נפרדת ב־P0.

## 12. חסמים וגבולות

**טרם הוכרע:** (1) ביקורת ארכיטקטורה עצמאית חוזרת על B1–B5; (2) בעל מוצר מאשר/דוחה תחילת P0 מחקרית ואת P1 בהמשך בהליך נפרד; (3) אימות צילום עמוד Alan Leo, מפתחות ביבליוגרפיים והכרעת source review ו־relation review נפרדות; (4) תרגום typed TermRegistry של מקור + N2 לאנוטציות מבוקרות לאחר אישור; (5) gold test corpus אמיתי אחרי אישור מקור; (6) קליטת snapshot PR #29 הסופי לפי immutable content digest. **נכון למסירה: 0 positive gold approved.**

**איסורים:** אין מימוש N3/P1, אין שינוי R1/N1/N2/R2, RulePack 96 או PR #29, אין LLM, אין פרשנות משולבת בדוח משתמש, אין merge ל־main ואין Release. כל claims הם symbolic source-attributed בלבד, לא טענה אמפירית/ביוגרפית. המפרט אינו מאשר את עצמו; נדרשת הכרעת ביקורת עצמאית ואישור בעל מוצר אחריה.

---
**הכרעת תכנון:** תכנון N3 מחייב DAG חתימות, מיפוי קטגוריות N2 חתום, AST טיפוסי עם scope מבוקר, מזהי עובדות נגזרים ממקור ו־N3Plan עם הכרעות לפי route. היתרונות נבחנים על delta סמנטי מורשה ולא על מספר המשפטים; הימנעות עם trace היא תוצאה תקינה.
