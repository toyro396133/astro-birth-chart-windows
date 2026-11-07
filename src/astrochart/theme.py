"""A self-contained, offline Qt visual theme for the Hebrew desktop UI.

No custom web views, image assets, fonts, downloads, or telemetry are used.
Object names intentionally scope visual changes to avoid platform-dialog regressions.
"""
APP_STYLE = r"""
QMainWindow, QWidget#rootSurface {
    background-color: #f1f5fb;
    color: #25364b;
    font-family: "Segoe UI", "Arial";
    font-size: 12px;
}
QFrame#appHeader {
    background-color: #142b49;
    border: 1px solid #142b49;
    border-radius: 16px;
}
QFrame#appHeader QLabel {
    background: transparent;
    border: none;
    color: #edf5ff;
}
QFrame#appHeader QLabel#appTitle {
    font-size: 23px;
    font-weight: 750;
    color: #ffffff;
}
QFrame#appHeader QLabel#appSubtitle {
    font-size: 11px;
    color: #c0d3e9;
}
QFrame#appHeader QLabel#versionPill {
    border: 1px solid #45637e;
    background-color: #213d5c;
    border-radius: 11px;
    padding: 5px 10px;
    font-size: 11px;
    color: #d9eafe;
}
QFrame#appHeader QLabel#updateStatus {
    color: #b8d7f4;
    font-size: 11px;
}
QFrame#appHeader QCheckBox {
    color: #e4effc;
    spacing: 7px;
    font-size: 11px;
}
QFrame#appHeader QCheckBox::indicator {
    width: 15px;
    height: 15px;
}
QFrame#appHeader QPushButton#updateButton {
    color: #ddecfc;
    border: 1px solid #57708d;
    border-radius: 8px;
    background: #284866;
    min-height: 28px;
    padding: 4px 12px;
}
QFrame#appHeader QPushButton#updateButton:hover {
    background: #376080;
    border-color: #8ac2f2;
}
QFrame#appHeader QPushButton#updateButton:disabled {
    color: #8da5c1;
    background: #223b55;
}
QFrame#updatePanel {
    background-color: #e8f2ff;
    border: 1px solid #bcd8f4;
    border-radius: 9px;
}
QFrame#updatePanel QLabel#latestUpdateLabel {
    color: #204d81;
    font-weight: 650;
    font-size: 11px;
}
QFrame#updatePanel QCheckBox {
    color: #284e7b;
    font-size: 11px;
}
QFrame#updatePanel QPushButton {
    color: #ffffff;
    background-color: #2766aa;
    border: 1px solid #2766aa;
    border-radius: 7px;
    min-height: 26px;
    padding: 3px 10px;
    font-size: 11px;
}
QFrame#updatePanel QPushButton:hover { background-color: #1e528c; }
QFrame#updatePanel QPushButton:disabled {
    color: #7690b1;
    background-color: #eef3fa;
    border-color: #cddceb;
}
QGroupBox#inputCard {
    border: 1px solid #e2eaf4;
    border-radius: 15px;
    background-color: #ffffff;
    margin-top: 7px;
    padding-top: 7px;
    font-weight: normal;
}
QGroupBox#inputCard::title {
    subcontrol-origin: margin;
    subcontrol-position: top right;
    margin-right: 17px;
    padding: 0px 8px;
    color: #26446a;
    font-size: 13px;
    font-weight: 700;
    background-color: #ffffff;
}
QFrame#panelCard {
    border: 1px solid #e2eaf4;
    border-radius: 15px;
    background-color: #ffffff;
}
QFrame#panelCard QLabel {
    border: none;
    background: transparent;
}
QLabel#sectionTitle {
    color: #203a5b;
    font-size: 14px;
    font-weight: 750;
    background-color: transparent;
}
QLabel#helperText {
    color: #7689a3;
    font-size: 10px;
    background-color: transparent;
}
QLabel#fieldLabel {
    color: #586d88;
    font-size: 11px;
    background: transparent;
}
QLabel#conversionInfo {
    color: #225f90;
    font-size: 11px;
    font-weight: 600;
}
QLabel#noteTitle {
    color: #526984;
    font-size: 11px;
    font-weight: 700;
}
QLabel#warningText {
    color: #a75c26;
    font-size: 10px;
    line-height: 1.3;
    background: transparent;
}
QComboBox, QDateEdit, QTimeEdit, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #f7faff;
    color: #233d58;
    border: 1px solid #d9e4f0;
    border-radius: 7px;
    min-height: 20px;
    padding: 2px 7px;
    selection-background-color: #377bd1;
}
QComboBox:hover, QDateEdit:hover, QTimeEdit:hover, QSpinBox:hover,
QDoubleSpinBox:hover, QLineEdit:hover {
    border: 1px solid #99bddd;
    background: #ffffff;
}
QComboBox:focus, QDateEdit:focus, QTimeEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border: 1px solid #347ad1;
    background: #ffffff;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #263f60;
    border: 1px solid #c7d9ef;
    selection-background-color: #d9eaff;
    selection-color: #193a62;
    padding: 4px;
    outline: 0;
}
QCheckBox {
    color: #465d7a;
    spacing: 7px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
}
QPushButton#calculateButton {
    color: white;
    background-color: #2369c4;
    font-size: 13px;
    font-weight: 700;
    border: 1px solid #2369c4;
    border-radius: 9px;
    min-height: 30px;
    padding: 5px 18px;
}
QPushButton#calculateButton:hover {
    background-color: #1b539e;
    border-color: #1b539e;
}
QPushButton#calculateButton:pressed {
    background-color: #153e77;
}
QPushButton#interpretationButton {
    color: #244f85;
    background-color: #eef6ff;
    border: 1px solid #b7d1ee;
    border-radius: 8px;
    padding: 4px 9px;
    font-weight: 650;
    font-size: 11px;
    min-height: 23px;
}
QPushButton#interpretationButton:hover {
    background-color: #dbeafa;
    border-color: #6d9dcc;
}
QPushButton#interpretationButton:disabled {
    color: #98a9bc;
    background: #f5f8fc;
    border-color: #e1e8f0;
}
QPushButton#advancedToggle {
    color: #2b619a;
    border: none;
    background: transparent;
    text-align: right;
    font-weight: 650;
    padding: 3px 2px;
}
QPushButton#advancedToggle:hover { color: #164b86; }
QFrame#advancedPanel {
    background-color: #f7faff;
    border: 1px solid #e4edf7;
    border-radius: 8px;
}
QTableWidget#bodyTable {
    color: #263b53;
    background-color: #ffffff;
    alternate-background-color: #f6f9fe;
    gridline-color: #e9eef6;
    selection-background-color: #dcecff;
    selection-color: #193a62;
    border: 1px solid #e5ecf6;
    border-radius: 8px;
    font-size: 11px;
}
QTableWidget#bodyTable QHeaderView::section {
    background-color: #eff5fc;
    border: none;
    border-left: 1px solid #e1e9f4;
    border-bottom: 1px solid #dee9f6;
    color: #385474;
    font-size: 11px;
    font-weight: 750;
    padding: 4px 3px;
}
QTextEdit#aspectText {
    color: #354d6d;
    font-size: 11px;
    background-color: #f8faff;
    border: 1px solid #e6edf6;
    border-radius: 8px;
    padding: 4px 6px;
    selection-background-color: #dcecff;
}
QScrollArea#warningScroll {
    background-color: #fff9f2;
    border: 1px solid #f2e7d8;
    border-radius: 8px;
}
QWidget#warningContents {
    background-color: #fff9f2;
}
QSplitter::handle {
    background: transparent;
    width: 8px;
}
QScrollBar:vertical {
    background: #f4f7fb;
    width: 9px;
    margin: 1px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #c5d5e6;
    border-radius: 4px;
    min-height: 22px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def apply_theme(window):
    """Apply on the main window only; native dialogs keep platform defaults."""
    window.setStyleSheet(APP_STYLE)
