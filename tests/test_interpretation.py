"""Rule-engine contracts: evidence, extensibility, uncertainty and safe overlays."""
import json
from dataclasses import replace

import pytest

from astrochart.domain import Aspect, BodyPosition, Chart
from astrochart.interpretation import (
    RulePackError, format_interpretation, interpret_chart, load_rulepack, model_input,
)


def sample_chart(*, unknown=False, estimated=False):
    sun = BodyPosition("שמש", 12.4, False, (0,), house=None if unknown else 1)
    moon = BodyPosition("ירח", 41.1, False, (1,), house=None if unknown else 2)
    mercury = BodyPosition("מרקורי", 35.0, False, (1,), house=None if unknown else 2)
    return Chart(
        [sun, moon, mercury],
        [Aspect("שמש", "ירח", "ריבוע", 91.0, 1.0)],
        None if unknown else 20.0,
        None if unknown else 96.0,
        unknown,
        ["שעת הלידה משוערת לצורך הבדיקה"] if estimated else [],
    )


def test_builtin_pack_has_stable_evidence_schema():
    pack = load_rulepack()
    assert pack.version == "0.2.0"
    assert len(pack.rules) == 96
    assert all(rule.get("review_status") in {"reviewed", "unverified"} for rule in pack.rules)
    assert pack.tradition == "western-tropical-whole-sign"
    assert len(pack.rules) >= 40
    assert len({r["id"] for r in pack.rules}) == len(pack.rules)
    report = interpret_chart(sample_chart(), pack)
    assert report["schema_version"] == 1
    assert report["status"] == "symbolic-editorial"
    assert report["time_uncertain"] is False
    ids = {hit["rule_id"] for hit in report["signals"]}
    assert "sun-sign-1" in ids
    assert "moon-sign-2" in ids
    assert "mercury-sign-2" in ids
    assert "sun-house-1" in ids
    assert report["axes"] and all(axis["evidence_ids"] for axis in report["axes"])
    assert all(hit["evidence"] and hit["source"] for hit in report["signals"])
    assert report == interpret_chart(sample_chart(), pack)
    result = format_interpretation(report)
    assert "כלל sun-sign-1" in result
    assert "אינה אבחון אופי מדעי" in result


def test_unknown_hour_rejects_house_midpoint_aspect_and_ambiguous_moon_sign():
    chart = sample_chart(unknown=True)
    moon = chart.bodies[1]
    moon.signs_possible = (1, 2)
    report = interpret_chart(chart)
    ids = {hit["rule_id"] for hit in report["signals"]}
    assert "sun-sign-1" in ids
    assert not any(rule.startswith("moon-sign") for rule in ids)
    assert not any("-house-" in rule for rule in ids)
    assert not any("trine" in rule or "square" in rule for rule in ids)
    assert report["time_uncertain"]
    assert "עשויים לעבור מזל" in " ".join(report["warnings"])
    context = model_input(chart, report)
    assert context["chart_facts"]["aspects"] == []
    assert all(item["house"] is None for item in context["chart_facts"]["bodies"])
    assert context["generation_constraints"]["do_not_invent_chart_facts"]
    assert context["chart_facts"]["bodies"][1]["possible_signs"] == ["שור", "תאומים"]


def test_estimated_clock_suppresses_houses_and_aspects():
    chart = sample_chart(estimated=True)
    report = interpret_chart(chart)
    assert report["time_uncertain"]
    assert all(not h["rule_id"].startswith("sun-house-") for h in report["signals"])
    assert all(h["provisional"] for h in report["signals"])
    assert model_input(chart, report)["chart_facts"]["aspects"] == []


def test_no_chart_raises_and_missing_facts_dont_generate_rules():
    with pytest.raises(ValueError):
        interpret_chart(None)
    chart = Chart([], [], None, None, True, [])
    report = interpret_chart(chart)
    assert not report["signals"]
    assert not report["axes"]
    assert any("אין מספיק" in s for s in report["warnings"])


