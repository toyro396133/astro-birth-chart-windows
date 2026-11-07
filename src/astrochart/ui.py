from datetime import date, time
from PySide6.QtCore import QDate, Qt, QTime, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHeaderView, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
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
                      auto_updates_enabled, save_auto_updates,
                      auto_install_enabled, save_auto_install)
from .wheel import Wheel
from .theme import apply_theme



class UpdateCheckThread(QThread):
    """Only check the Release metadata. Never download from this thread."""
    result = Signal(object)
    error = Signal(str)

    def run(self):
        try:
            installed = install_directory()
            mode = "setup" if is_installed_setup(installed) else "portable"
            latest = latest_release(SETUP_ASSET if mode == "setup" else ASSET)
            self.result.emit(
                (latest, mode)
                if latest and is_newer(latest.version, __version__) else None)
        except Exception as exc:
            self.error.emit(str(exc))


class UpdateDownloadThread(QThread):
    """Download the user-selected release and verify it, without installing."""
    result = Signal(object)
    error = Signal(str)

    def __init__(self, release, mode, parent=None):
        super().__init__(parent)
        self.release = release
        self.mode = mode

    def run(self):
        import tempfile
        from pathlib import Path
        import shutil
        try:
            if self.mode == "setup":
                folder = Path(tempfile.mkdtemp(prefix="AstroChart-Setup-"))
                path = folder / SETUP_ASSET
                try:
                    download_release(self.release, path)
                except BaseException:
                    shutil.rmtree(folder, ignore_errors=True)
                    raise
                self.result.emit((self.release.version, path, "setup", self.release.digest))
            else:
                installed = install_directory()
                with tempfile.TemporaryDirectory(prefix="AstroChart-Download-") as temp:
                    archive = Path(temp) / "update.zip"
                    download_release(self.release, archive)
                    stage = extract_release(archive, installed, self.release.version)
                self.result.emit((self.release.version, stage, "portable", None))
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AstroBirthChart — מפת לידה")
        self.resize(1240, 830)
        self.setMinimumSize(980, 700)
        self.calc = None
        self._interpretation_chart = None
        self._updating = False
        self._update_thread = None
        self._update_task = None
        self._latest_update = None
        self._update_mode = None
        self._prepared_update = None
        self._install_after_download = False
        self._build()
        QTimer.singleShot(1000, self._automatic_update_check)

    def _build(self):
        root = QWidget()
        root.setObjectName("rootSurface")
        root.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(13, 11, 13, 11)
        main.setSpacing(6)

        def field_label(text):
            label = QLabel(text)
            label.setObjectName("fieldLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            return label

        def section_title(text):
            label = QLabel(text)
            label.setObjectName("sectionTitle")
            return label

        # Elevated application header: identity, status, version and updates.
        header = QFrame()
        header.setObjectName("appHeader")
        heading = QHBoxLayout(header)
        heading.setContentsMargins(16, 6, 16, 6)
        heading.setSpacing(11)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        title = QLabel("מפת לידה אסטרונומית")
        title.setObjectName("appTitle")
        subtitle = QLabel("טרופי  ·  Whole Sign  ·  חישוב מקומי ופרטי")
        subtitle.setObjectName("appSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        heading.addLayout(brand, 1)
        version = QLabel("v" + __version__)
        version.setObjectName("versionPill")
        heading.addWidget(version)
        self.auto_update = QCheckBox("בדיקה אוטומטית")
        self.auto_update.setToolTip(
            "בודק אם יש גרסה חדשה בעת פתיחה. אינו מוריד או מתקין דבר; "
            "נתוני המפה אינם נשלחים.")
        self.auto_update.setChecked(auto_updates_enabled())
        self.auto_update.toggled.connect(self._toggle_auto_update)
        heading.addWidget(self.auto_update)
        self.update_button = QPushButton("בדוק עדכונים")
        self.update_button.setObjectName("updateButton")
        self.update_button.clicked.connect(self._manual_update_check)
        heading.addWidget(self.update_button)
        self.update_status = QLabel("")
        self.update_status.setObjectName("updateStatus")
        heading.addWidget(self.update_status)
        main.addWidget(header)
        # Updates are shown only after a metadata-only check finds a new version.
        self.update_panel = QFrame()
        self.update_panel.setObjectName("updatePanel")
        panel_row = QHBoxLayout(self.update_panel)
        panel_row.setContentsMargins(12, 5, 12, 5)
        panel_row.setSpacing(8)
        self.latest_update_label = QLabel("")
        self.latest_update_label.setObjectName("latestUpdateLabel")
        panel_row.addWidget(self.latest_update_label, 1)
        self.auto_install = QCheckBox("התקן אוטומטית אחרי ההורדה")
        self.auto_install.setObjectName("autoInstallChoice")
        self.auto_install.setToolTip(
            "הורדה מתחילה רק בלחיצה על 'הורד עדכון'. "
            "כאשר מסומן, העדכון המאומת מותקן ומפעיל מחדש בלי בקשת אישור נוספת.")
        self.auto_install.setChecked(auto_install_enabled())
        self.auto_install.toggled.connect(self._toggle_auto_install)
        panel_row.addWidget(self.auto_install)
        self.download_button = QPushButton("הורד עדכון")
        self.download_button.setObjectName("downloadUpdateButton")
        self.download_button.clicked.connect(self._download_update)
        panel_row.addWidget(self.download_button)
        self.install_button = QPushButton("התקן והפעל מחדש")
        self.install_button.setObjectName("installUpdateButton")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._install_prepared)
        panel_row.addWidget(self.install_button)
        main.addWidget(self.update_panel)
        self.update_panel.hide()

        # Clean, progressive-disclosure input card. Common fields stay visible;
        # coordinates and IANA zone remain one click away for power users.
        form_box = QGroupBox("פרטי לידה")
        form_box.setObjectName("inputCard")
        form = QGridLayout(form_box)
        form.setContentsMargins(12, 7, 12, 5)
        form.setHorizontalSpacing(11)
        form.setVerticalSpacing(2)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 2)

        self.date_mode = QComboBox()
        self.date_mode.addItem("לועזי", "gregorian")
        self.date_mode.addItem("עברי", "hebrew")
        self.date_mode.setMaximumWidth(215)
        form.addWidget(field_label("סוג תאריך"), 0, 0)
        form.addWidget(self.date_mode, 0, 1)
        form.addWidget(field_label("תאריך הלידה"), 0, 2)
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
        hrow.setSpacing(6)
        self.hebrew_year = QSpinBox()
        self.hebrew_year.setRange(5500, 6100)
        self.hebrew_year.setFixedWidth(112)
        self.hebrew_year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hebrew_year.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.hebrew_month = QComboBox()
        self.hebrew_month.setMinimumWidth(105)
        self.hebrew_day = QSpinBox()
        self.hebrew_day.setRange(1, 30)
        self.hebrew_day.setFixedWidth(76)
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
        self.hour.setMaximumWidth(215)
        form.addWidget(field_label("שעת לידה"), 1, 0)
        form.addWidget(self.hour, 1, 1)

        options = QHBoxLayout()
        options.setSpacing(16)
        self.unknown = QCheckBox("השעה אינה ידועה")
        self.unknown.toggled.connect(self._unknown_changed)
        self.approx_hour = QCheckBox("שעה בקירוב")
        options.addWidget(self.unknown)
        options.addWidget(self.approx_hour)
        options.addStretch(1)
        form.addLayout(options, 1, 2, 1, 2)

        self.city = QComboBox()
        self.city.addItems(["הזנה ידנית", *CITIES])
        self.city.setCurrentText("ירושלים")
        self.city.currentTextChanged.connect(self._city_changed)
        self.city.setMaximumWidth(300)
        form.addWidget(field_label("מקום לידה"), 2, 0)
        form.addWidget(self.city, 2, 1)
        self.phase_label = field_label("יום או לילה")
        self.phase = QComboBox()
        for key, label in (
            ("day", "יום"),
            ("evening", "לילה — לפני חצות"),
            ("after_midnight", "לילה — אחרי חצות"),
        ):
            self.phase.addItem(label, key)
        form.addWidget(self.phase_label, 2, 2)
        form.addWidget(self.phase, 2, 3)

        self.advanced_toggle = QPushButton("＋ מיקום מתקדם")
        self.advanced_toggle.setObjectName("advancedToggle")
        self.advanced_toggle.setToolTip("עריכה ידנית של קווי רוחב/אורך ואזור זמן")
        self.advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.advanced_toggle.clicked.connect(lambda: self._toggle_advanced())
        form.addWidget(self.advanced_toggle, 3, 0, 1, 2)
        self.conversion_label = QLabel("")
        self.conversion_label.setObjectName("conversionInfo")
        self.conversion_label.setWordWrap(True)
        form.addWidget(self.conversion_label, 3, 2, 1, 2)

        footnote = QLabel("החישוב נשאר במחשב שלך — ללא העברת נתונים")
        footnote.setObjectName("helperText")
        footnote.setWordWrap(True)
        form.addWidget(footnote, 4, 0, 1, 2)
        self.run = QPushButton("חשב מפת לידה")
        self.run.setObjectName("calculateButton")
        self.run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run.clicked.connect(self._calculate)
        form.addWidget(self.run, 4, 2, 1, 2)

        self.advanced = QFrame()
        self.advanced.setObjectName("advancedPanel")
        adv = QGridLayout(self.advanced)
        adv.setContentsMargins(10, 7, 10, 7)
        adv.setHorizontalSpacing(10)
        adv.setVerticalSpacing(6)
        adv.setColumnStretch(1, 1)
        adv.setColumnStretch(3, 1)

        self.lat = QDoubleSpinBox()
        self.lat.setRange(-89.99, 89.99)
        self.lat.setDecimals(5)
        self.lat.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.lon = QDoubleSpinBox()
        self.lon.setRange(-180, 180)
        self.lon.setDecimals(5)
        self.lon.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        adv.addWidget(field_label("קו רוחב (+צפון)"), 0, 0)
        adv.addWidget(self.lat, 0, 1)
        adv.addWidget(field_label("קו אורך (+מזרח)"), 0, 2)
        adv.addWidget(self.lon, 0, 3)

        self.tz = QLineEdit()
        self.tz.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.tz.setAlignment(Qt.AlignmentFlag.AlignLeft)
        adv.addWidget(field_label("אזור זמן IANA"), 1, 0)
        adv.addWidget(self.tz, 1, 1, 1, 3)
        form.addWidget(self.advanced, 5, 0, 1, 4)
        self.advanced.setVisible(False)
        main.addWidget(form_box)

        # Initialize both calendars before any calculation.
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

        # Equal-weight dashboard cards, resizable by a native Qt splitter.
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(9)
        wheel_card = QFrame()
        wheel_card.setObjectName("panelCard")
        wheel_layout = QVBoxLayout(wheel_card)
        wheel_layout.setContentsMargins(12, 10, 12, 10)
        wheel_layout.setSpacing(4)
        wheel_heading = QHBoxLayout()
        wheel_heading.addWidget(section_title("גלגל המפה"), 1)
        wheel_legend = QLabel("מיקומים והיבטים")
        wheel_legend.setObjectName("helperText")
        wheel_heading.addWidget(wheel_legend)
        wheel_layout.addLayout(wheel_heading)
        self.wheel = Wheel()
        wheel_layout.addWidget(self.wheel, 1)
        split.addWidget(wheel_card)

        details_card = QFrame()
        details_card.setObjectName("panelCard")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_layout.setSpacing(4)
        table_heading = QHBoxLayout()
        table_heading.addWidget(section_title("מיקומי הגופים"), 1)
        self.chart_caption = QLabel("תוצאות החישוב יופיעו כאן")
        self.chart_caption.setObjectName("helperText")
        table_heading.addWidget(self.chart_caption)
        self.interpret_button = QPushButton("פרשנות אופי (ניסוי)")
        self.interpret_button.setObjectName("interpretationButton")
        self.interpret_button.setToolTip(
            "פרשנות סמלית לפי חבילת כללים מתפתחת, בנפרד מנתוני החישוב")
        self.interpret_button.setEnabled(False)
        self.interpret_button.clicked.connect(self._open_interpretation)
        table_heading.addWidget(self.interpret_button)
        details_layout.addLayout(table_heading)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("bodyTable")
        self.table.setHorizontalHeaderLabels(
            ["גוף", "מזל", "מעלה במזל", "בית", "תנועה"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setFixedHeight(27)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(275)
        details_layout.addWidget(self.table, 1)

        self.aspects_title = section_title("היבטים בין הגופים")
        details_layout.addWidget(self.aspects_title)
        self.aspects = QTextEdit()
        self.aspects.setObjectName("aspectText")
        self.aspects.setReadOnly(True)
        self.aspects.setMinimumHeight(47)
        self.aspects.setMaximumHeight(66)
        details_layout.addWidget(self.aspects)

        details_layout.addWidget(section_title("הערות ודיוק החישוב"))
        self.warning_scroll = QScrollArea()
        self.warning_scroll.setObjectName("warningScroll")
        self.warning_scroll.setWidgetResizable(True)
        self.warning_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.warning_scroll.setMinimumHeight(39)
        self.warning_scroll.setMaximumHeight(61)
        warning_contents = QWidget()
        warning_contents.setObjectName("warningContents")
        warning_layout = QVBoxLayout(warning_contents)
        warning_layout.setContentsMargins(9, 6, 9, 6)
        self.warnings = QLabel("")
        self.warnings.setObjectName("warningText")
        self.warnings.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.warnings.setWordWrap(True)
        warning_layout.addWidget(self.warnings)
        warning_layout.addStretch()
        self.warning_scroll.setWidget(warning_contents)
        details_layout.addWidget(self.warning_scroll)
        split.addWidget(details_card)
        split.setSizes([520, 610])
        main.addWidget(split, 1)

        apply_theme(self)

    def _toggle_advanced(self, checked=None):
        expanded = (not self.advanced.isHidden()) if checked is None else bool(checked)
        if checked is None:
            expanded = not expanded
        self.advanced.setVisible(expanded)
        self.advanced_toggle.setText(
            "− הסתר מיקום מתקדם" if expanded
            else "＋ מיקום מתקדם")

    def _toggle_auto_update(self, checked):
        try:
            save_auto_updates(checked)
            self.update_status.setText(
                "בדיקה אוטומטית בפתיחה" if checked else "בדיקה אוטומטית כבויה")
        except OSError as exc:
            QMessageBox.warning(self, "שמירת הגדרות", str(exc))

    def _toggle_auto_install(self, checked):
        try:
            save_auto_install(checked)
        except OSError as exc:
            self.auto_install.blockSignals(True)
            self.auto_install.setChecked(not checked)
            self.auto_install.blockSignals(False)
            QMessageBox.warning(self, "שמירת הגדרות", str(exc))

    def _automatic_update_check(self):
        if self.auto_update.isChecked():
            self._start_update_check()

    def _manual_update_check(self):
        self._start_update_check()

    def _clear_prepared_update(self):
        """Delete only discarded verified downloads; not an active installation."""
        import shutil
        if self._prepared_update is not None:
            _, prepared, mode, _ = self._prepared_update
            if mode == "setup":
                shutil.rmtree(prepared.parent, ignore_errors=True)
            else:
                shutil.rmtree(prepared, ignore_errors=True)
            self._prepared_update = None
        self.install_button.setEnabled(False)

    def _start_update_check(self):
        if self._updating:
            return
        self._clear_prepared_update()
        self._latest_update = None
        self._update_mode = None
        self.update_panel.hide()
        self.update_status.setText("בודק גרסאות...")
        self.update_button.setEnabled(False)
        self._updating = True
        self._update_task = "check"
        self._update_thread = UpdateCheckThread(self)
        self._update_thread.result.connect(self._on_update_checked)
        self._update_thread.error.connect(self._on_update_error)
        self._update_thread.finished.connect(self._on_update_finished)
        self._update_thread.start()

    def _on_update_checked(self, value):
        if value is None:
            self.update_status.setText("אין עדכון חדש זמין")
            return
        release, mode = value
        self._latest_update = release
        self._update_mode = mode
        megabytes = release.size / (1024 * 1024)
        self.latest_update_label.setText(
            f"גרסה אחרונה: v{release.version} · גודל הורדה: {megabytes:.1f}MB")
        self.update_panel.show()
        self.download_button.setEnabled(True)
        self.update_status.setText(f"עדכון v{release.version} זמין — טרם הורד")

    def _download_update(self):
        if self._updating or self._latest_update is None or self._prepared_update is not None:
            return
        if not is_newer(self._latest_update.version, __version__):
            return
        self._updating = True
        self._update_task = "download"
        self._install_after_download = self.auto_install.isChecked()
        self.auto_install.setEnabled(False)
        self.update_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.update_status.setText(f"מוריד ומאמת גרסה {self._latest_update.version}...")
        self._update_thread = UpdateDownloadThread(
            self._latest_update, self._update_mode, self)
        self._update_thread.result.connect(self._on_update_downloaded)
        self._update_thread.error.connect(self._on_update_error)
        self._update_thread.finished.connect(self._on_update_finished)
        self._update_thread.start()

    def _on_update_downloaded(self, value):
        self._prepared_update = value
        version = value[0]
        self.update_status.setText(f"גרסה {version} הורדה ואומתה — מוכנה להתקנה")
        self.install_button.setEnabled(True)

    def _install_prepared(self):
        if self._updating or self._prepared_update is None:
            return
        version, prepared, mode, digest = self._prepared_update
        if not is_newer(version, __version__):
            self._clear_prepared_update()
            return
        try:
            if mode == "setup":
                launch_setup_install(prepared, install_directory(), version, digest)
            else:
                launch_install(prepared, install_directory(), version)
            # The worker owns the prepared files once it is launched.
            self._prepared_update = None
            self.update_status.setText("מתקין את העדכון ומפעיל מחדש...")
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(self, "התקנת עדכון", str(exc))
            self.update_status.setText("התקנה נכשלה — אפשר לנסות שוב")

    def _on_update_error(self, message):
        operation = "ההורדה" if self._update_task == "download" else "בדיקת העדכון"
        self.update_status.setText(operation + " נכשלה")
        if self.isVisible():
            QMessageBox.warning(self, "עדכון תוכנה", message)

    def _on_update_finished(self):
        task = self._update_task
        self._updating = False
        self._update_task = None
        self.update_button.setEnabled(True)
        self.auto_install.setEnabled(True)
        if task == "download":
            if self._prepared_update is None:
                self.download_button.setEnabled(self._latest_update is not None)
                return
            if self._install_after_download:
                self._install_prepared()
            else:
                version = self._prepared_update[0]
                reply = QMessageBox.question(
                    self, "עדכון מוכן",
                    f"גרסה {version} הורדה ואומתה. להתקין אותה כעת ולהפעיל מחדש?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._install_prepared()
                else:
                    self.update_status.setText(
                        f"גרסה {version} מוכנה — ניתן להתקין בכל עת")
                    self.download_button.setEnabled(False)

    def closeEvent(self, event):
        if self._updating and self._update_thread and self._update_thread.isRunning():
            event.ignore()
            self.update_status.setText("המתן לסיום בדיקת/הורדת העדכון")
            return
        self._clear_prepared_update()
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
        elif city == "הזנה ידנית":
            self._toggle_advanced(True)

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
        self._interpretation_chart = chart
        self.interpret_button.setEnabled(True)
        self.chart_caption.setText(
            f"{len(chart.bodies)} גופים · " +
            ("שעה לא ידועה" if chart.approximate else "מפה מחושבת"))
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

    def _open_interpretation(self):
        if self._interpretation_chart is None:
            return
        from .interpretation_dialog import RuleInterpretationDialog
        dialog = RuleInterpretationDialog(self._interpretation_chart, self)
        dialog.exec()
