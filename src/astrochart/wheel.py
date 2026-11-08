"""Native Qt vector wheel, entirely local and offline.

Exact planetary angles are used for aspect endpoints and anchor dots.
When several bodies are near each other, labels are spread tangentially and
connected to their *true* angles instead of letting the symbols overlap.
"""
import math
from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .domain import SIGNS, degree_in_sign, spread_marker_angles

SYMBOLS = {
    "שמש": "☉", "ירח": "☽", "מרקורי": "☿", "ונוס": "♀",
    "מאדים": "♂", "צדק": "♃", "שבתאי": "♄", "אורנוס": "♅",
    "נפטון": "♆", "פלוטו": "♇",
}


class Wheel(QWidget):
    """Chart labels can be inspected directly; exact coordinates never move."""

    bodySelected = Signal(str)

    def __init__(self):
        super().__init__()
        self.chart = None
        self.selected_body = None
        self._hit_targets = {}
        self.setMinimumSize(350, 350)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("גלגל מפה אינטראקטיבי")
        self.setToolTip("לחץ על סמל בגוף במפה כדי לבחור אותו בטבלה")

    def set_chart(self, chart):
        self.chart = chart
        self.selected_body = None
        self._hit_targets = {}
        self.update()

    def set_selected_body(self, name):
        valid = bool(self.chart and any(b.name == name for b in self.chart.bodies))
        selected = name if valid else None
        if self.selected_body != selected:
            self.selected_body = selected
            self.update()

    def nearest_marker(self, point):
        """Use the actual rendered label positions, not raw longitudes."""
        if not self.chart:
            return None
        closest, distance = None, 21.0
        for name, position in self._hit_targets.items():
            delta = math.hypot(point.x() - position.x(), point.y() - position.y())
            if delta < distance:
                closest, distance = name, delta
        return closest

    def mouseMoveEvent(self, event):
        name = self.nearest_marker(event.position())
        if name:
            body = next(b for b in self.chart.bodies if b.name == name)
            self.setToolTip(
                f"{name} · {body.sign} · {degree_in_sign(body.longitude):.2f}°"
                + (f" · בית {body.house}" if body.house is not None else ""))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("לחץ על סמל במפה כדי לבחור גוף")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            name = self.nearest_marker(event.position())
            if name is not None:
                self.set_selected_body(name)
                self.bodySelected.emit(name)
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        self._hit_targets = {}
        if self.chart is None:
            p.setPen(QColor("#64748b"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "חשב מפה להצגת הגלגל")
            p.end()
            return

        w, h = self.width(), self.height()
        r = max(95.0, min(w, h) * 0.438)
        center = QPointF(w / 2, h / 2)
        origin = self.chart.ascendant if self.chart.ascendant is not None else 0.0

        # Pale dial and precise concentric guides; no photographic assets.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f8fbff"))
        p.drawEllipse(center, r, r)
        p.setBrush(Qt.BrushStyle.NoBrush)

        def point(lon, radius):
            a = math.radians((lon - origin) % 360)
            return QPointF(center.x() - radius * math.cos(a),
                           center.y() + radius * math.sin(a))

        for radius, stroke, width in (
            (r, "#314968", 2.0),
            (r * 0.80, "#829bb9", 1.5),
            (r * 0.57, "#c8d8eb", 1.1),
        ):
            p.setPen(QPen(QColor(stroke), width))
            p.drawEllipse(center, radius, radius)
        p.setFont(QFont("Segoe UI", 10))
        for s in range(12):
            lon = s * 30
            p.setPen(QPen(QColor("#d5e2f1"), 1))
            p.drawLine(point(lon, r * 0.80), point(lon, r))
            pos = point(lon + 15, r * 0.90)
            p.setPen(QColor("#334d6d"))
            p.drawText(int(pos.x() - 28), int(pos.y() - 10), 56, 20,
                       Qt.AlignmentFlag.AlignCenter, SIGNS[s])

        if self.chart.ascendant is not None:
            p.setPen(QPen(QColor("#94b7e0"), 1.1))
            for i in range(12):
                cusp = (int(origin // 30) + i) * 30
                p.drawLine(point(cusp, r * 0.05), point(cusp, r * 0.55))
                pos = point(cusp + 15, r * 0.43)
                p.drawText(int(pos.x() - 12), int(pos.y() - 12), 24, 24,
                           Qt.AlignmentFlag.AlignCenter, str(i + 1))

        lookup = {b.name: b for b in self.chart.bodies}
        for aspect in self.chart.aspects:
            color = QColor({
                "sextile": "#5487d4",
                "trine": "#5487d4",
                "square": "#d39a55",
                "opposition": "#d39a55",
            }.get(aspect.kind_id, "#a7b7c9"))
            connected = self.selected_body in (aspect.first, aspect.second)
            color.setAlpha(220 if connected else (45 if self.selected_body else 175))
            p.setPen(QPen(color, 1.8 if connected else 1.1))
            p.drawLine(point(lookup[aspect.first].longitude, r * 0.52),
                       point(lookup[aspect.second].longitude, r * 0.52))

        # The central disk keeps the interior uncluttered when lines converge.
        p.setPen(QPen(QColor("#e0e9f5"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(center, r * 0.07, r * 0.07)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # The anchor dots are exact; only symbol labels may move.
        angles = spread_marker_angles([b.longitude for b in self.chart.bodies], 15)
        p.setFont(QFont("Segoe UI Symbol", 15))
        planet_colors = {
            "שמש": "#c58538", "ירח": "#5272a6", "מרקורי": "#4d8091",
            "ונוס": "#9d6594", "מאדים": "#b9665e", "צדק": "#567d63",
            "שבתאי": "#7c7790", "אורנוס": "#488e93", "נפטון": "#647cab",
            "פלוטו": "#786e9b",
        }
        for body, label_lon in zip(self.chart.bodies, angles):
            anchor = point(body.longitude, r * 0.585)
            label = point(label_lon, r * 0.70)
            self._hit_targets[body.name] = label
            chosen = body.name == self.selected_body
            p.setPen(QPen(QColor("#4e8fda" if chosen else "#a6bad2"),
                           1.8 if chosen else 1))
            p.drawLine(anchor, label)
            symbol_color = QColor(planet_colors.get(body.name, "#314968"))
            p.setPen(QPen(symbol_color, 1))
            p.setBrush(symbol_color)
            p.drawEllipse(anchor, 2.3, 2.3)
            if chosen:
                p.setPen(QPen(QColor("#2879d4"), 2))
                p.setBrush(QColor("#dfedff"))
                p.drawEllipse(label, 19, 19)
            p.setPen(QPen(QColor("#4289d3" if chosen else "#dbe6f4"),
                          1.4 if chosen else 1.1))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(label, 14.5, 14.5)
            p.setPen(symbol_color)
            p.drawText(int(label.x() - 14), int(label.y() - 14), 28, 28,
                       Qt.AlignmentFlag.AlignCenter, SYMBOLS[body.name])

        if self.chart.approximate:
            p.setFont(QFont("Arial", 9))
            p.setPen(QColor("#b77938"))
            p.drawText(int(center.x() - 110), int(center.y() - 14), 220, 28,
                       Qt.AlignmentFlag.AlignCenter, "שעה לא ידועה — ללא בתים")
        p.end()
