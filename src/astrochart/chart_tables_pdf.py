"""Local print-ready PDF containing the signs/positions and aspects tables only.

No chart wheel, narrative report or interpretation is drawn. All values are
derived from the same Chart domain data used in the application's right panel.
"""
from PySide6.QtCore import QRect, QRectF, Qt
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



# Palette: restrained professional report, friendly to office printers.
NAVY = QColor("#17314c")
INK = QColor("#26374a")
MUTED = QColor("#62768b")
TEAL = QColor("#168e91")
PAPER = QColor("#ffffff")
PALE = QColor("#f2f6fa")
LINE = QColor("#e0e8ef")
AMBER = QColor("#fff4dc")
AMBER_INK = QColor("#805a23")
SECTION_ACCENTS = (QColor("#168e91"), QColor("#4d7bbb"))


def _font(size, bold=False):
    font = QFont("Segoe UI")
    font.setPointSizeF(float(size))
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def _text(painter, rect, text, size=9, bold=False, color=None,
          alignment=None, wrap=False):
    """Text is rendered as local vector glyphs; wrap and RTL align by Qt."""
    painter.save()
    painter.setFont(_font(size, bold))
    painter.setPen(color or INK)
    flags = (alignment if alignment is not None else
             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if wrap:
        flags |= Qt.TextFlag.TextWordWrap
    painter.drawText(QRectF(rect), flags, str(text))
    painter.restore()


def _status_note(chart):
    if chart.time_certainty == "unknown":
        return ("דיוק הנתונים", "שעת הלידה אינה ידועה. המעלות וההיבטים מבוססים על דגימה "
                "ואינם מוצגים כנתוני לידה מדויקים.")
    if chart.time_certainty == "estimated":
        return ("דיוק הנתונים", "שעת הלידה משוערת. המיקומים, הבתים וההיבטים תלויים "
                "בשעה שנבחרה לחישוב.")
    return None


def _header_details(metadata):
    """Display real inputs only; never invent a person's name or an absent value."""
    if not isinstance(metadata, dict):
        return []
    from datetime import date
    raw_date = metadata.get("civil_date")
    try:
        pretty_date = date.fromisoformat(raw_date).strftime("%d.%m.%Y")
    except (TypeError, ValueError, AttributeError):
        pretty_date = None
    city = metadata.get("city")
    city = city.strip()[:80] if isinstance(city, str) and city.strip() else None
    clock = metadata.get("clock")
    clock = clock if isinstance(clock, str) and len(clock) == 5 and (
        clock[:2].isdigit() and clock[2] == ":" and clock[3:].isdigit()) else None
    clock = "לא ידועה" if metadata.get("unknown_time") is True else clock
    if metadata.get("estimated_time") is True and clock:
        clock += " (משוערת)"
    return [(label, value) for label, value in
            (("תאריך", pretty_date), ("מקום", city), ("שעה", clock)) if value]


def _row_height(painter, values, fractions, full_width):
    """Measure wrapped text before assigning a printable row to a page."""
    painter.save()
    painter.setFont(_font(9.0))
    flags = (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter |
             Qt.TextFlag.TextWordWrap)
    heights = []
    for content, width in zip(values, fractions):
        inner = max(36, int(full_width * width) - 27)
        rect = painter.fontMetrics().boundingRect(
            QRect(0, 0, inner, 4000), flags, str(content))
        heights.append(rect.height())
    painter.restore()
    return max(54, max(heights, default=0) + 23)


def _plan_pages(sections, painter, page_width, page_height, top_first, top_next):
    """Page breaks before rows, with repeated section/header and no clipping."""
    available_bottom = page_height - 106
    table_width = page_width - 156
    pages = [[]]
    y = top_first

    def new_page():
        nonlocal y
        pages.append([])
        y = top_next

    for section_idx, (title, headers, rows, widths) in enumerate(sections):
        data = list(rows) or [["לא נמצאו נתונים"] + [""] * (len(headers) - 1)]
        row_heights = [_row_height(painter, row, widths, table_width) for row in data]
        if y + 59 + 47 + row_heights[0] > available_bottom:
            new_page()

        def start_section(continued=False):
            nonlocal y
            pages[-1].append(("title", section_idx, title, len(rows), continued, y, 59))
            y += 59
            pages[-1].append(("head", section_idx, headers, widths, y, 47))
            y += 47

        start_section()
        for idx, (row, height) in enumerate(zip(data, row_heights)):
            if height > available_bottom - top_next - 106:
                raise ValueError("שורת טבלה ארוכה מדי עבור עמוד A4")
            if y + height > available_bottom:
                new_page()
                start_section(continued=True)
            pages[-1].append(("row", section_idx, row, widths, y, height, idx))
            y += height
        y += 34
    return pages


def _draw_cover_header(painter, page_width, metadata, caution):
    margin = 78
    content_width = page_width - 2 * margin
    painter.fillRect(QRectF(0, 0, page_width, 154), NAVY)
    painter.fillRect(QRectF(0, 154, page_width, 6), TEAL)
    _text(painter, QRectF(margin, 17, content_width, 25),
          "ASTROBIRTHCHART", size=8.3, color=QColor("#b4c9d9"),
          alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    _text(painter, QRectF(margin, 47, content_width, 59),
          "מפת לידה | טבלאות מיקומים והיבטים", 19.0, True, PAPER)
    _text(painter, QRectF(margin, 109, content_width, 29),
          "נתוני החישוב • ללא גלגל וללא פרשנות", 9.3,
          color=QColor("#c7d6e3"))

    y = 186
    if metadata:
        gap = 12
        width = (content_width - gap * (len(metadata) - 1)) / len(metadata)
        x = page_width - margin
        for label, value in metadata:
            x -= width
            r = QRectF(x, y, width, 74)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(PALE)
            painter.drawRoundedRect(r, 9, 9)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            _text(painter, QRectF(x + 15, y + 6, width - 30, 25),
                  label, size=8.2, color=MUTED)
            # No spillover for long city names or approximate-hour values.
            painter.save()
            painter.setFont(_font(10.4, True))
            shown = painter.fontMetrics().elidedText(str(value),
                Qt.TextElideMode.ElideLeft, max(35, int(width - 30)))
            painter.restore()
            _text(painter, QRectF(x + 15, y + 29, width - 30, 34),
                  shown, size=10.4, bold=True)
            x -= gap
        y = 282
    else:
        y = 195

    if caution:
        note_title, note_body = caution
        r = QRectF(margin, y, content_width, 78)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(AMBER)
        painter.drawRoundedRect(r, 9, 9)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.fillRect(QRectF(page_width - margin - 5, y + 10, 4, 58),
                         QColor("#d4a650"))
        _text(painter, QRectF(margin + 16, y + 7, content_width - 37, 23),
              note_title, size=9.4, bold=True, color=AMBER_INK)
        _text(painter, QRectF(margin + 16, y + 28, content_width - 37, 43),
              note_body, size=8.7, color=AMBER_INK, wrap=True)
        y += 101
    return y + 20


def _draw_continuation_header(painter, page_width):
    margin = 78
    content = page_width - 2 * margin
    painter.fillRect(QRectF(0, 0, page_width, 96), NAVY)
    painter.fillRect(QRectF(0, 96, page_width, 4), TEAL)
    _text(painter, QRectF(margin, 26, content, 48),
          "מפת לידה — המשך הטבלאות", 14.5, bold=True, color=PAPER)
    return 135


def _draw_section_title(painter, page_width, section_idx, name, count, continued, y):
    margin = 78
    table_width = page_width - 2 * margin
    accent = SECTION_ACCENTS[section_idx % len(SECTION_ACCENTS)]
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(accent)
    painter.drawRoundedRect(QRectF(page_width - margin - 6, y + 10, 6, 34), 3, 3)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    name = name + (" — המשך" if continued else "")
    _text(painter, QRectF(margin + 13, y + 2, table_width - 36, 48),
          name, size=13.0, bold=True, color=NAVY)
    if not continued:
        _text(painter, QRectF(margin + 7, y + 11, 148, 30),
              f"{count} רשומות", size=8.2, color=MUTED,
              alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def _draw_table_row(painter, page_width, values, fractions, y, height,
                    heading=False, index=0, section_idx=0):
    margin = 78
    table_width = page_width - 2 * margin
    bg = NAVY if heading else PAPER if index % 2 == 0 else PALE
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(bg)
    outer = QRectF(margin, y, table_width, height)
    if heading:
        painter.drawRoundedRect(outer, 7, 7)
    else:
        painter.drawRect(outer)
        painter.setPen(QPen(LINE, 0.8))
        painter.drawLine(margin, int(y + height), page_width - margin, int(y + height))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    x = page_width - margin
    for col, (value, fraction) in enumerate(zip(values, fractions)):
        width = table_width * fraction
        x -= width
        # Small emphasis marker for the two most recognizable bodies.
        if not heading and section_idx == 0 and col == 0 and value in ("שמש", "ירח"):
            color = QColor("#d4a14a") if value == "שמש" else QColor("#6987b3")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(x + 9, y + height / 2 - 4, 8, 8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        _text(painter, QRectF(x + 13, y + 5, width - 26, height - 10),
              value, size=8.7 if heading else 9.0, bold=heading or (
                  section_idx == 0 and col == 0),
              color=PAPER if heading else INK,
              wrap=True)


def _draw_footer(painter, page_width, page_height, page_number, page_count):
    from datetime import date
    margin = 78
    y = page_height - 73
    painter.setPen(QPen(LINE, 1.1))
    painter.drawLine(margin, int(y), page_width - margin, int(y))
    _text(painter, QRectF(margin, y + 14, 320, 30),
          "ASTROBIRTHCHART  •  " + date.today().strftime("%d.%m.%Y"),
          size=8.0, color=MUTED,
          alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    _text(painter, QRectF(page_width - margin - 230, y + 14, 230, 30),
          f"עמוד {page_number} מתוך {page_count}", size=8.3,
          color=MUTED)


def export_chart_tables_pdf(chart, destination, metadata=None):
    """Print-quality A4 RTL tables, branded header, source metadata and page footer.

    Purely local. No wheel, interpretation, predictions or external assets.
    """
    sections = chart_table_sections(chart)
    details = _header_details(metadata)
    caution = _status_note(chart)
    writer = QPdfWriter(str(destination))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    writer.setTitle("AstroBirthChart — טבלת מזלות והיבטים")
    writer.setCreator("AstroBirthChart")
    painter = QPainter(writer)
    if not painter.isActive():
        raise OSError("יצירת מסמך PDF נכשלה")
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        page_width, page_height = writer.width(), writer.height()
        # Same first-page offsets as the header drawing, without writing while
        # measuring. This ensures page numbers can show a true total.
        start_y = (282 if details else 195) + (101 if caution else 0) + 20
        pages = _plan_pages(sections, painter, page_width, page_height,
                            start_y, 135)
        for page_index, commands in enumerate(pages):
            if page_index:
                writer.newPage()
                _draw_continuation_header(painter, page_width)
            else:
                _draw_cover_header(painter, page_width, details, caution)
            for cmd in commands:
                if cmd[0] == "title":
                    _, section_idx, title, count, continued, y, _ = cmd
                    _draw_section_title(painter, page_width, section_idx,
                                        title, count, continued, y)
                elif cmd[0] == "head":
                    _, section_idx, values, fractions, y, height = cmd
                    _draw_table_row(painter, page_width, values, fractions,
                                    y, height, heading=True, section_idx=section_idx)
                else:
                    _, section_idx, values, fractions, y, height, row_index = cmd
                    _draw_table_row(painter, page_width, values, fractions,
                                    y, height, index=row_index,
                                    section_idx=section_idx)
            _draw_footer(painter, page_width, page_height,
                         page_index + 1, len(pages))
    finally:
        painter.end()
