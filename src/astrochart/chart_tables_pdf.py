"""Local print-ready PDF containing the signs/positions and aspects tables only.

No chart wheel, narrative report or interpretation is drawn. All values are
derived from the same Chart domain data used in the application's right panel.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPageSize, QPdfWriter, QColor, QPen

from .domain import SIGNS, degree_in_sign


def chart_table_sections(chart):
    """Pure, testable, RTL table data; preserve all uncertainty markers."""
    if chart is None:
        raise ValueError("יש לחשב מפה לפני ייצוא")
    positions = []
    for body in chart.bodies:
        sign = (" / ".join(SIGNS[i] for i in body.signs_possible)
                if chart.approximate and body.signs_possible else body.sign)
        degree = f"{degree_in_sign(body.longitude):.3f}°"
        if chart.time_certainty == "unknown":
            degree += " (דגימה)"
        elif body.degree_certainty == "estimated" or chart.time_certainty == "estimated":
            degree += " (משוער)"
        house = "—" if body.house is None else str(body.house)
        if body.house is not None and chart.time_certainty == "estimated":
            house += " (משוער)"
        motion = ("לא ודאי" if body.motion_uncertain else
                  "נסיגה" if body.retrograde else "ישירה")
        positions.append([body.name, sign, degree, house, motion])
    aspects = []
    for aspect in chart.aspects:
        status = ("דגימה בלבד" if chart.time_certainty == "unknown" else
                  "משוער" if aspect.certainty == "estimated" or
                  chart.time_certainty == "estimated" else "מחושב")
        aspects.append([aspect.first, aspect.second, aspect.kind,
                        f"{aspect.separation:.2f}°", f"{aspect.orb:.2f}°", status])
    return [
        ("מיקומי הגופים במזלות",
         ["גוף", "מזל", "מעלה במזל", "בית", "תנועה"], positions,
         [0.16, 0.25, 0.23, 0.15, 0.21]),
        ("היבטים בין הגופים",
         ["גוף ראשון", "גוף שני", "היבט", "מרחק", "סטייה", "דיוק"], aspects,
         [0.18, 0.18, 0.18, 0.14, 0.13, 0.19]),
    ]


def export_chart_tables_pdf(chart, destination):
    """A4 multi-page vector PDF; no wheel dependency or interpretative text."""
    sections = chart_table_sections(chart)
    writer = QPdfWriter(str(destination))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    writer.setTitle("AstroBirthChart — טבלת מזלות והיבטים")
    painter = QPainter(writer)
    if not painter.isActive():
        raise OSError("יצירת מסמך PDF נכשלה")
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        page_width, page_height = writer.width(), writer.height()
        margin, header_height, row_height = 65, 48, 54
        table_width = page_width - 2 * margin
        y = 92

        def set_font(size, bold=False):
            painter.setFont(QFont("Segoe UI", size,
                                  QFont.Weight.Bold if bold else QFont.Weight.Normal))

        def new_page():
            nonlocal y
            writer.newPage()
            y = 88

        def draw_cell(rect, value, bold=False, background=None):
            painter.save()
            if background is not None:
                painter.fillRect(rect, QColor(background))
            painter.setPen(QPen(QColor("#bac6d3"), 0.8))
            painter.drawRect(rect)
            painter.setPen(QColor("#192b3d"))
            set_font(8 if not bold else 9, bold)
            inner = rect.adjusted(9, 3, -9, -3)
            painter.drawText(inner, Qt.AlignmentFlag.AlignRight |
                             Qt.AlignmentFlag.AlignVCenter |
                             Qt.TextFlag.TextWordWrap, str(value))
            painter.restore()

        def draw_table_row(values, widths, height, heading=False, row_number=0):
            nonlocal y
            x = page_width - margin
            for value, fraction in zip(values, widths):
                width = table_width * fraction
                x -= width
                draw_cell(QRectF(x, y, width, height), value,
                          bold=heading,
                          background="#e5eef7" if heading else
                          "#f4f8fc" if row_number % 2 else "#ffffff")
            y += height

        set_font(18, True)
        painter.setPen(QColor("#102a47"))
        painter.drawText(QRectF(margin, 26, table_width, 58),
                         Qt.AlignmentFlag.AlignRight,
                         "מפת לידה — טבלת מזלות והיבטים")
        set_font(9)
        painter.drawText(QRectF(margin, 87, table_width, 32),
                         Qt.AlignmentFlag.AlignRight,
                         "נתוני חישוב בלבד • ללא גלגל וללא פרשנות")
        y = 142

        for title, headings, rows, widths in sections:
            if y + 120 > page_height - margin:
                new_page()
            set_font(13, True)
            painter.setPen(QColor("#102a47"))
            painter.drawText(QRectF(margin, y, table_width, 38),
                             Qt.AlignmentFlag.AlignRight, title)
            y += 43
            draw_table_row(headings, widths, header_height, heading=True)
            if not rows:
                draw_table_row(["לא נמצאו נתונים"] + [""] * (len(widths) - 1),
                               widths, row_height)
            for index, row in enumerate(rows):
                if y + row_height > page_height - margin:
                    new_page()
                    # Keep column labels visible on every subsequent page.
                    set_font(11, True)
                    painter.drawText(QRectF(margin, y, table_width, 34),
                                     Qt.AlignmentFlag.AlignRight, title + " — המשך")
                    y += 39
                    draw_table_row(headings, widths, header_height, heading=True)
                draw_table_row(row, widths, row_height, row_number=index)
            y += 32

        if chart.time_certainty in ("unknown", "estimated"):
            if y + 85 > page_height - margin:
                new_page()
            set_font(9, True)
            painter.setPen(QColor("#102a47"))
            note = ("שעה לא ידועה: המעלות וההיבטים משקפים דגימה ואינם "
                    "נתוני לידה מדויקים."
                    if chart.time_certainty == "unknown" else
                    "שעה משוערת: המיקומים, הבתים וההיבטים תלויים בשעה שנבחרה.")
            painter.drawText(QRectF(margin, y, table_width, 80),
                             Qt.AlignmentFlag.AlignRight |
                             Qt.TextFlag.TextWordWrap, note)
    finally:
        painter.end()
