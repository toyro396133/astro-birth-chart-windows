"""Offline chart aspect explorer. Uses computed facts, never inferred traits."""
import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)


def filter_aspects(chart, body=None, kind_id=None):
    if chart is None:
        return []
    selected = []
    for aspect in chart.aspects:
        if body and body not in (aspect.first, aspect.second):
            continue
        if kind_id and aspect.kind_id != kind_id:
            continue
        if not math.isfinite(aspect.orb) or aspect.orb < 0:
            continue
        selected.append(aspect)
    return sorted(selected, key=lambda aspect: (aspect.orb, aspect.first, aspect.second))


def certainty_label(chart, aspect):
    if chart.approximate:
        return "דגימת שעה בלבד"
    if chart.time_certainty == "estimated" or aspect.certainty == "estimated":
        return "לפי שעה משוערת"
    return "מחושב"


class AspectExplorerDialog(QDialog):
    """Nonmodal; selecting an aspect highlights the matching wheel line."""

    aspectSelected = Signal(str, str)

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        if chart is None:
            raise ValueError("יש לחשב מפה לפני חקירת היבטים")
        self.chart = chart
        self._visible_aspects = []
        self.setWindowTitle("חקירת היבטים — מיקומים מחושבים")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(780, 480)
        self.setMinimumWidth(620)

        root = QVBoxLayout(self)
        notice = QLabel(
            "מיון לפי סטייה (Orb) · בחירת שורה מדגישה את ההיבט בגלגל המפה. "
            "כאשר השעה אינה ידועה, ההיבטים הם דגימות בלבד.")
        notice.setWordWrap(True)
        root.addWidget(notice)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("גוף:"))
        self.body_filter = QComboBox()
        self.body_filter.addItem("כל הגופים", None)
        for name in dict.fromkeys(body.name for body in chart.bodies):
            self.body_filter.addItem(name, name)
        filters.addWidget(self.body_filter)
        filters.addWidget(QLabel("סוג היבט:"))
        self.kind_filter = QComboBox()
        self.kind_filter.addItem("כל ההיבטים", None)
        seen = set()
        for aspect in chart.aspects:
            if aspect.kind_id not in seen:
                seen.add(aspect.kind_id)
                self.kind_filter.addItem(aspect.kind, aspect.kind_id)
        filters.addWidget(self.kind_filter)
        root.addLayout(filters)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["גוף ראשון", "גוף שני", "היבט", "זווית", "Orb", "ודאות"])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._select_aspect)
        root.addWidget(self.table)
        self.body_filter.currentIndexChanged.connect(self._populate)
        self.kind_filter.currentIndexChanged.connect(self._populate)
        self._populate()

    def _populate(self, *args):
        selected = filter_aspects(
            self.chart, self.body_filter.currentData(), self.kind_filter.currentData())
        self._visible_aspects = selected
        self.table.blockSignals(True)
        self.table.setRowCount(len(selected))
        for row, aspect in enumerate(selected):
            values = [
                aspect.first, aspect.second, aspect.kind,
                f"{aspect.separation:.2f}°", f"{aspect.orb:.2f}°",
                certainty_label(self.chart, aspect),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.clearSelection()
        self.table.blockSignals(False)

    def _select_aspect(self):
        # A selected row does not always become the Qt current index.
        selection = self.table.selectionModel().selectedRows()
        row = selection[0].row() if selection else self.table.currentRow()
        if not 0 <= row < len(self._visible_aspects):
            return
        aspect = self._visible_aspects[row]
        self.aspectSelected.emit(aspect.first, aspect.second)
