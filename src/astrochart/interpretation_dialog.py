"""Read-only offline viewer for prototype symbolic interpretation.

The dialog never changes the astronomical calculation or transmits birth data.
"""
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .interpretation import (
    format_interpretation, interpret_chart, model_input,
)


class RuleInterpretationDialog(QDialog):
    def __init__(self, chart, parent=None, pack=None):
        super().__init__(parent)
        self.setWindowTitle("פרשנות אופי אסטרולוגית — גרסת ניסוי")
        self.setMinimumSize(670, 510)
        self.resize(790, 625)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.report = interpret_chart(chart, pack)
        self.structured_payload = model_input(chart, self.report)
        self.readable = format_interpretation(self.report)

        layout = QVBoxLayout(self)
        header = QLabel(
            "פרשנות סמלית על סמך כללי המפה — לא אבחון אופי מדעי"
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #25466e; padding: 6px;")
        layout.addWidget(header)
        version = QLabel(
            f"חבילת כללים {self.report['pack_version']} · "
            f"{len(self.report['signals'])} התאמות · "
            f"{len(self.report['axes'])} צירים")
        version.setObjectName("rulePackStatus")
        version.setStyleSheet("color: #627b96; padding: 2px 6px;")
        layout.addWidget(version)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("interpretationTabs")
        self.summary = QTextEdit()
        self.summary.setObjectName("interpretationSummary")
        self.summary.setReadOnly(True)
        self.summary.setPlainText(self.readable)
        self.tabs.addTab(self.summary, "פרשנות")
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setObjectName("interpretationEvidence")
        detail_lines = []
        for hit in self.report["signals"]:
            detail_lines.extend([
                f"כלל: {hit['rule_id']}",
                f"ציר: {hit['axis']} | משקל עריכתי: {hit['weight']}",
                f"נתון תומך: {hit['evidence']}",
                f"משמעות: {hit['text']}",
                f"סטטוס ביקורת: {hit.get('review_status', 'unverified')}",
                f"קבוצת ראיה: {hit.get('evidence_key', '')}",
                "השלמה מותנית — ללא משקל נפרד" if hit.get("modifier_only") else "",
                f"מקור: {hit['source']}",
                f"קישור למקור: {hit.get('source_url') or 'טרם אומת'}",
                "",
            ])
        self.details.setPlainText(
            "\n".join(detail_lines) if detail_lines else "אין התאמות בחבילת הכללים הנוכחית.")
        self.tabs.addTab(self.details, "מקורות והנמקות")
        self.payload = QTextEdit()
        self.payload.setReadOnly(True)
        self.payload.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.payload.setObjectName("interpretationModelData")
        self.payload.setPlainText(
            json.dumps(self.structured_payload, ensure_ascii=False, indent=2))
        self.tabs.addTab(self.payload, "מבנה נתונים למודל")
        layout.addWidget(self.tabs, 1)
        buttons = QHBoxLayout()
        self.copy_text_button = QPushButton("העתק פרשנות")
        self.copy_text_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.readable))
        buttons.addWidget(self.copy_text_button)
        self.copy_json_button = QPushButton("העתק נתונים מובנים")
        self.copy_json_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.payload.toPlainText()))
        buttons.addWidget(self.copy_json_button)
        buttons.addStretch(1)
        close = QPushButton("סגור")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
