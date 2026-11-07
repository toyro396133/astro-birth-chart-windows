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


def spread_marker_angles(longitudes: list[float], min_gap: float = 15.0) -> list[float]:
    """Spread *labels*, never astronomical positions, around the full circle.

    Rotate the ring at its largest empty gap then apply isotonic regression
    to find the least-squares displacement with at least min_gap degrees
    between adjacent labels. Original longitude anchors remain unchanged.
    Handles clusters crossing 0 degrees without special cases.
    """
    n = len(longitudes)
    if n <= 1:
        return [float(a) % 360 for a in longitudes]
    if min_gap <= 0 or n * min_gap >= 360:
        raise ValueError("Marker gap must fit in a full circle")
    order = sorted(range(n), key=lambda i: longitudes[i] % 360)
    angles = [longitudes[i] % 360 for i in order]
    gaps = [angles[i + 1] - angles[i] for i in range(n - 1)]
    gaps.append(angles[0] + 360 - angles[-1])
    cut = (gaps.index(max(gaps)) + 1) % n
    order = order[cut:] + order[:cut]
    unwrapped = []
    for i in order:
        a = longitudes[i] % 360
        if unwrapped and a < unwrapped[-1]:
            a += 360
        unwrapped.append(a)

    # Pool adjacent violators algorithm: optimal order-preserving spacing.
    blocks = []
    for i, a in enumerate(unwrapped):
        blocks.append([i, i, a - i * min_gap, 1])
        while len(blocks) > 1 and (
            blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]
        ):
            last = blocks.pop()
            blocks[-1][1] = last[1]
            blocks[-1][2] += last[2]
            blocks[-1][3] += last[3]

    result = [0.0] * n
    for first, last, total, count in blocks:
        for i in range(first, last + 1):
            result[order[i]] = (total / count + i * min_gap) % 360
    return result