def test_overlay_disable_add_and_version_audit(tmp_path):
    overlay = {
        "schema_version": 1,
        "base_pack_version": "0.2.0",
        "pack_version": "0.3.0",
        "rules": [
            {"id": "sun-sign-1", "enabled": False},
            {
                "id": "custom-focus-aries", "enabled": True, "type": "placement",
                "when": {"body": "שמש", "sign": "טלה"},
                "axis": "דיוק ויוזמה משולבים", "polarity": -1, "weight": 2.75,
                "text": "כלל ניסוי מקומי לשילוב צירים בפרשנות, אינו אבחוני.",
                "source": "בדיקה עריכתית ידנית, גרסה חדשה",
            },
        ],
    }
    f = tmp_path / "overlay.json"
    f.write_text(json.dumps(overlay, ensure_ascii=False), encoding="utf-8")
    pack = load_rulepack(overlay_path=f)
    assert pack.version == "0.3.0"
    report = interpret_chart(sample_chart(), pack)
    ids = {s["rule_id"] for s in report["signals"]}
    assert "sun-sign-1" not in ids
    assert "custom-focus-aries" in ids
    assert report["pack_version"] == "0.3.0"
    signal = next(x for x in report["signals"] if x["rule_id"] == "custom-focus-aries")
    assert signal["polarity"] == -1
    assert signal["source"] == "בדיקה עריכתית ידנית, גרסה חדשה"


def test_overlay_requires_version_match_and_explicit_source(tmp_path):
    p = tmp_path / "over.json"
    def write(data):
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    bad = {"schema_version": 1, "base_pack_version": "9.0.0",
           "pack_version": "0.3.0", "rules": []}
    write(bad)
    with pytest.raises(RulePackError):
        load_rulepack(overlay_path=p)
    bad["base_pack_version"] = "0.2.0"
    bad["rules"] = [{"id": "sun-sign-1", "text": "נוסח מתוקן בלי מקור"}]
    write(bad)
    with pytest.raises(RulePackError, match="מקור"):
        load_rulepack(overlay_path=p)


def test_invalid_rule_does_not_run_code_or_accept_malformed_pair(tmp_path):
    pack = {
        "schema_version": 1,
        "pack_version": "0.9.0",
        "tradition": "western-tropical-whole-sign",
        "rules": [{
            "id": "invalid-pair", "enabled": True, "type": "aspect",
            "axis": "גמישות", "polarity": 1, "weight": 1,
            "text": "נוסח כלל היבט שנועד לבדיקה בלבד.",
            "source": "בדיקת אימות נתונים",
            "when": {"pair": [[], "שמש"], "kind": "ריבוע"},
        }],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RulePackError):
        load_rulepack(path=path)


def test_opposing_signals_are_explained_not_hidden():
    chart = sample_chart()
    original = load_rulepack()
    custom = {
        "id": "manual-counter-signal", "enabled": True, "type": "placement",
        "when": {"body": "שמש", "sign": "טלה"},
        "axis": "יוזמה", "polarity": -1, "weight": 1,
        "text": "נוסח נגדי לצורך בדיקת הצגת סתירות.",
        "source": "בדיקה ממוקדת לגרסאות הכללים",
    }
    from astrochart.interpretation import RulePack
    pack = RulePack(original.version, original.tradition,
                    original.rules + (custom,))
    report = interpret_chart(chart, pack)
    initiative = next(a for a in report["axes"] if a["axis"] == "יוזמה")
    assert initiative["has_tension"] is True
    assert initiative["support"] > 0 and initiative["counter"] > 0
    assert "אין מסקנה חד־משמעית" in format_interpretation(report)


def test_rulepack_file_size_limit(tmp_path):
    path = tmp_path / "too-large.json"
    path.write_bytes(b"x" * 260_000)
    with pytest.raises(RulePackError):
        load_rulepack(path=path)


def test_axis_heading_is_human_readable_not_python_dict():
    result = format_interpretation(interpret_chart(sample_chart()))
    assert "◆ יוזמה" in result
    assert "◆ {'axis':" not in result


def test_unknown_hour_never_exports_noon_sample_as_natal_longitude():
    chart = sample_chart(unknown=True)
    report = interpret_chart(chart)
    assert report["time_mode"] == "unknown"
    assert all("12.40°" not in h["evidence"] for h in report["signals"])
    bodies = model_input(chart, report)["chart_facts"]["bodies"]
    assert all(b["longitude"] is None and b["longitude_is_sample"] for b in bodies)
    assert all(not b["sign_is_confirmed"] for b in bodies)


