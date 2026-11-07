"""Skyfield/JPL DE440s; no network calls at runtime."""
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .domain import BodyPosition, Chart, calculate_aspects, house_of, sign_index
from .timeconv import full_local_day, local_to_utc

EPHEMERIS_NAME = "de440s.bsp"
TARGETS = (
    ("שמש", "sun"), ("ירח", "moon"), ("מרקורי", "mercury"),
    ("ונוס", "venus"), ("מאדים", "mars"), ("צדק", "jupiter barycenter"),
    ("שבתאי", "saturn barycenter"), ("אורנוס", "uranus barycenter"),
    ("נפטון", "neptune barycenter"), ("פלוטו", "pluto barycenter"),
)


def ephemeris_path() -> Path:
    # The frozen app has _MEIPASS; the source project has data/ at its root.
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data" / "ephemeris" / EPHEMERIS_NAME
    return Path(__file__).resolve().parents[2] / "data" / "ephemeris" / EPHEMERIS_NAME


def ascendant_mc(t, latitude: float, longitude: float) -> tuple[float, float]:
    """East-horizon intersection and upper meridian of true ecliptic of date."""
    from skyfield.nutationlib import mean_obliquity, iau2000a_radians
    epsilon = math.radians(mean_obliquity(t.tdb) / 3600) + iau2000a_radians(t)[1]
    theta = math.radians((t.gast * 15.0 + longitude) % 360.0)
    phi = math.radians(latitude)
    # East-horizon ecliptic intersection; select the rising (eastern) root.
    numerator = math.cos(theta)
    denominator = -(math.sin(theta) * math.cos(epsilon)
                    + math.tan(phi) * math.sin(epsilon))
    asc = math.degrees(math.atan2(numerator, denominator)) % 360
    mc = math.degrees(math.atan2(math.sin(theta) / math.cos(epsilon),
                                math.cos(theta))) % 360
    return asc, mc


class Calculator:
    def __init__(self, kernel: Path | None = None):
        from skyfield.api import load_file, load
        self.kernel = kernel or ephemeris_path()
        if not self.kernel.is_file():
            raise FileNotFoundError(
                "קובץ האפמריס חסר בחבילה: " + str(self.kernel))
        self.planets = load_file(str(self.kernel))
        self.timescale = load.timescale(builtin=True)
        from skyfield.framelib import ecliptic_frame
        self.ecliptic_frame = ecliptic_frame
        self.earth = self.planets["earth"]

    def position(self, moment: datetime, target: str) -> float:
        if moment.utcoffset() is None:
            raise ValueError("UTC datetime with timezone is required")
        t = self.timescale.from_datetime(moment.astimezone(timezone.utc))
        apparent = self.earth.at(t).observe(self.planets[target]).apparent()
        _, lon, _ = apparent.frame_latlon(self.ecliptic_frame)
        return lon.degrees % 360

    def _positions(self, moment: datetime) -> list[BodyPosition]:
        delta = timedelta(minutes=30)
        positions = []
        for name, target in TARGETS:
            lon = self.position(moment, target)
            previous = self.position(moment - delta, target)
            following = self.position(moment + delta, target)
            motion = (following - previous + 180) % 360 - 180
            positions.append(BodyPosition(name, lon, motion < 0))
        return positions

    def calculate(self, day, clock, zone_name: str, latitude: float,
                  longitude: float, unknown_time: bool = False) -> Chart:
        if not (-90 < latitude < 90) or not (-180 <= longitude <= 180):
            raise ValueError("קו רוחב חייב להיות בין הקטבים, וקו אורך בין ‎-180 ל־180")
        warnings = [
            "צדק עד פלוטו מחושבים לפי מרכזי המסה של המערכות הפלנטריות (JPL)."
        ]
        if unknown_time:
            start, end = full_local_day(day, zone_name)
            # Midpoint is NOT represented as a birth hour: only a display sample.
            midpoint = start + (end - start) / 2
            bodies = self._positions(midpoint)
            samples = []
            at = start
            while at < end:
                samples.append(self._positions(at))
                at += timedelta(hours=1)
            samples.append(self._positions(end - timedelta(seconds=1)))
            for idx, body in enumerate(bodies):
                body.signs_possible = tuple(sorted({
                    sign_index(sample[idx].longitude) for sample in samples
                }))
                body.motion_uncertain = len({
                    sample[idx].retrograde for sample in samples
                }) > 1
            warnings.append(
                "שעת הלידה אינה ידועה: המעלות וההיבטים הם דוגמה מנקודת האמצע "
                "של היום האזרחי ולא נתוני לידה מדויקים. אין אופק, MC או בתים.")
            if any(len(b.signs_possible) > 1 for b in bodies):
                warnings.append("גוף אחד לפחות עשוי להחליף מזל במהלך היום.")
            return Chart(bodies, calculate_aspects(bodies), None, None, True, warnings)
        if clock is None:
            raise ValueError("יש להזין שעה או לסמן ששעת הלידה אינה ידועה")
        local = datetime.combine(day, clock)
        moment = local_to_utc(local, zone_name)
        bodies = self._positions(moment)
        t = self.timescale.from_datetime(moment)
        asc, mc = ascendant_mc(t, latitude, longitude)
        for body in bodies:
            body.house = house_of(body.longitude, asc)
        if abs(latitude) >= 66.5:
            warnings.append("קו רוחב קיצוני: יש לאמת במיוחד את זוויות המפה.")
        return Chart(bodies, calculate_aspects(bodies), asc, mc, False, warnings)
