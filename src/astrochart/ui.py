from datetime import date, time
from PySide6.QtCore import QDate, Qt, QTime, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QGridLayout, QGroupBox,
    QHeaderView, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QTimeEdit, QVBoxLayout, QWidget,
)
from .domain import SIGNS, degree_in_sign
from .engine import Calculator
from .hebrew_dates import (months_of_year, days_of_month, from_gregorian,
                           resolve_hebrew_date, sun_altitude, validate_phase_sun)
from .locations import CITIES
from . import __version__
from .updater import (UpdateError, latest_release, is_newer, download_release,
                      extract_release, install_directory, launch_install, launch_setup_install,
                      is_installed_setup, SETUP_ASSET, ASSET,
                      auto_updates_enabled, save_auto_updates)
from .wheel import Wheel



class UpdateCheckThread(QThread):
    result = Signal(object)
    error = Signal(str)

    def run(self):
        import tempfile
        from pathlib import Path
        try:
            installed = install_directory()
            is_setup = is_installed_setup(installed)
            latest = latest_release(SETUP_ASSET if is_setup else ASSET)
            if latest is None or not is_newer(latest.version, __version__):
                self.result.emit(None)
                return
            if is_setup:
                # Retain a verified installer until the external worker
                # takes over after the GUI has fully exited.
                folder = Path(tempfile.mkdtemp(prefix="AstroChart-Setup-"))
                setup = folder / SETUP_ASSET
                try:
                    download_release(latest, setup)
                except BaseException:
                    import shutil
                    shutil.rmtree(folder, ignore_errors=True)
                    raise
                self.result.emit((latest.version, setup, "setup", latest.digest))
            else:
                with tempfile.TemporaryDirectory(prefix="AstroChart-Download-") as temp:
                    zip_path = Path(temp) / "update.zip"
                    download_release(latest, zip_path)
                    stage = extract_release(zip_path, installed, latest.version)
                self.result.emit((latest.version, stage, "portable", None))
        except Exception as exc:
            self.error.emit(str(exc))



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("מפת לידה — חישוב מקומי")
        self.resize(1160, 780)
        self.calc = None
        self._updating = False
        self._update_thread = None
        self._build()
        QTimer.singleShot(1000, self._automatic_update_check)

    def _build(self):
        root = QWidget()
        root.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        intro = QLabel("מפת לידה אסטרונומית | טרופי | Whole Sign | חישוב מקומי")
        intro.setStyleSheet("font-size: 19px; font-weight: bold; color: #1e3a5f;")
        heading = QHBoxLayout()
        heading.setSpacing(6)
        heading.addWidget(intro, 1)
        heading.addWidget(QLabel("v" + __version__))
        self.auto_update = QCheckBox("עדכונים אוטומטיים")
        self.auto_update.setToolTip(
            "במצב פעיל התוכנה בודקת GitHub בעת פתיחתה. "
            "קובצי המפה ונתוני הלידה אינם נשלחים.")
        self.auto_update.setChecked(auto_updates_enabled())
        self.auto_update.toggled.connect(self._toggle_auto_update)
        heading.addWidget(self.auto_update)
        self.update_button = QPushButton("בדוק עדכונים")
        self.update_button.clicked.connect(self._manual_update_check)
        heading.addWidget(self.update_button)
        self.update_status = QLabel("")
        heading.addWidget(self.update_status)
        main.addLayout(heading)

        # A compact two-column form preserves room for all ten table rows.
        form_box = QGroupBox("נתוני חישוב")
        form = QGridLayout(form_box)
        form.setContentsMargins(10, 5, 10, 5)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        # Switch between Gregorian date and a fully local Hebrew-date editor.
        self.date_mode = QComboBox()
        self.date_mode.addItem("לועזי", "gregorian")
        self.date_mode.addItem("עברי", "hebrew")
        form.addWidget(QLabel("סוג תאריך:"), 0, 0)
        form.addWidget(self.date_mode, 0, 1)
        form.addWidget(QLabel("תאריך:"), 0, 2)
        self.date_stack = QStackedWidget()
        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.day.setDisplayFormat("dd.MM.yyyy")
        self.day.setDate(QDate.currentDate())
        self.day.setMinimumDate(QDate(1850, 1, 1))
        self.day.setMaximumDate(QDate(2149, 12, 31))
        self.day.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.date_stack.addWidget(self.day)

        hebrew_input = QWidget()
        hrow = QHBoxLayout(hebrew_input)
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setSpacing(3)
        self.hebrew_year = QSpinBox()
        self.hebrew_year.setRange(5500, 6100)
        self.hebrew_year.setFixedWidth(114)
        self.hebrew_year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hebrew_year.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.hebrew_month = QComboBox()
        self.hebrew_month.setMinimumWidth(120)
        self.hebrew_day = QSpinBox()
        self.hebrew_day.setRange(1, 30)
        self.hebrew_day.setFixedWidth(78)
        self.hebrew_day.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hebrew_day.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        hrow.addWidget(self.hebrew_day)
        hrow.addWidget(self.hebrew_month, 1)
        hrow.addWidget(self.hebrew_year)
        self.date_stack.addWidget(hebrew_input)
        form.addWidget(self.date_stack, 0, 3)

        self.hour = QTimeEdit()
        self.hour.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.hour.setDisplayFormat("HH:mm")
        self.hour.setTime(QTime(12, 0))
        self.hour.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addWidget(QLabel("שעת לידה:"), 1, 0)
        form.addWidget(self.hour, 1, 1)

        self.unknown = QCheckBox("השעה אינה ידועה")
        self.unknown.toggled.connect(self._unknown_changed)
        form.addWidget(self.unknown, 1, 2)
        self.approx_hour = QCheckBox("שעה בקירוב")
        form.addWidget(self.approx_hour, 1, 3)

        self.city = QComboBox()
        self.city.addItems(["הזנה ידנית", *CITIES])
        self.city.setCurrentText("ירושלים")
        self.city.currentTextChanged.connect(self._city_changed)
        form.addWidget(QLabel("מקום:"), 2, 0)
        form.addWidget(self.city, 2, 1)
        self.phase_label = QLabel("יום / לילה:")
        self.phase = QComboBox()
        for key, label in (
            ("day", "יום"),
            ("evening", "לילה — לפני חצות"),
            ("after_midnight", "לילה — אחרי חצות"),
        ):
            self.phase.addItem(label, key)
        form.addWidget(self.phase_label, 2, 2)
        form.addWidget(self.phase, 2, 3)

        self.lat = QDoubleSpinBox()
        self.lat.setRange(-89.99, 89.99)
        self.lat.setDecimals(5)
        self.lat.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.lon = QDoubleSpinBox()
        self.lon.setRange(-180, 180)
        self.lon.setDecimals(5)
        self.lon.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addWidget(QLabel("קו רוחב (+צפון):"), 3, 0)
        form.addWidget(self.lat, 3, 1)
        form.addWidget(QLabel("קו אורך (+מזרח):"), 3, 2)
        form.addWidget(self.lon, 3, 3)

        self.tz = QLineEdit()
        self.tz.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.tz.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addWidget(QLabel("אזור זמן IANA:"), 4, 0)
        form.addWidget(self.tz, 4, 1, 1, 3)

        self.conversion_label = QLabel("")
        self.conversion_label.setWordWrap(True)
        self.conversion_label.setStyleSheet("color: #1e40af; font-weight: bold;")
        form.addWidget(self.conversion_label, 5, 0, 1, 3)
        self.run = QPushButton("חשב מפת לידה")
        self.run.setMinimumHeight(30)
        self.run.setStyleSheet(
            "font-size: 15px; padding: 4px; background: #2563eb; color: white;")
        self.run.clicked.connect(self._calculate)
        form.addWidget(self.run, 5, 3)
        main.addWidget(form_box)

        # The library treats a date as its daytime date. Correctly map the
        # beginning of the night to the previous Gregorian civil evening.
        gy, gm, gd = from_gregorian(date.today())
        self.hebrew_year.setValue(gy)
        self._fill_hebrew_months(gm)
        self.hebrew_day.setValue(gd)
        self.hebrew_year.valueChanged.connect(self._year_changed)
        self.hebrew_month.currentIndexChanged.connect(self._month_changed)
        self.hebrew_day.valueChanged.connect(self._update_conversion)
        self.phase.currentIndexChanged.connect(self._phase_changed)
        self.hour.timeChanged.connect(self._update_conversion)
        self.date_mode.currentIndexChanged.connect(self._date_mode_changed)
        self._city_changed(self.city.currentText())
        self._date_mode_changed()

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        self.wheel = Wheel()
        split.addWidget(self.wheel)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 2, 4, 2)
        right_layout.setSpacing(4)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["גוף", "מזל", "מעלה במזל", "בית", "תנועה"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setFixedHeight(26)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setMinimumHeight(258)
        right_layout.addWidget(self.table, 1)
        right_layout.addWidget(QLabel("היבטים"))
        self.aspects = QTextEdit()
        self.aspects.setReadOnly(True)
        self.aspects.setMinimumHeight(60)
        self.aspects.setMaximumHeight(88)
        right_layout.addWidget(self.aspects)
        self.warnings = QLabel("")
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet("color: #9a3412;")
        right_layout.addWidget(self.warnings)
        split.addWidget(right)
        split.setSizes([490, 590])
        main.addWidget(split, 1)

    def _toggle_auto_update(self, checked):
        try:
            save_auto_updates(checked)
            self.update_status.setText(
                "בדיקה אוטומטית בפתיחה" if checked else "עדכונים כבויים")
        except OSError as exc:
            QMessageBox.warning(self, "שמירת הגדרות", str(exc))

    def _automatic_update_check(self):
        if self.auto_update.isChecked():
            self._start_update_check()

    def _manual_update_check(self):
        self._start_update_check()

    def _start_update_check(self):
        if self._update_thread is not None and self._update_thread.isRunning():
            return
        self.update_status.setText("בודק...")
        self.update_button.setEnabled(False)
        self._updating = True
        self._update_thread = UpdateCheckThread(self)
        self._update_thread.result.connect(self._on_update_checked)
        self._update_thread.error.connect(self._on_update_error)
        self._update_thread.finished.connect(self._on_update_finished)
        self._update_thread.start()

    def _on_update_checked(self, value):
        if value is None:
            self.update_status.setText("אין גרסה חדשה")
            return
        version, prepared, mode, digest = value
        self.update_status.setText("גרסה " + version + " מוכנה")
        reply = QMessageBox.question(
            self, "עדכון זמין", "גרסה " + version + " הורדה ואומתה. "
            "להתקין אותה כעת ולהפעיל מחדש?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if mode == "setup":
                    launch_setup_install(prepared, install_directory(), version, digest)
                else:
                    launch_install(prepared, install_directory(), version)
                from PySide6.QtWidgets import QApplication
                QApplication.quit()
            except Exception as exc:
                QMessageBox.warning(self, "התקנת עדכון", str(exc))
        else:
            import shutil
            if mode == "setup":
                shutil.rmtree(prepared.parent, ignore_errors=True)
            else:
                shutil.rmtree(prepared, ignore_errors=True)
            self.update_status.setText("העדכון נדחה")

    def _on_update_error(self, message):
        self.update_status.setText("בדיקת העדכון נכשלה")
        if self.isVisible():
            QMessageBox.warning(self, "עדכון תוכנה", message)

    def _on_update_finished(self):
        self._updating = False
        self.update_button.setEnabled(True)

    def closeEvent(self, event):
        if self._updating and self._update_thread and self._update_thread.isRunning():
            event.ignore()
            self.update_status.setText("המתן לסיום בדיקת העדכון")
            return
        super().closeEvent(event)

    def _fill_hebrew_months(self, preferred=None):
        old = preferred if preferred is not None else self.hebrew_month.currentData()
        self.hebrew_month.blockSignals(True)
        self.hebrew_month.clear()
        for number, name in months_of_year(self.hebrew_year.value()):
            self.hebrew_month.addItem(name, number)
        idx = self.hebrew_month.findData(old)
        self.hebrew_month.setCurrentIndex(idx if idx >= 0 else 0)
        self.hebrew_month.blockSignals(False)
        self._month_changed()

    def _year_changed(self, value):
        self._fill_hebrew_months()

    def _month_changed(self, *args):
        month = self.hebrew_month.currentData()
        if month is not None:
            maximum = days_of_month(self.hebrew_year.value(), month)
            self.hebrew_day.setMaximum(maximum)
        self._update_conversion()

    def _unknown_changed(self, checked):
        self.hour.setEnabled(not checked)
        self.approx_hour.setEnabled(not checked)
        self._update_conversion()

    def _date_mode_changed(self, *args):
        hebrew = self.date_mode.currentData() == "hebrew"
        self.date_stack.setCurrentIndex(1 if hebrew else 0)
        self.phase.setVisible(hebrew)
        self.phase_label.setVisible(hebrew)
        # A Hebrew day/night selection needs at least an estimated clock time.
        # For wholly unknown hour, use the Gregorian-date mode instead.
        if hebrew:
            self.unknown.setChecked(False)
        self.unknown.setEnabled(not hebrew)
        self.unknown.setToolTip(
            "בתאריך עברי נדרשת שעה משוערת כדי לזהות את היום האזרחי" if hebrew else "")
        self.approx_hour.setChecked(hebrew)
        self._update_conversion()

    def _phase_changed(self, *args):
        key = self.phase.currentData()
        suggested = {"day": (12, 0), "evening": (21, 0),
                     "after_midnight": (1, 0)}
        if key in suggested:
            self.hour.setTime(QTime(*suggested[key]))
        self._update_conversion()

    def _resolved_input(self):
        clock = self.hour.time()
        local_time = time(clock.hour(), clock.minute())
        if self.date_mode.currentData() == "hebrew":
            return resolve_hebrew_date(
                self.hebrew_year.value(), self.hebrew_month.currentData(),
                self.hebrew_day.value(), self.phase.currentData(), local_time)
        greg = self.day.date()
        from .hebrew_dates import ResolvedDate
        return ResolvedDate(date(greg.year(), greg.month(), greg.day()),
                            local_time, "day")

    def _update_conversion(self, *args):
        if not hasattr(self, "conversion_label"):
            return
        if self.date_mode.currentData() != "hebrew":
            self.conversion_label.setText("")
            return
        try:
            resolved = self._resolved_input()
            self.conversion_label.setText(
                "לועזי: " + resolved.label
                + (" • שעה משוערת" if self.approx_hour.isChecked() else ""))
        except (ValueError, TypeError) as exc:
            self.conversion_label.setText(str(exc))

    def _city_changed(self, city):
        if city in CITIES:
            lat, lon, tz = CITIES[city]
            self.lat.setValue(lat)
            self.lon.setValue(lon)
            self.tz.setText(tz)

    def _calculate(self):
        try:
            if self.date_mode.currentData() == "hebrew" and self.unknown.isChecked():
                raise ValueError("לתאריך עברי בחר יום/לילה ושעה בקירוב")
            resolved = self._resolved_input()
            if self.calc is None:
                self.calc = Calculator()
            day = resolved.civil_day
            hour = resolved.local_time
            zone = self.tz.text().strip()
            latitude, longitude = self.lat.value(), self.lon.value()
            phase_warning = None
            if self.date_mode.currentData() == "hebrew":
                altitude = sun_altitude(
                    self.calc, day, hour, zone, latitude, longitude)
                phase_warning = validate_phase_sun(resolved.phase, altitude)
            chart = self.calc.calculate(
                day, hour, zone, latitude, longitude, self.unknown.isChecked())
            if phase_warning:
                chart.warnings.append(phase_warning)
            if self.approx_hour.isChecked() and not self.unknown.isChecked():
                chart.warnings.append(
                    "שעת הלידה משוערת. המעלות, האופק, רום השמיים, "
                    "הבתים וההיבטים חושבו לפי שעה זו בלבד; "
                    "ייתכנו שינויים כאשר השעה האמיתית שונה.")
            if self.date_mode.currentData() == "hebrew":
                chart.warnings.insert(0, "המרת תאריך עברי: " + resolved.label)
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
        self.aspects.setPlainText("\n".join(
            f"{a.first} – {a.second}: {a.kind}, מרחק {a.separation:.2f}°, סטייה {a.orb:.2f}°"
            for a in chart.aspects))
        angles = "" if chart.ascendant is None else (
            f"\nאופק: {chart.ascendant:.3f}° | MC: {chart.mc:.3f}°"
            f" | ציר נגדי: {chart.descendant:.3f}°")
        self.warnings.setText("\n".join(chart.warnings) + angles)
        self.wheel.set_chart(chart)
