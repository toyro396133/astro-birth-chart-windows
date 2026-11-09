from astrochart.person_matching import (
    MIN_FUZZY_NAME_LENGTH, SIMILARITY_THRESHOLD,
    find_similar_people, normalize_person_name,
)


def person(person_id, name):
    return {"id": person_id, "name": name}


def test_exact_normalized_match_is_reported_even_for_short_names():
    matches = find_similar_people("דן", [person("a", "דן")])
    assert len(matches) == 1
    assert matches[0]["exact"] is True
    assert matches[0]["score"] == 1.0


def test_conservative_fuzzy_match_finds_a_typo_in_a_longer_hebrew_name():
    matches = find_similar_people(
        "דוד כוהן", [person("a", "דוד כהן")])
    assert len(matches) == 1
    assert matches[0]["exact"] is False
    assert matches[0]["score"] >= SIMILARITY_THRESHOLD
    assert MIN_FUZZY_NAME_LENGTH == 6


def test_short_names_do_not_generate_fuzzy_false_positives():
    assert find_similar_people(
        "דן", [person("a", "דני"), person("b", "דנה")]) == []
    assert find_similar_people(
        "אור", [person("c", "אורי")]) == []


def test_hebrew_spaces_maqaf_and_geresh_are_normalized_conservatively():
    left = "  ר׳  כהן־לוי  "
    right = "ר כהן - לוי"
    assert normalize_person_name(left) == normalize_person_name(right)
    matches = find_similar_people(left, [person("a", right)])
    assert len(matches) == 1 and matches[0]["exact"] is True


def test_nfkc_casefold_and_quote_marks_are_normalized():
    assert normalize_person_name("  Ｏ’ＮＥＩＬ ") == "oneil"
    assert find_similar_people("O'Neil", [person("a", "oneil")])[0]["exact"]


def test_edit_excludes_only_the_current_person_id():
    people = [person("self", "רות לוי"), person("other", "רות לוי")]
    matches = find_similar_people(
        "רות לוי", people, exclude_person_id="self")
    assert [match["person_id"] for match in matches] == ["other"]
