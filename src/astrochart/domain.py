from dataclasses import dataclass
from itertools import combinations

SIGNS = ("טלה", "שור", "תאומים", "סרטן", "אריה", "בתולה",
         "מאזניים", "עקרב", "קשת", "גדי", "דלי", "דגים")
BODIES = ("שמש", "ירח", "מרקורי", "ונוס", "מאדים",
          "צדק", "שבתאי", "אורנוס", "נפטון", "פלוטו")
ASPECTS = ((0, "צמידות", 8), (60, "שישים", 6), (90, "ריבוע", 6),
           (120, "משולש", 6), (180, "ניגוד", 8))


def sign_index(longitude: float) -> int:
    return int((longitude % 360) // 30)


def degree_in_sign(longitude: float) -> float:
    return longitude % 30


def short_separation(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def house_of(longitude: float, ascendant: float) -> int:
    """Whole Sign houses: cusp 1 starts at 0 degrees of Ascendant's sign."""
    return (sign_index(longitude) - sign_index(ascendant)) % 12 + 1


@dataclass
class BodyPosition:
    name: str
    longitude: float
    retrograde: bool
    signs_possible: tuple[int, ...] = ()
    motion_uncertain: bool = False
    house: int | None = None

    @property
    def sign(self) -> str:
        return SIGNS[sign_index(self.longitude)]


@dataclass
class Aspect:
    first: str
    second: str
    kind: str
    separation: float
    orb: float


@dataclass
class Chart:
    bodies: list[BodyPosition]
    aspects: list[Aspect]
    ascendant: float | None
    mc: float | None
    approximate: bool
    warnings: list[str]

    @property
    def descendant(self) -> float | None:
        return None if self.ascendant is None else (self.ascendant + 180) % 360

    @property
    def ic(self) -> float | None:
        return None if self.mc is None else (self.mc + 180) % 360


def calculate_aspects(bodies: list[BodyPosition]) -> list[Aspect]:
    result = []
    for a, b in combinations(bodies, 2):
        distance = short_separation(a.longitude, b.longitude)
        for exact, name, max_orb in ASPECTS:
            orb = abs(distance - exact)
            if orb <= max_orb:
                result.append(Aspect(a.name, b.name, name, distance, orb))
                break
    return sorted(result, key=lambda a: a.orb)
