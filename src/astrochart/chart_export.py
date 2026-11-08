"""Qt-native local visual exports. No PDF dependency or network service."""
from PySide6.QtCore import QRectF, Qt
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
        wheel.render(painter)
    finally:
        painter.end()
    if not image.save(str(destination), "PNG"):
        raise OSError("שמירת תמונת PNG נכשלה")


def export_chart_pdf(wheel, chart, destination):
    """Vector page with wheel and text report, overflowing onto extra pages."""
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
                         Qt.AlignmentFlag.AlignRight, "AstroBirthChart — דוח מפה")
        if wheel.width() > 0 and wheel.height() > 0:
            max_width = page_w - 2 * margin
            max_height = page_h * 0.45
            scale = min(max_width / wheel.width(), max_height / wheel.height())
            painter.save()
            painter.translate((page_w - wheel.width() * scale) / 2, 90)
            painter.scale(scale, scale)
            wheel.render(painter)
            painter.restore()
            line_y = 90 + wheel.height() * scale + 22
        else:
            line_y = 100
        painter.setFont(QFont("Segoe UI", 9))
        for text in format_chart_report(chart).splitlines():
            if line_y > page_h - margin:
                writer.newPage()
                line_y = margin
            painter.drawText(QRectF(margin, line_y, page_w - 2 * margin, 23),
                             Qt.AlignmentFlag.AlignRight | Qt.TextFlag.TextWordWrap,
                             text)
            line_y += 23
    finally:
        painter.end()
