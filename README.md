# Astro Birth Chart Windows — גרסה 0.1

תוכנת Windows מקומית לחישוב מפת לידה אסטרונומית: ממשק עברי RTL, מיקומי עשרה גופים, נסיגה, אופק/MC, בתי Whole Sign, היבטים וגלגל מפה. אין שרת, חשבונות, אנליטיקה או העברת נתוני לידה.

## התחלה על Windows

דרושות Python 3.12 ו-Python Launcher (py).

1. הורידו את המאגר.
2. פתחו PowerShell בשורש המאגר.
3. הריצו:  .\scripts\build_windows.ps1
4. פתחו:  dist\AstroBirthChart\AstroBirthChart.exe

הסקריפט מוריד את האפמריס *בזמן הבנייה בלבד*, בודק את חתימתו, מריץ בדיקות ומייצר EXE ותיקיית קבצי ריצה נלווים. יש להעתיק את **כל** התיקייה dist/AstroBirthChart, ולא רק את קובץ ה-EXE. אחרי הבנייה אין צורך בחיבור לאינטרנט.

## תחומי דיוק

- גלגל טרופי; אורכי הגופים הם גאוצנטריים, apparent, במסגרת true ecliptic/equinox of date באמצעות Skyfield ו-JPL DE440s.
- מאדים, צדק, שבתאי, אורנוס, נפטון ופלוטו ממוקמים לפי מרכזי מסה (barycenters) שמספקת DE440s; קיים הבדל זעיר לעומת מרכזי הדיסקה.
- טווח התוכנה: 1850–2149, בהתאם לאפמריס; שעת לידה מלאה מאפשרת חישוב בתים ו-MC/Asc.
- אזורי זמן היסטוריים מתקבלים מ-IANA דרך tzdata מקומי; שעה כפולה/לא קיימת במעבר שעון מוחזרת כשגיאה, לא מנחשים.
- בשעה לא ידועה אין אופק/MC/בתים. המעלות וההיבטים המסומנים 'דגימה' אינם תוצאה מדויקת; אם גוף עשוי להחליף מזל, מוצגות האפשרויות.
- פרטי חישוב אינם נשמרים ואינם נשלחים כלל; שכבת אחסון תתווסף רק אם תהיה דרישה מפורשת.

## מבנה

- src/astrochart/engine.py — מנוע אסטרונומי ללא קריאות רשת
- src/astrochart/timeconv.py — המרות היסטוריות ל-UTC
- src/astrochart/domain.py — מזלות, בתים והיבטים
- src/astrochart/ui.py / wheel.py — ממשק PySide6 וגלגל
- tests/ — בדיקות יחידה ובדיקות אפמריס
- scripts/download_ephemeris.py — הורדה מאומתת בזמן בנייה
- .github/workflows/windows-build.yml — בניית Windows ואימות EXE

## רישיונות והפצה עתידית

Skyfield: MIT. PySide6/Qt Widgets: LGPL-3.0 (או רישיון מסחרי מתאים); בהפצה נדרש לקיים את חובות LGPL, לרבות הודעות רישוי, יכולת להחליף ספריות Qt ומסירת חומר רישוי מתאים. לכן יוצרים onedir ולא קובץ EXE 'onefile' המשלב את כל הספריות. אל תשנו את קובץ JPL DE440s: NASA NAIF מתירה הפצה מחדש של kernels לא-משופרים. קוד האפליקציה טרם קיבל רישיון כלשהו. אין להסיק שההפצה אושרה משפטית ללא בדיקה משלימה של כלל התלויות.

- https://pypi.org/project/skyfield/
- https://pypi.org/project/PySide6/
- https://www.qt.io/development/open-source-lgpl-obligations
- https://naif.jpl.nasa.gov/naif/rules.html
- https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp
- https://rhodesmill.org/skyfield/planets.html

## גבולות גרסה ראשונה

מנוע אפמריס ולא נוסחאות קירוב לפי תאריך; דורש בדיקות השוואה נוספות מול מקורות עצמאיים לפני הגדרת הגרסה כמדויקת לצורכי הפצה. אין פרשנות אסטרולוגית, שמירת מפות או PDF.
