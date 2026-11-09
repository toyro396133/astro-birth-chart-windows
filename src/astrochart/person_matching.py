"""Conservative, local-only matching for possible duplicate person names.

Exact normalized matches are always returned. Fuzzy matches require at least
6 normalized characters and a SequenceMatcher ratio of at least 0.86.
This deliberately avoids approximate matches for short names.
"""
from difflib import SequenceMatcher
import unicodedata

SIMILARITY_THRESHOLD = 0.86
MIN_FUZZY_NAME_LENGTH = 6

_DASHES = frozenset("-‐‑‒–—―־")
_QUOTE_MARKS = frozenset("'’‘ʼʻ`´׳״″“”„")


def normalize_person_name(name: str) -> str:
    """Normalize compatibility forms, case, whitespace and common punctuation."""
    if not isinstance(name, str):
        return ""
    value = unicodedata.normalize("NFKC", name).casefold()
    normalized = []
    for char in value:
        if char in _DASHES:
            normalized.append(" ")
        elif char in _QUOTE_MARKS:
            # Hebrew geresh/gershayim and apostrophe/quotation variants are
            # presentation marks, not meaningful separators in a person's name.
            continue
        elif char.isspace() or unicodedata.category(char).startswith("P"):
            normalized.append(" ")
        else:
            normalized.append(char)
    return " ".join("".join(normalized).split())


def find_similar_people(name: str, people, *, exclude_person_id: str | None = None):
    """Return deterministic exact/near matches without changing any records."""
    query = normalize_person_name(name)
    if not query:
        return []

    matches = []
    for person in people:
        if not isinstance(person, dict):
            continue
        person_id = person.get("id")
        if exclude_person_id is not None and person_id == exclude_person_id:
            continue
        candidate = normalize_person_name(person.get("name", ""))
        if not candidate:
            continue
        exact = query == candidate
        score = SequenceMatcher(None, query, candidate, autojunk=False).ratio()
        if exact or (
            min(len(query), len(candidate)) >= MIN_FUZZY_NAME_LENGTH
            and score >= SIMILARITY_THRESHOLD
        ):
            matches.append({
                "person_id": person_id,
                "name": person.get("name", ""),
                "score": score,
                "exact": exact,
            })

    matches.sort(key=lambda item: (
        not item["exact"], -item["score"], item["name"].casefold(),
        str(item["person_id"] or ""),
    ))
    return matches
