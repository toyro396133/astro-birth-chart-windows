"""Native Qt vector wheel, entirely local and offline.

Exact planetary angles are used for aspect endpoints and anchor dots.
When several bodies are near each other, labels are spread tangentially and
connected to their *true* angles instead of letting the symbols overlap.
"""
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .domain import SIGNS, spread_marker_angles

SYMBOLS = {
    "שמש": "☉", "ירח": "☽", "מרקורי": "☿", "ונוס": "♀",
    "מאדים": "♂", "צדק": "♃", "שבתאי": "♄", "אורנוס": "♅",
    "נפטון": "♆", "פלוטו": "♇",
}


class Wheel(QWidget):
    def __init__(self):
        super().__init__()
        self.chart = None
        self.setMinimumSize(400, 400)

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
            p.end()
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
        for radius in (r, r * 0.80, r * 0.57):
            p.drawEllipse(center, radius, radius)
        p.setFont(QFont("Arial", 10))
        for s in range(12):
            lon = s * 30
            p.setPen(QPen(QColor("#cbd5e1"), 1))
            p.drawLine(point(lon, r * 0.80), point(lon, r))
            pos = point(lon + 15, r * 0.90)
            p.setPen(QColor("#334155"))
            p.drawText(int(pos.x() - 28), int(pos.y() - 10), 56, 20,
                       Qt.AlignmentFlag.AlignCenter, SIGNS[s])

        if self.chart.ascendant is not None:
            p.setPen(QPen(QColor("#2563eb"), 1.1))
            for i in range(12):
                cusp = (int(origin // 30) + i) * 30
                p.drawLine(point(cusp, r * 0.05), point(cusp, r * 0.55))
                pos = point(cusp + 15, r * 0.43)
                p.drawText(int(pos.x() - 12), int(pos.y() - 12), 24, 24,
                           Qt.AlignmentFlag.AlignCenter, str(i + 1))

        lookup = {b.name: b for b in self.chart.bodies}
        p.setPen(QPen(QColor("#d6a34e"), 1.1))
        for aspect in self.chart.aspects:
            p.drawLine(point(lookup[aspect.first].longitude, r * 0.52),
                       point(lookup[aspect.second].longitude, r * 0.52))

        # The anchor dots are exact; only symbol labels may move.
        angles = spread_marker_angles([b.longitude for b in self.chart.bodies], 15)
        p.setFont(QFont("Segoe UI Symbol", 15))
        for body, label_lon in zip(self.chart.bodies, angles):
            anchor = point(body.longitude, r * 0.585)
            label = point(label_lon, r * 0.70)
            p.setPen(QPen(QColor("#94a3b8"), 1))
            p.drawLine(anchor, label)
            p.setPen(QPen(QColor("#334155"), 1))
            p.setBrush(QColor("#334155"))
            p.drawEllipse(anchor, 2.2, 2.2)
            p.setPen(QPen(QColor("#e2e8f0"), 1))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(label, 14, 14)
            p.setPen(QColor("#0f172a"))
            p.drawText(int(label.x() - 14), int(label.y() - 14), 28, 28,
                       Qt.AlignmentFlag.AlignCenter, SYMBOLS[body.name])

        if self.chart.approximate:
            p.setFont(QFont("Arial", 9))
            p.setPen(QColor("#b45309"))
            p.drawText(int(center.x() - 110), int(center.y() - 14), 220, 28,
                       Qt.AlignmentFlag.AlignCenter, "שעה לא ידועה — ללא בתים")
        p.end()
