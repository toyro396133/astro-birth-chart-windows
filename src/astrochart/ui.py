from datetime import date, time
import json
from pathlib import Path
from PySide6.QtCore import QDate, Qt, QTime, QTimer, QThread, Signal, QSettings
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHeaderView, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QTimeEdit, QVBoxLayout, QWidget,
)
from .domain import SIGNS, degree_in_sign
from .engine import Calculator
from .hebrew_dates import (months_of_year, days_of_month, from_gregorian,
                           resolve_hebrew_date, sun_altitude, validate_phase_sun)
from .mixed_dates import hebrew_months_in_gregorian_year, mixed_candidates
from .changelog import render_history
from .locations import CITIES
from .location_catalog import (
    catalog_labels, resolve_location, load_favorites, save_favorite, MANUAL_LABEL,
)
from . import __version__
from .updater import (UpdateError, latest_release, is_newer, download_release,
                      extract_release, install_directory, launch_install, launch_setup_install,
                      is_installed_setup, SETUP_ASSET, ASSET, selected_setup_download,
                      auto_updates_enabled, save_auto_updates,
                      auto_install_enabled, save_auto_install)
from .wheel import Wheel, format_body_label
from .theme import apply_theme
from .report import format_chart_report
from .chart_storage import make_record, read_record, save_record, export_results
from .chart_export import export_wheel_png, export_chart_pdf
from .chart_tables_pdf import export_chart_tables_pdf
from .aspect_explorer import AspectExplorerDialog
from .display_preferences import (
    DisplayPreferences, read_preferences, save_preferences,
    FONT_PERCENTS, ROW_HEIGHTS, SYMBOL_SIZES,
)



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
                asset, filename, selected_mode = selected_setup_download(self.release)
                path = folder / filename
                try:
                    try:
                        download_release(asset, path)
                    except (UpdateError, OSError, ValueError):
                        if selected_mode != "setup-delta":
                            raise
                        # Invalid or unavailable delta: use the existing full
                        # signed installer, with the same registered-install path.
                        path.unlink(missing_ok=True)
                        selected_mode = "setup"
                        asset = self.release
                        path = folder / SETUP_ASSET
                        download_release(asset, path)
                except BaseException:
                    shutil.rmtree(folder, ignore_errors=True)
                    raise
                self.result.emit((self.release.version, path, selected_mode, asset.digest))
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
        self._active_chart = None
        self._aspect_dialog = None
        self._active_record = None
        self._current_file = None
        self._display_settings = QSettings("AstroBirthChart", "AstroBirthChart")
        self._favorites = load_favorites()
        self._session_locations = {}
        self._updating = False
        self._update_thread = None
        self._update_task = None
        self._latest_update = None
        self._update_mode = None
        self._prepared_update = None
        self._install_after_download = False
        self._build()
        self._apply_display_preferences(read_preferences(self._display_settings))
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
        self.file_button = QPushButton("קובץ")
        self.file_button.setObjectName("fileMenuButton")
        self.file_menu = QMenu(self.file_button)
        for text, fn in (
            ("פתח מפה...", self._open_chart),
            ("שמור מפה", lambda: self._save_chart(False)),
            ("שמור בשם...", lambda: self._save_chart(True)),
            ("ייצא כ־JSON...", lambda: self._export_chart("json")),
            ("ייצא כטקסט...", lambda: self._export_chart("txt")),
            ("ייצא גלגל PNG...", lambda: self._export_chart("png")),
            ("ייצא דוח PDF...", lambda: self._export_chart("pdf")),
            ("ייצא PDF — טבלת מזלות והיבטים...", lambda: self._export_chart("pdf_tables")),
        ):
            action = self.file_menu.addAction(text)
            action.triggered.connect(fn)
        history_action = self.file_menu.addAction("יומן שינויים לפי חבילות...")
        history_action.triggered.connect(self._show_changelog)
        self.file_menu.addSeparator()
        preferences_action = self.file_menu.addAction("הגדרות תצוגה...")
        preferences_action.triggered.connect(self._open_display_preferences)
        self.file_button.setMenu(self.file_menu)
        heading.addWidget(self.file_button)
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
        self.update_details = QTextEdit()
        self.update_details.setReadOnly(True)
        self.update_details.setMaximumHeight(150)
        self.update_details.setObjectName("updateChanges")
        main.addWidget(self.update_details)
        self.update_details.hide()

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
        self.date_mode.addItem("מעורב: שנה לועזית + יום וחודש עבריים", "mixed")
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
        hroot = QVBoxLayout(hebrew_input)
        hroot.setContentsMargins(0, 0, 0, 0)
        hroot.setSpacing(2)
        hrow = QHBoxLayout()
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setSpacing(6)
        hroot.addLayout(hrow)
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
        self.mixed_year = QSpinBox()
        self.mixed_year.setRange(1850, 2149)
        self.mixed_year.setValue(date.today().year)
        self.mixed_year.setFixedWidth(112)
        self.mixed_year.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.mixed_year.setToolTip("השנה לפי הלוח הלועזי")
        hrow.addWidget(self.mixed_year)
        self.mixed_year.hide()
        self.mixed_choice = QComboBox()
        self.mixed_choice.setToolTip("בחר את התאריך המדויק אם קיימות כמה התאמות בשנה הלועזית")
        self.mixed_choice.hide()
        hroot.addWidget(self.mixed_choice)
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
        self.city.setEditable(True)
        self.city.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.city.addItems(catalog_labels(self._favorites))
        self.city.setCurrentText("ירושלים")
        completer = self.city.completer()
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
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
        self.save_favorite_button = QPushButton("שמור מיקום נוכחי כמועדף")
        self.save_favorite_button.setToolTip(
            "שומר את הקואורדינטות ואזור הזמן במחשב זה בלבד")
        self.save_favorite_button.clicked.connect(self._save_favorite_location)
        adv.addWidget(self.save_favorite_button, 2, 0, 1, 4)
        form.addWidget(self.advanced, 5, 0, 1, 4)
        self.advanced.setVisible(False)
        main.addWidget(form_box)

        # Initialize both calendars before any calculation.
        gy, gm, gd = from_gregorian(date.today())
        self.hebrew_year.setValue(gy)
        self._fill_hebrew_months(gm)
        self.hebrew_day.setValue(gd)
        self.hebrew_year.valueChanged.connect(self._year_changed)
        self.mixed_year.valueChanged.connect(self._mixed_year_changed)
        self.mixed_choice.currentIndexChanged.connect(self._update_conversion)
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
        self.wheel_legend = QLabel("לחץ על סמל במפה כדי לבחור גוף")
        self.wheel_legend.setObjectName("helperText")
        self.wheel_legend.setMinimumWidth(120)
        self.wheel_legend.setMaximumWidth(355)
        self.wheel_legend.setWordWrap(True)
        wheel_heading.addWidget(self.wheel_legend)
        wheel_layout.addLayout(wheel_heading)
        self.wheel = Wheel()
        self.wheel.bodySelected.connect(self._on_wheel_selection)
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
        self.copy_button = QPushButton("העתק תקציר")
        self.copy_button.setObjectName("copyReportButton")
        self.copy_button.setToolTip("העתק את נתוני המפה, כולל מגבלות הדיוק")
        self.copy_button.setAccessibleName("העתקת תקציר מפה")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_report)
        table_heading.addWidget(self.copy_button)
        self.copy_row_button = QPushButton("העתק שורה")
        self.copy_row_button.setObjectName("copyRowButton")
        self.copy_row_button.clicked.connect(self._copy_selected_table_rows)
        table_heading.addWidget(self.copy_row_button)
        details_layout.addLayout(table_heading)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("bodyTable")
        self.table.setHorizontalHeaderLabels(
            ["גוף", "מזל", "מעלה במזל", "בית", "תנועה"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultSectionSize(98)
        self.table.horizontalHeader().setFixedHeight(24)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setMinimumSectionSize(18)
        self.table.verticalHeader().setDefaultSectionSize(21)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(262)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.currentCellChanged.connect(self._on_table_selection)
        self.table.setSortingEnabled(True)
        QShortcut(QKeySequence.StandardKey.Copy, self.table).activated.connect(
            self._copy_selected_table_rows)
        self.table.setToolTip("בחירת שורה מסמנת את הגוף בגלגל")
        details_layout.addWidget(self.table, 1)

        self.aspects_title = section_title("היבטים בין הגופים")
        aspect_heading = QHBoxLayout()
        aspect_heading.addWidget(self.aspects_title)
        aspect_heading.addStretch()
        self.aspect_explorer_button = QPushButton("חקירת היבטים")
        self.aspect_explorer_button.setObjectName("aspectExplorerButton")
        self.aspect_explorer_button.setFixedHeight(18)
        self.aspect_explorer_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; "
            "color: #2a609e; min-height: 0; padding: 0 5px; font-size: 10px; }")
        self.aspect_explorer_button.setEnabled(False)
        self.aspect_explorer_button.clicked.connect(self._open_aspect_explorer)
        aspect_heading.addWidget(self.aspect_explorer_button)
        details_layout.addLayout(aspect_heading)
        self.aspects = QTextEdit()
        self.aspects.setObjectName("aspectText")
        self.aspects.setReadOnly(True)
        self.aspects.setMinimumHeight(34)
        self.aspects.setMaximumHeight(54)
        details_layout.addWidget(self.aspects)

        details_layout.addWidget(section_title("הערות ודיוק החישוב"))
        self.warning_scroll = QScrollArea()
        self.warning_scroll.setObjectName("warningScroll")
        self.warning_scroll.setWidgetResizable(True)
        self.warning_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.warning_scroll.setMinimumHeight(29)
        self.warning_scroll.setMaximumHeight(52)
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

        for signal in (
            self.day.dateChanged, self.hour.timeChanged, self.unknown.toggled,
            self.approx_hour.toggled, self.city.currentTextChanged,
            self.lat.valueChanged, self.lon.valueChanged, self.tz.textChanged,
            self.date_mode.currentIndexChanged, self.hebrew_year.valueChanged,
            self.hebrew_month.currentIndexChanged, self.hebrew_day.valueChanged,
            self.mixed_year.valueChanged, self.mixed_choice.currentIndexChanged,
            self.phase.currentIndexChanged,
        ):
            signal.connect(self._invalidate_chart)

    def _apply_display_preferences(self, preferences):
        """Adjust layout only; the computed astronomical chart remains unchanged."""
        apply_theme(self, preferences.font_percent)
        self.table.verticalHeader().setDefaultSectionSize(preferences.row_height)
        self.wheel.set_symbol_point_size(preferences.symbol_size)

    def _open_display_preferences(self):
        current = read_preferences(self._display_settings)
        dialog = QDialog(self)
        dialog.setWindowTitle("הגדרות תצוגה")
        dialog.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        dialog.setMinimumWidth(320)
        layout = QVBoxLayout(dialog)
        description = QLabel("הגדרות אלו נשמרות במחשב זה ואינן משנות את החישוב.")
        description.setWordWrap(True)
        layout.addWidget(description)

        def combo(caption, options, selected):
            layout.addWidget(QLabel(caption))
            widget = QComboBox()
            for text, value in options:
                widget.addItem(text, value)
            widget.setCurrentIndex(widget.findData(selected))
            layout.addWidget(widget)
            return widget

        font = combo("גודל הגופנים", [
            ("קטן (90%)", 90), ("רגיל (100%)", 100),
            ("גדול (110%)", 110), ("גדול מאוד (120%)", 120),
        ], current.font_percent)
        rows = combo("צפיפות טבלת התוצאות", [
            ("צפופה", 21), ("רגילה", 26), ("מרווחת", 30),
        ], current.row_height)
        symbols = combo("גודל סמלי הגלגל", [
            ("קטנים", 14), ("רגילים", 16), ("גדולים", 18),
        ], current.symbol_size)
        buttons = QHBoxLayout()
        save = QPushButton("שמור")
        cancel = QPushButton("ביטול")
        save.clicked.connect(dialog.accept)
        cancel.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = DisplayPreferences(
            font.currentData(), rows.currentData(), symbols.currentData())
        try:
            save_preferences(self._display_settings, updated)
            self._apply_display_preferences(updated)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "הגדרות תצוגה", str(exc))

    def _invalidate_chart(self, *args):
        """A form change invalidates all chart data, interpretation and exports."""
        if self._active_chart is None and self._interpretation_chart is None:
            return
        self._active_chart = None
        self._interpretation_chart = None
        if self._aspect_dialog is not None:
            self._aspect_dialog.close()
            self._aspect_dialog = None
        self._active_record = None
        self.aspect_explorer_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.interpret_button.setEnabled(False)
        self.wheel.set_chart(None)
        self.table.setRowCount(0)
        self.aspects.clear()
        self.wheel_legend.setText("לחץ על סמל במפה כדי לבחור גוף")
        self.chart_caption.setText("הנתונים השתנו — נדרש חישוב מחדש")
        self.warnings.setText("התוצאה הקודמת הוסרה כי אינה מתאימה לנתוני הקלט")

    def _copy_selected_table_rows(self):
        selection = self.table.selectionModel()
        rows = sorted({index.row() for index in selection.selectedRows()})
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        if not rows and self.table.rowCount() == 1:
            rows = [0]
        if not rows:
            return
        QApplication.clipboard().setText("\n".join("\t".join(
            self.table.item(row, column).text() if self.table.item(row, column) else ""
            for column in range(self.table.columnCount())) for row in rows))

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
            if mode in ("setup", "setup-delta"):
                shutil.rmtree(prepared.parent, ignore_errors=True)
            else:
                shutil.rmtree(prepared, ignore_errors=True)
            self._prepared_update = None
        self.install_button.setEnabled(False)

    def _show_changelog(self):
        QMessageBox.information(self, "יומן שינויים — לפי חבילות", render_history())

    def _start_update_check(self):
        if self._updating:
            return
        self._clear_prepared_update()
        self._latest_update = None
        self._update_mode = None
        self.update_panel.hide()
        self.update_details.hide()
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
        partial = mode == "setup" and release.delta_size > 0
        megabytes = (release.delta_size if partial else release.size) / (1024 * 1024)
        suffix = (" · עדכון חלקי (במקום "
                  f"{release.size / (1024 * 1024):.1f}MB)"
                  if partial else " · חבילה מלאה")
        self.latest_update_label.setText(
            f"גרסה אחרונה: v{release.version} · הורדה: {megabytes:.1f}MB{suffix}")
        self.update_panel.show()
        self.update_details.setPlainText(
            release.notes.strip() or "לא פורסם פירוט שינויים עבור גרסה זו.")
        self.update_details.show()
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
        kind = "העדכון החלקי" if value[2] == "setup-delta" else "החבילה"
        self.update_status.setText(f"גרסה {version}: {kind} הורדה ואומתה — מוכנה להתקנה")
        self.install_button.setEnabled(True)

    def _install_prepared(self):
        if self._updating or self._prepared_update is None:
            return
        version, prepared, mode, digest = self._prepared_update
        if not is_newer(version, __version__):
            self._clear_prepared_update()
            return
        try:
            if mode in ("setup", "setup-delta"):
                if mode == "setup-delta":
                    launch_setup_install(prepared, install_directory(), version, digest,
                                         fallback_release=self._latest_update)
                else:
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
        if self.date_mode.currentData() == "mixed":
            months = hebrew_months_in_gregorian_year(self.mixed_year.value())
        else:
            months = months_of_year(self.hebrew_year.value())
        for number, name in months:
            self.hebrew_month.addItem(name, number)
        idx = self.hebrew_month.findData(old)
        self.hebrew_month.setCurrentIndex(idx if idx >= 0 else 0)
        self.hebrew_month.blockSignals(False)
        self._month_changed()

    def _year_changed(self, value):
        if self.date_mode.currentData() != "mixed":
            self._fill_hebrew_months()

    def _mixed_year_changed(self, value):
        if self.date_mode.currentData() == "mixed":
            self._fill_hebrew_months()

    def _month_changed(self, *args):
        month = self.hebrew_month.currentData()
        if month is not None:
            if self.date_mode.currentData() == "mixed":
                year = self.mixed_year.value()
                begin = from_gregorian(date(year, 1, 1))[0]
                end = from_gregorian(date(year, 12, 31))[0]
                lengths = [days_of_month(hebrew_year, month)
                           for hebrew_year in range(begin - 1, end + 2)
                           if month in {number for number, _ in months_of_year(hebrew_year)}]
                maximum = max(lengths) if lengths else 29
            else:
                maximum = days_of_month(self.hebrew_year.value(), month)
            self.hebrew_day.setMaximum(maximum)
        self._update_conversion()

    def _refresh_mixed_choices(self):
        if self.date_mode.currentData() != "mixed":
            return
        month = self.hebrew_month.currentData()
        selected = self.mixed_choice.currentData()
        options = mixed_candidates(
            self.mixed_year.value(), month, self.hebrew_day.value(),
            self.phase.currentData(), time(self.hour.time().hour(), self.hour.time().minute())
        ) if month is not None else []
        self.mixed_choice.blockSignals(True)
        self.mixed_choice.clear()
        if len(options) > 1:
            self.mixed_choice.addItem("בחר התאמה — קיימים כמה תאריכים", None)
        for option in options:
            self.mixed_choice.addItem(option.label, option.key)
        idx = self.mixed_choice.findData(selected) if selected is not None else -1
        if idx >= 0:
            self.mixed_choice.setCurrentIndex(idx)
        elif len(options) > 1:
            self.mixed_choice.setCurrentIndex(0)
        elif options:
            self.mixed_choice.setCurrentIndex(0)
        self.mixed_choice.blockSignals(False)


    def _unknown_changed(self, checked):
        self.hour.setEnabled(not checked)
        self.approx_hour.setEnabled(not checked)
        self._update_conversion()

    def _date_mode_changed(self, *args):
        calendar_mode = self.date_mode.currentData() in ("hebrew", "mixed")
        mixed = self.date_mode.currentData() == "mixed"
        self.date_stack.setCurrentIndex(1 if calendar_mode else 0)
        self.phase.setVisible(calendar_mode)
        self.phase_label.setVisible(calendar_mode)
        self.hebrew_year.setVisible(not mixed)
        self.mixed_year.setVisible(mixed)
        self.mixed_choice.setVisible(mixed)
        if calendar_mode:
            self.unknown.setChecked(False)
        self.unknown.setEnabled(not calendar_mode)
        self.unknown.setToolTip(
            "בתאריך עברי או מעורב נדרשת שעה בקירוב" if calendar_mode else "")
        self.approx_hour.setChecked(calendar_mode)
        self._fill_hebrew_months()
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
        mode = self.date_mode.currentData()
        if mode == "hebrew":
            return resolve_hebrew_date(
                self.hebrew_year.value(), self.hebrew_month.currentData(),
                self.hebrew_day.value(), self.phase.currentData(), local_time)
        if mode == "mixed":
            candidates = mixed_candidates(
                self.mixed_year.value(), self.hebrew_month.currentData(),
                self.hebrew_day.value(), self.phase.currentData(), local_time)
            if not candidates:
                raise ValueError("לא נמצאה התאמה בין השנה הלועזית לתאריך העברי")
            selected = self.mixed_choice.currentData()
            if selected is None:
                raise ValueError("נמצאו כמה תאריכים — יש לבחור התאמה")
            for candidate in candidates:
                if candidate.key == selected:
                    return candidate.resolved
            raise ValueError("התאריך שנבחר אינו תואם לקלט הנוכחי")
        greg = self.day.date()
        from .hebrew_dates import ResolvedDate
        return ResolvedDate(date(greg.year(), greg.month(), greg.day()),
                            local_time, "day")

    def _update_conversion(self, *args):
        if not hasattr(self, "conversion_label"):
            return
        if self.date_mode.currentData() not in ("hebrew", "mixed"):
            self.conversion_label.setText("")
            return
        if self.date_mode.currentData() == "mixed":
            self._refresh_mixed_choices()
        try:
            resolved = self._resolved_input()
            self.conversion_label.setText(
                "לועזי: " + resolved.label
                + (" • שעה משוערת" if self.approx_hour.isChecked() else ""))
        except (ValueError, TypeError) as exc:
            self.conversion_label.setText(str(exc))

    def _city_changed(self, city):
        location = resolve_location(
            city, {**self._favorites, **self._session_locations})
        if location is not None:
            lat, lon, tz = location
            self.lat.setValue(lat)
            self.lon.setValue(lon)
            self.tz.setText(tz)
            self.run.setEnabled(True)
            self.city.setToolTip("")
        elif city == MANUAL_LABEL:
            self._toggle_advanced(True)
            self.run.setEnabled(True)
            self.city.setToolTip("הזן קואורדינטות ואזור זמן במיקום מתקדם")
        else:
            # Never silently calculate an unrecognized city using old coordinates.
            self.run.setEnabled(False)
            self.city.setToolTip("מיקום לא מוכר: בחר מהרשימה או בהזנה ידנית")

    def _save_favorite_location(self):
        name, accepted = QInputDialog.getText(
            self, "שמירת מיקום", "שם המיקום המועדף:")
        if not accepted:
            return
        try:
            saved = save_favorite(
                name, self.lat.value(), self.lon.value(), self.tz.text().strip())
            self._favorites = saved
            if self.city.findText(name) < 0:
                self.city.addItem(name)
            self.city.setCurrentText(name)
        except Exception as exc:
            QMessageBox.warning(self, "שמירת מיקום מועדף", str(exc))

    def _calculate(self):
        self._invalidate_chart()
        self._active_record = None
        try:
            if self.city.currentText() != MANUAL_LABEL and resolve_location(
                    self.city.currentText(),
                    {**self._favorites, **self._session_locations}) is None:
                raise ValueError("בחר מיקום מוכר או השתמש בהזנה ידנית")
            if self.date_mode.currentData() in ("hebrew", "mixed") and self.unknown.isChecked():
                raise ValueError("לתאריך עברי בחר יום/לילה ושעה בקירוב")
            resolved = self._resolved_input()
            if self.calc is None:
                self.calc = Calculator()
            day = resolved.civil_day
            hour = resolved.local_time
            zone = self.tz.text().strip()
            latitude, longitude = self.lat.value(), self.lon.value()
            phase_warning = None
            if self.date_mode.currentData() in ("hebrew", "mixed"):
                altitude = sun_altitude(
                    self.calc, day, hour, zone, latitude, longitude)
                phase_warning = validate_phase_sun(resolved.phase, altitude)
            chart = self.calc.calculate(
                day, hour, zone, latitude, longitude, self.unknown.isChecked())
            if phase_warning:
                chart.warnings.append(phase_warning)
            if self.approx_hour.isChecked() and not self.unknown.isChecked():
                chart.time_certainty = "estimated"
                for body in chart.bodies:
                    body.degree_certainty = "estimated"
                    body.sign_certainty = "estimated"
                for aspect in chart.aspects:
                    aspect.certainty = "estimated"
                chart.warnings.append(
                    "שעת הלידה משוערת. המעלות, האופק, רום השמיים, "
                    "הבתים וההיבטים חושבו לפי שעה זו בלבד; "
                    "ייתכנו שינויים כאשר השעה האמיתית שונה.")
            if self.date_mode.currentData() in ("hebrew", "mixed"):
                chart.warnings.insert(0, "המרת תאריך עברי: " + resolved.label)
            record = make_record(self._capture_input(), __version__)
            self._show_chart(chart)
            self._active_record = record
        except Exception as exc:
            QMessageBox.warning(self, "לא ניתן לחשב", str(exc))

    def _show_chart(self, chart):
        if self._aspect_dialog is not None:
            self._aspect_dialog.close()
            self._aspect_dialog = None
        self._active_chart = chart
        self.aspect_explorer_button.setEnabled(True)
        self._interpretation_chart = chart
        self.copy_button.setEnabled(True)
        self.wheel_legend.setText("לחץ על סמל במפה כדי לבחור גוף")
        self.interpret_button.setEnabled(True)
        self.chart_caption.setText(
            f"{len(chart.bodies)} גופים · " +
            {"known": "מפה מחושבת", "estimated": "שעה משוערת",
             "unknown": "שעה לא ידועה"}[chart.time_certainty])
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(chart.bodies))
        for row, b in enumerate(chart.bodies):
            signs = (" / ".join(SIGNS[i] for i in b.signs_possible)
                     if chart.approximate and b.signs_possible else b.sign)
            motion = "לא ודאי" if b.motion_uncertain else ("נסיגה" if b.retrograde else "ישירה")
            values = [
                b.name, signs,
                f"{degree_in_sign(b.longitude):.3f}°" + (
                    " (דגימה)" if chart.time_certainty == "unknown"
                    else " (משוער)" if chart.time_certainty == "estimated" else ""),
                "—" if b.house is None else
                f"{b.house} (משוער)" if chart.time_certainty == "estimated"
                else str(b.house), motion
            ]
            tooltip = format_body_label(chart, b, digits=3)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.table.setItem(row, column, item)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)
        self.aspects.setPlainText("\n".join(
            f"{a.first} – {a.second}: {a.kind}, מרחק {a.separation:.2f}°, סטייה {a.orb:.2f}°"
            + (" (דגימה בלבד; לא היבט לידה)" if chart.time_certainty == "unknown"
               else " (לפי שעה משוערת)" if a.certainty == "estimated" else "")
            for a in chart.aspects))
        angles = "" if chart.ascendant is None else (
            f"\nאופק: {chart.ascendant:.3f}° | MC: {chart.mc:.3f}°"
            f" | ציר נגדי: {chart.descendant:.3f}°")
        self.warnings.setText("\n".join(chart.warnings) + angles)
        self.wheel.set_chart(chart)

    def _open_aspect_explorer(self):
        if self._active_chart is None:
            return
        if self._aspect_dialog is not None:
            self._aspect_dialog.close()
        dialog = AspectExplorerDialog(self._active_chart, self)
        dialog.aspectSelected.connect(self.wheel.set_selected_aspect_pair)
        self._aspect_dialog = dialog
        dialog.show()
        dialog.raise_()

    def _on_table_selection(self, row, column, previous_row, previous_column):
        chart = self._active_chart
        if chart is None or row < 0 or row >= self.table.rowCount():
            self.wheel.set_selected_body(None)
            self.wheel_legend.setText("לחץ על סמל במפה כדי לבחור גוף")
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        body = next((b for b in chart.bodies if b.name == item.text()), None)
        if body is None:
            return
        self.wheel.set_selected_body(body.name)
        self.wheel_legend.setText(format_body_label(chart, body, digits=1))

    def _on_wheel_selection(self, name):
        if self._active_chart is None:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.text() == name:
                self.table.setCurrentCell(row, 0)
                return

    def _copy_report(self):
        if self._active_chart is None:
            return
        QApplication.clipboard().setText(format_chart_report(self._active_chart))
        self.chart_caption.setText("התקציר הועתק ללוח")

    def _capture_input(self):
        resolved = self._resolved_input()
        raw_day = self.day.date()
        clock = resolved.local_time
        mixed = self.date_mode.currentData() == "mixed"
        selected_year = self.hebrew_year.value()
        if mixed:
            candidate = next((option for option in mixed_candidates(
                self.mixed_year.value(), self.hebrew_month.currentData(),
                self.hebrew_day.value(), self.phase.currentData(), clock)
                if option.key == resolved.civil_day.isoformat()), None)
            if candidate is None:
                raise ValueError("לא ניתן לשמור תאריך מעורב לא מוכרע")
            selected_year = candidate.hebrew_year
        return {
            "date_mode": self.date_mode.currentData(),
            "civil_date": resolved.civil_day.isoformat(),
            "clock": None if self.unknown.isChecked() else clock.strftime("%H:%M"),
            "gregorian_date": (date(self.mixed_year.value(), 1, 1).isoformat()
                               if mixed else date(raw_day.year(), raw_day.month(), raw_day.day()).isoformat()),
            "hebrew_year": selected_year,
            "hebrew_month": int(self.hebrew_month.currentData()),
            "hebrew_day": self.hebrew_day.value(),
            "phase": self.phase.currentData(),
            "unknown_time": self.unknown.isChecked(),
            "estimated_time": self.approx_hour.isChecked() and not self.unknown.isChecked(),
            "city": self.city.currentText(),
            "latitude": self.lat.value(),
            "longitude": self.lon.value(),
            "zone": self.tz.text().strip(),
        }

    def _require_current_chart(self):
        if self._active_chart is None or self._active_record is None:
            raise ValueError("יש לחשב מפה תקינה לפני שמירה או ייצוא")
        if self._capture_input() != self._active_record["input"]:
            raise ValueError("הקלט השתנה מאז החישוב. יש לחשב מחדש לפני שמירה או ייצוא")
        return self._active_chart, self._active_record

    def _save_chart(self, save_as=False):
        try:
            chart, record = self._require_current_chart()
            selected = None if save_as else self._current_file
            if not selected:
                selected, _ = QFileDialog.getSaveFileName(
                    self, "שמור מפה מקומית", "", "AstroBirthChart (*.astrochart.json);;JSON (*.json)")
            if not selected:
                return
            path = Path(selected)
            if not path.name.endswith(".json"):
                path = path.with_name(path.name + ".astrochart.json")
            save_record(path, record)
            self._current_file = str(path)
            self.chart_caption.setText("המפה נשמרה במחשב")
        except Exception as exc:
            QMessageBox.warning(self, "שמירת מפה", str(exc))

    def _restore_input(self, values):
        # Load only validated primitive values; all result fields are recomputed.
        self.date_mode.setCurrentIndex(self.date_mode.findData("gregorian"))
        self.day.setDate(QDate.fromString(values["gregorian_date"], "yyyy-MM-dd"))
        self.mixed_year.setValue(date.fromisoformat(values["gregorian_date"]).year)
        self.hebrew_year.setValue(values["hebrew_year"])
        month_index = self.hebrew_month.findData(values["hebrew_month"])
        if month_index < 0:
            raise ValueError("החודש השמור אינו קיים בשנה העברית")
        self.hebrew_month.setCurrentIndex(month_index)
        self.hebrew_day.setValue(values["hebrew_day"])
        self.phase.setCurrentIndex(self.phase.findData(values["phase"]))
        city = values["city"]
        if city != MANUAL_LABEL and resolve_location(
                city, {**self._favorites, **self._session_locations}) is None:
            # Portably restore a user-defined location from the saved chart,
            # without persisting it to the favorites catalogue.
            self._session_locations[city] = (
                values["latitude"], values["longitude"], values["zone"])
            if self.city.findText(city) < 0:
                self.city.addItem(city)
        self.city.setCurrentText(city)
        self.lat.setValue(values["latitude"])
        self.lon.setValue(values["longitude"])
        self.tz.setText(values["zone"])
        self.date_mode.setCurrentIndex(self.date_mode.findData(values["date_mode"]))
        if values["clock"] is not None:
            self.hour.setTime(QTime.fromString(values["clock"], "HH:mm"))
        if values["date_mode"] == "mixed":
            self._refresh_mixed_choices()
            index = self.mixed_choice.findData(values["civil_date"])
            if index < 0:
                raise ValueError("התאריך המעורב השמור אינו זמין")
            self.mixed_choice.setCurrentIndex(index)
        self.unknown.setChecked(values["unknown_time"])
        self.approx_hour.setChecked(values["estimated_time"])

    def _open_chart(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "פתח מפה מקומית", "", "AstroBirthChart (*.astrochart.json *.json)")
        if not selected:
            return
        try:
            record = read_record(selected)
            self._restore_input(record["input"])
            restored = self._capture_input()
            if restored != record["input"]:
                raise ValueError("בחירות התאריך או המיקום אינן ניתנות לשחזור מדויק")
            self._calculate()
            if self._active_record is None:
                raise ValueError("חישוב מחדש של הקובץ נכשל")
            self._current_file = selected
            if (record["app_version"] != __version__ or
                    record["tzdata_version"] != self._active_record["tzdata_version"]):
                QMessageBox.information(
                    self, "חישוב מחדש",
                    "גרסת התוכנה או נתוני אזורי הזמן השתנתה. המפה חושבה מחדש; "
                    "לא הובטח שחזור מספרי זהה לקובץ הקודם.")
        except Exception as exc:
            QMessageBox.warning(self, "פתיחת מפה", str(exc))

    def _export_chart(self, kind):
        try:
            chart, record = self._require_current_chart()
            suffix = {"json": ".json", "txt": ".txt",
                      "png": ".png", "pdf": ".pdf", "pdf_tables": ".pdf"}[kind]
            filters = {"json": "JSON (*.json)", "txt": "Text (*.txt)",
                        "png": "PNG (*.png)", "pdf": "PDF (*.pdf)", "pdf_tables": "PDF (*.pdf)"}
            selected, _ = QFileDialog.getSaveFileName(
                self, "ייצא מפה", "", filters[kind])
            if not selected:
                return
            destination = Path(selected)
            if destination.suffix.lower() != suffix:
                destination = destination.with_name(destination.name + suffix)
            if kind == "json":
                payload = export_results(chart, record)
                destination.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n", encoding="utf-8")
            elif kind == "txt":
                destination.write_text(format_chart_report(chart), encoding="utf-8")
            elif kind == "png":
                export_wheel_png(self.wheel, destination)
            elif kind == "pdf_tables":
                export_chart_tables_pdf(chart, destination, metadata=record["input"])
            else:
                export_chart_pdf(self.wheel, chart, destination)
            self.chart_caption.setText("הייצוא הושלם במחשב")
        except Exception as exc:
            QMessageBox.warning(self, "ייצוא מפה", str(exc))

    def _open_interpretation(self):
        if self._interpretation_chart is None:
            return
        from .interpretation_dialog import RuleInterpretationDialog
        dialog = RuleInterpretationDialog(self._interpretation_chart, self)
        dialog.exec()
