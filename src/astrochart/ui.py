from datetime import date, time
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QTimeEdit,
    QVBoxLayout, QWidget,
)
from .domain import SIGNS, degree_in_sign
from .engine import Calculator
from .locations import CITIES
from .wheel import Wheel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("מפת לידה — חישוב מקומי")
        self.resize(1160, 780)
        self.calc = None
        self._build()

    def _build(self):
        root = QWidget()
        root.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        intro = QLabel("מפת לידה אסטרונומית | טרופי | Whole Sign | ללא אינטרנט")
        intro.setStyleSheet("font-size: 19px; font-weight: bold; color: #1e3a5f;")
        main.addWidget(intro)

        form_box = QGroupBox("נתוני חישוב")
        form = QFormLayout(form_box)
        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd.MM.yyyy")
        self.day.setDate(QDate.currentDate())
        self.day.setMinimumDate(QDate(1850, 1, 1))
        self.day.setMaximumDate(QDate(2149, 12, 31))
        form.addRow("תאריך:", self.day)
        self.hour = QTimeEdit()
        self.hour.setDisplayFormat("HH:mm")
        self.hour.setTime(QTime(12, 0))
        form.addRow("שעת לידה:", self.hour)
        self.unknown = QCheckBox("שעת הלידה אינה ידועה")
        self.unknown.toggled.connect(lambda checked: self.hour.setEnabled(not checked))
        form.addRow("", self.unknown)
        self.city = QComboBox()
        self.city.addItems(["הזנה ידנית", *CITIES])
        self.city.setCurrentText("ירושלים")
        self.city.currentTextChanged.connect(self._city_changed)
        form.addRow("מקום:", self.city)
        self.lat = QDoubleSpinBox()
        self.lat.setRange(-89.99, 89.99)
        self.lat.setDecimals(5)
        self.lon = QDoubleSpinBox()
        self.lon.setRange(-180, 180)
        self.lon.setDecimals(5)
        self.tz = QLineEdit()
        form.addRow("קו רוחב (+צפון):", self.lat)
        form.addRow("קו אורך (+מזרח):", self.lon)
        form.addRow("אזור זמן IANA:", self.tz)
        self._city_changed(self.city.currentText())
        self.run = QPushButton("חשב מפת לידה")
        self.run.setStyleSheet("font-size: 16px; padding: 10px; background: #2563eb; color: white;")
        self.run.clicked.connect(self._calculate)
        form.addRow("", self.run)
        main.addWidget(form_box)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.wheel = Wheel()
        split.addWidget(self.wheel)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["גוף", "מזל", "מעלה במזל", "בית", "תנועה"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.table)
        right_layout.addWidget(QLabel("היבטים"))
        self.aspects = QTextEdit()
        self.aspects.setReadOnly(True)
        self.aspects.setMaximumHeight(145)
        right_layout.addWidget(self.aspects)
        self.warnings = QLabel("")
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet("color: #9a3412;")
        right_layout.addWidget(self.warnings)
        split.addWidget(right)
        split.setSizes([500, 580])
        main.addWidget(split, 1)

    def _city_changed(self, city):
        if city in CITIES:
            lat, lon, tz = CITIES[city]
            self.lat.setValue(lat)
            self.lon.setValue(lon)
            self.tz.setText(tz)

    def _calculate(self):
        try:
            if self.calc is None:
                self.calc = Calculator()
            d = self.day.date()
            t = self.hour.time()
            day = date(d.year(), d.month(), d.day())
            hour = time(t.hour(), t.minute())
            chart = self.calc.calculate(
                day, hour, self.tz.text().strip(),
                self.lat.value(), self.lon.value(), self.unknown.isChecked())
            self._show_chart(chart)
        except Exception as exc:
            QMessageBox.warning(self, "לא ניתן לחשב", str(exc))

    def _show_chart(self, chart):
        self.table.setRowCount(len(chart.bodies))
        for row, b in enumerate(chart.bodies):
            signs = " / ".join(SIGNS[i] for i in b.signs_possible) if chart.approximate else b.sign
            motion = "לא ודאי" if b.motion_uncertain else ("נסיגה" if b.retrograde else "ישירה")
            values = [
                b.name, signs,
                f"{degree_in_sign(b.longitude):.3f}°" + (" (דגימה)" if chart.approximate else ""),
                "—" if b.house is None else str(b.house), motion
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self.aspects.setPlainText("\n".join(
            f"{a.first} – {a.second}: {a.kind}, מרחק {a.separation:.2f}°, סטייה {a.orb:.2f}°"
            for a in chart.aspects))
        angles = "" if chart.ascendant is None else (
            f"\nאופק: {chart.ascendant:.3f}° | MC: {chart.mc:.3f}°"
            f" | ציר נגדי: {chart.descendant:.3f}°")
        self.warnings.setText("\n".join(chart.warnings) + angles)
        self.wheel.set_chart(chart)
