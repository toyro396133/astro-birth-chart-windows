"""Qt-native local visual exports. No PDF dependency or network service."""
import math
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPdfWriter, QPixmap, QPageSize


def export_wheel_png(wheel, destination, scale=3):
    if wheel.chart is None:
        raise ValueError("אין מפה מחושבת לייצוא")
    if not 1 <= scale <= 4:
        raise ValueError("מקדם הגדלה לא נתמך")
    image = QPixmap(wheel.width() * scale, wheel.height() * scale)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)
        wheel.render(painter, QPoint(0, 0))
    finally:
        painter.end()
    if not image.save(str(destination), "PNG"):
        raise OSError("שמירת תמונת PNG נכשלה")


def _wrapped_pdf_line_height(painter, width, text):
    """Measure wrapped text in PDF painter coordinates before placing it."""
    flags = (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
             | Qt.TextFlag.TextWordWrap)
    measured = painter.boundingRect(QRectF(0, 0, width, 20000), flags, text or " ")
    return max(23, math.ceil(measured.height()) + 6)


def export_chart_pdf(wheel, chart, destination, include_report=True):
    """Vector wheel, optionally followed by text. No interpretation is included."""
    from .report import format_chart_report
    if chart is None or wheel.chart is None:
        raise ValueError("אין מפה מחושבת לייצוא")
    writer = QPdfWriter(str(destination))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    painter = QPainter(writer)
    if not painter.isActive():
        raise OSError("יצירת מסמך PDF נכשלה")
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        page_w, page_h = writer.width(), writer.height()
        margin = 70
        painter.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        painter.drawText(QRectF(margin, 35, page_w - 2 * margin, 42),
                         Qt.AlignmentFlag.AlignRight, "AstroBirthChart — דוח מפה" if include_report else "AstroBirthChart — מפה בלבד")
        if wheel.width() > 0 and wheel.height() > 0:
            max_width = page_w - 2 * margin
            max_height = page_h * 0.45
            scale = min(max_width / wheel.width(), max_height / wheel.height())
            painter.save()
            painter.translate((page_w - wheel.width() * scale) / 2, 90)
            painter.scale(scale, scale)
            wheel.render(painter, QPoint(0, 0))
            painter.restore()
            line_y = 90 + wheel.height() * scale + 22
        else:
            line_y = 100
        if not include_report:
            return
        painter.setFont(QFont("Segoe UI", 9))
        text_width = page_w - 2 * margin
        flags = (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
                 | Qt.TextFlag.TextWordWrap)
        for text in format_chart_report(chart).splitlines():
            if not text:
                line_y += 12
                continue
            height = _wrapped_pdf_line_height(painter, text_width, text)
            if line_y + height > page_h - margin:
                writer.newPage()
                line_y = margin
            painter.drawText(QRectF(margin, line_y, text_width, height),
                             flags, text)
            line_y += height
    finally:
        painter.end()
