"""Per-release, per-package change journal. No network is needed to inspect it."""
from .updater import parts_version

JOURNAL = {
    "0.6.1": {
        "עדכונים והפצה": (
            ("חדש", "כפתור העדכון בהתקנת Windows רגילה תומך בחבילת עדכון חלקית, לפי גרסת מקור מדויקת."),
            ("שיפור", "אימות SHA-256 לכל קובץ שנשמר והעברת השדרוג דרך Inno Setup לשמירת רישום ההסרה."),
            ("שיפור", "חזרה אוטומטית למתקין המלא אם עדכון חלקי נכשל או אינו מתאים."),
            ("מידע", "משדרגים מגרסה ישנה שאינה תומכת בעדכון חלקי עשויים להוריד מתקין מלא בפעם הראשונה."),
        ),
    },
    "0.6.0": {
        "עדכונים והפצה": (
            ("חדש", "יומן שינויים לפי חבילות וגרסאות מתוך התוכנה."),
            ("חדש", "הצגת חידושים ותיקונים בעת זיהוי עדכון, לפני הורדה."),
        ),
        "קלט תאריכים": (
            ("חדש", "הזנת שנה לועזית עם חודש ויום עבריים ובחירת התאמה במקרה של עמימות."),
        ),
        "ייצוא": (
            ("חדש", "ייצוא PDF של גלגל המפה בלבד, ללא דוח או פרשנות."),
        ),
    },
    "0.5.1": {
        "פרשנות N2": (
            ("שיפור", "הרחבת מאגר הקריאות הפעילות ל־77 לפי הערות ההפצה של גרסה 0.5.1."),
        ),
    },
}


def render_release_notes(version: str) -> str:
    if version not in JOURNAL:
        raise ValueError("לגרסה זו אין יומן שינויים מאושר")
    lines = [f"AstroBirthChart v{version} — מה חדש", ""]
    for package, changes in JOURNAL[version].items():
        lines.append(f"## {package}")
        for kind, description in changes:
            lines.append(f"- {kind}: {description}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_history() -> str:
    return "\n\n".join(
        render_release_notes(version).strip()
        for version in sorted(JOURNAL, key=parts_version, reverse=True)
    )
