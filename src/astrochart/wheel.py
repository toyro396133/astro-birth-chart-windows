"""Native Qt vector wheel, entirely local and offline.

Exact planetary angles are used for aspect endpoints and anchor dots.
When several bodies are near each other, labels are spread tangentially and
connected to their *true* angles instead of letting the symbols overlap.
"""
import math
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .domain import SIGNS, degree_in_sign, spread_marker_angles

SYMBOLS = {
    "שמש": "☉", "ירח": "☽", "מרקורי": "☿", "ונוס": "♀",
    "מאדים": "♂", "צדק": "♃", "שבתאי": "♄", "אורנוס": "♅",
    "נפטון": "♆", "פלוטו": "♇",
}


def format_body_label(chart, body, digits=2):
    """Shared, certainty-aware text for hover, table and selection labels."""
    degree = f"{degree_in_sign(body.longitude):.{digits}f}°"
    if chart.approximate or chart.time_certainty == "unknown":
        possibilities = (" / ".join(SIGNS[i] for i in body.signs_possible)
                         if body.signs_possible else body.sign)
        kind = "מזלות אפשריים" if body.signs_possible else "מזל בדגימה"
        return (f"{body.name} · {kind}: {possibilities} · "
                f"{degree} (מעלת דגימת אמצע יום, לא מיקום לידה)")
    house = f" · בית {body.house}" if body.house is not None else ""
    if chart.time_certainty == "estimated":
        return (f"{body.name} · {body.sign} · {degree} (לפי שעה משוערת)"
                + (f"{house} (משוער)" if house else ""))
    return f"{body.name} · {body.sign} · {degree}{house}"


def wheel_certainty_note(chart):
    """Certainty disclosure, present in both the interactive wheel and exports."""
    if chart is None:
        return ""
    if chart.approximate or chart.time_certainty == "unknown":
        return ("שעה לא ידועה — מיקומים והיבטים הם דגימת אמצע יום בלבד\n"
                "מעלות אינן מיקומי לידה ודאיים; בתים לא חושבו")
    if chart.time_certainty == "estimated":
        return ("שעה משוערת — מיקומים, בתים והיבטים חושבו לפי שעה משוערת\n"
                "הנתונים עשויים להשתנות אם שעת הלידה שונה")
    return ""


class Wheel(QWidget):
    """Chart labels can be inspected directly; exact coordinates never move."""

    bodySelected = Signal(str)

    def __init__(self):
        super().__init__()
        self.chart = None
        self._symbol_point_size = 16
        self.selected_body = None
        self.selected_aspect_pair = None
        self._hit_targets = {}
        self.setMinimumSize(350, 350)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("גלגל מפה אינטראקטיבי")
        self.setToolTip("לחץ על סמל בגוף במפה כדי לבחור אותו בטבלה")

    def set_symbol_point_size(self, size):
        if size not in (14, 16, 18):
            raise ValueError("גודל סמל גלגל אינו נתמך")
        self._symbol_point_size = size
        self.update()

    def set_chart(self, chart):
        self.chart = chart
        self.selected_body = None
        self.selected_aspect_pair = None
        self._hit_targets = {}
        self.update()

    def set_selected_body(self, name):
        valid = bool(self.chart and any(b.name == name for b in self.chart.bodies))
        selected = name if valid else None
        if self.selected_body != selected or self.selected_aspect_pair is not None:
            self.selected_body = selected
            self.selected_aspect_pair = None
            self.update()

    def set_selected_aspect_pair(self, first, second):
        valid = bool(self.chart and any(
            {aspect.first, aspect.second} == {first, second}
            for aspect in self.chart.aspects))
        pair = frozenset((first, second)) if valid else None
        if self.selected_aspect_pair != pair or self.selected_body is not None:
            self.selected_body = None
            self.selected_aspect_pair = pair
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
            self.setToolTip(format_body_label(self.chart, body))
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
        note = wheel_certainty_note(self.chart)
        # Reserve a bottom footer without covering markers.
        r = max(95.0, min(w, h) * (0.36 if note else 0.438))
        center = QPointF(w / 2, h / 2 - (7 if note else 0))
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
            connected = (
                self.selected_aspect_pair == frozenset((aspect.first, aspect.second))
                if self.selected_aspect_pair is not None
                else self.selected_body in (aspect.first, aspect.second))
            highlighted = self.selected_body is not None or self.selected_aspect_pair is not None
            color.setAlpha(235 if connected else (45 if highlighted else 175))
            p.setPen(QPen(color, 2.6 if connected else 1.1))
            p.drawLine(point(lookup[aspect.first].longitude, r * 0.52),
                       point(lookup[aspect.second].longitude, r * 0.52))

        # The central disk keeps the interior uncluttered when lines converge.
        p.setPen(QPen(QColor("#e0e9f5"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(center, r * 0.07, r * 0.07)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # The anchor dots are exact; only symbol labels may move.
        angles = spread_marker_angles([b.longitude for b in self.chart.bodies], 15)
        p.setFont(QFont("Segoe UI Symbol", self._symbol_point_size))
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

        if note:
            # The disclosure is part of the widget and survives PNG/PDF rendering.
            footer = QRectF(5, h - 54, w - 10, 51)
            p.setPen(QPen(QColor("#d5a45d" if self.chart.approximate
                                  else "#7398cc"), 1))
            p.setBrush(QColor("#fff6e9" if self.chart.approximate else "#f0f6ff"))
            p.drawRoundedRect(footer, 5, 5)
            p.setPen(QColor("#674219" if self.chart.approximate else "#244b79"))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(footer.adjusted(5, 2, -5, -2),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       note)
        p.end()
