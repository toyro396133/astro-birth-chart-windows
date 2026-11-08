"""User-triggered, local-only plain text export of calculated chart facts.

No automatic personal predictions or external services. This report preserves
unknown-hour uncertainty; a possible sign is not presented as certain.
"""
from .domain import SIGNS, degree_in_sign


def format_chart_report(chart):
    if chart is None:
        raise ValueError("אין מפה מחושבת להעתקה")

    lines = [
        "AstroBirthChart — נתוני מפה",
        "מיקומים והיבטים מחושבים בלבד; לא תחזית או אבחון.",
        "שעת לידה: " + ("לא ידועה — תוצאות בקירוב" if chart.time_certainty == "unknown"
                          else "שעה משוערת — תוצאות לפי שעת הדגימה"
                          if chart.time_certainty == "estimated"
                          else "בהתאם לשעת החישוב"),
        "",
        "מיקומי גופים:",
    ]
    for body in chart.bodies:
        signs = " / ".join(SIGNS[i] for i in body.signs_possible) \
            if chart.approximate and body.signs_possible else body.sign
        degree = f"{degree_in_sign(body.longitude):.3f}°"
        motion = ("לא ודאי" if body.motion_uncertain
                  else "נסיגה" if body.retrograde else "ישירה")
        place = "לא מחושב" if body.house is None else str(body.house)
        lines.append(
            f"• {body.name}: {signs}, {degree}, בית: {place}, תנועה: {motion}"
            + (" (מעלה לדוגמה)" if chart.approximate else ""))
    if chart.ascendant is not None:
        lines.append("")
        lines.append(f"אופק: {chart.ascendant:.3f}°")
        if chart.mc is not None:
            lines.append(f"רום השמיים (MC): {chart.mc:.3f}°")

    lines.extend(["", "היבטים:"])
    if chart.aspects:
        lines.extend(
            f"• {a.first} – {a.second}: {a.kind}, "
            f"מרחק {a.separation:.2f}°, סטייה {a.orb:.2f}°"
            + (" (דגימת אמצע היום בלבד — לא היבט לידה)"
               if chart.time_certainty == "unknown" else
               " (לפי שעה משוערת)" if a.certainty == "estimated" else "")
            for a in chart.aspects)
    else:
        lines.append("לא נמצאו היבטים בהגדרות החישוב.")

    if chart.warnings:
        lines.extend(["", "הערות דיוק:"])
        lines.extend(f"• {w}" for w in chart.warnings)
    return "\n".join(lines) + "\n"
