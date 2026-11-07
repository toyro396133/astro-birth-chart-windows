"""Native Qt vector wheel, entirely local and offline."""
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .domain import SIGNS

SYMBOLS = {
    "שמש": "☉", "ירח": "☽", "מרקורי": "☿", "ונוס": "♀",
    "מאדים": "♂", "צדק": "♃", "שבתאי": "♄", "אורנוס": "♅",
    "נפטון": "♆", "פלוטו": "♇",
}


class Wheel(QWidget):
    def __init__(self):
        super().__init__()
        self.chart = None
        self.setMinimumSize(450, 450)

    def set_chart(self, chart):
        self.chart = chart
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if self.chart is None:
            p.setPen(QColor("#64748b"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "חשב מפה להצגת הגלגל")
            return
        w, h = self.width(), self.height()
        r = max(100.0, min(w, h) * 0.43)
        center = QPointF(w / 2, h / 2)
        origin = self.chart.ascendant if self.chart.ascendant is not None else 0.0

        def point(lon, radius):
            a = math.radians((lon - origin) % 360)
            return QPointF(center.x() - radius * math.cos(a),
                           center.y() + radius * math.sin(a))

        p.setPen(QPen(QColor("#334155"), 2))
        for radius in (r, r * 0.73, r * 0.56):
            p.drawEllipse(center, radius, radius)
        p.setFont(QFont("Arial", 10))
        for s in range(12):
            lon = s * 30
            p.setPen(QPen(QColor("#cbd5e1"), 1))
            p.drawLine(point(lon, r * 0.73), point(lon, r))
            pos = point(lon + 15, r * 0.86)
            p.setPen(QColor("#334155"))
            p.drawText(int(pos.x() - 28), int(pos.y() - 10), 56, 20,
                       Qt.AlignmentFlag.AlignCenter, SIGNS[s])
        if self.chart.ascendant is not None:
            p.setPen(QPen(QColor("#2563eb"), 1.2))
            for i in range(12):
                cusp = (int(origin // 30) + i) * 30
                p.drawLine(point(cusp, r * 0.05), point(cusp, r * 0.56))
                pos = point(cusp + 15, r * 0.43)
                p.drawText(int(pos.x() - 12), int(pos.y() - 12), 24, 24,
                           Qt.AlignmentFlag.AlignCenter, str(i + 1))
        lookup = {b.name: b for b in self.chart.bodies}
        p.setPen(QPen(QColor("#d6a34e"), 1.1))
        for aspect in self.chart.aspects:
            p.drawLine(point(lookup[aspect.first].longitude, r * 0.54),
                       point(lookup[aspect.second].longitude, r * 0.54))
        p.setFont(QFont("Segoe UI Symbol", 15))
        p.setPen(QColor("#0f172a"))
        for body in self.chart.bodies:
            pos = point(body.longitude, r * 0.64)
            p.drawText(int(pos.x() - 14), int(pos.y() - 14), 28, 28,
                       Qt.AlignmentFlag.AlignCenter, SYMBOLS[body.name])
        if self.chart.approximate:
            p.setFont(QFont("Arial", 9))
            p.setPen(QColor("#b45309"))
            p.drawText(int(center.x() - 110), int(center.y() - 14), 220, 28,
                       Qt.AlignmentFlag.AlignCenter, "שעה לא ידועה — ללא בתים")
        p.end()