def test_estimated_time_near_sign_boundary_is_not_reported_as_certain():
    chart = sample_chart(estimated=True)
    chart.bodies[0].longitude = 0.1
    report = interpret_chart(chart)
    assert report["time_mode"] == "estimated"
    assert "sun-sign-1" not in {h["rule_id"] for h in report["signals"]}
    assert all("°)" not in h["evidence"] for h in report["signals"])


def test_same_fact_multiple_rules_count_once_and_keep_traceability():
    from astrochart.interpretation import RulePack
    base = load_rulepack()
    duplicate = {
        "id": "synthetic-duplicate-aries", "type": "placement",
        "when": {"body": "שמש", "sign": "טלה"},
        "axis": "יוזמה", "polarity": 1, "weight": 4,
        "text": "כפילות יזומה לבדיקת ספירה עצמאית.",
        "source": "מקרה סינתטי בלבד"
    }
    report = interpret_chart(sample_chart(), RulePack(
        base.version, base.tradition, base.rules + (duplicate,)))
    axis = next(a for a in report["axes"] if a["axis"] == "יוזמה")
    assert axis["support"] == 4
    assert axis["duplicated_rule_count"] == 1
    assert {"sun-sign-1", "synthetic-duplicate-aries"} <= set(axis["evidence_ids"])


def test_same_fact_opposing_polarity_is_explicit_source_conflict():
    from astrochart.interpretation import RulePack
    base = load_rulepack()
    counter = {
        "id": "synthetic-counter-aries", "type": "placement",
        "when": {"body": "שמש", "sign": "טלה"},
        "axis": "יוזמה", "polarity": -1, "weight": 1,
        "text": "פרשנות נוגדת לסימולציה.",
        "source": "מקרה סינתטי בלבד"
    }
    report = interpret_chart(sample_chart(), RulePack(
        base.version, base.tradition, base.rules + (counter,)))
    axis = next(a for a in report["axes"] if a["axis"] == "יוזמה")
    assert axis["tension_kind"] == "same-fact-conflict"
    assert axis["source_conflict_keys"] == ["placement:שמש:טלה"]


def test_composite_requires_both_facts_and_adds_no_independent_score():
    chart = sample_chart()
    report = interpret_chart(chart)
    axis = next(a for a in report["axes"] if a["axis"] == "יוזמה")
    assert "sun-aries-moon-taurus" in axis["modifier_rule_ids"]
    composite = next(h for h in report["signals"] if h["rule_id"] == "sun-aries-moon-taurus")
    assert composite["modifier_only"] and composite["weight"] == 0
    chart.bodies[1].longitude = 70
    changed = interpret_chart(chart)
    assert "sun-aries-moon-taurus" not in {h["rule_id"] for h in changed["signals"]}


def test_aspect_must_agree_with_positions_and_orb_cutoff():
    from astrochart.domain import calculate_aspects
    chart = sample_chart()
    assert "sun-moon-square" not in {h["rule_id"] for h in interpret_chart(chart)["signals"]}
    chart.bodies[1].longitude = chart.bodies[0].longitude + 96
    chart.aspects = calculate_aspects(chart.bodies)
    ids = {h["rule_id"] for h in interpret_chart(chart)["signals"]}
    assert "sun-moon-square" in ids
    chart.bodies[1].longitude += 0.1
    chart.aspects = calculate_aspects(chart.bodies)
    ids = {h["rule_id"] for h in interpret_chart(chart)["signals"]}
    assert "sun-moon-square" not in ids


def test_rejected_rule_fails_closed_and_legacy_pack_stays_compatible(tmp_path):
    base = json.loads((__import__("pathlib").Path(__file__).parents[1]
                       / "src/astrochart/interpretation_rules.json").read_text(encoding="utf-8"))
    base["rules"][0]["review_status"] = "rejected"
    target = tmp_path / "bad-pack.json"
    target.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RulePackError, match="סטטוס"):
        load_rulepack(path=target)
    base["rules"][0]["enabled"] = False
    target.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    assert len(load_rulepack(path=target).rules) == 95
