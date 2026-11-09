"""Read-only offline viewer for prototype symbolic interpretation.

The dialog never changes the astronomical calculation or transmits birth data.
"""
import json

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .interpretation import (
    format_interpretation, interpret_chart, model_input,
)
from .synthesis import format_synthesis, synthesize
from .narrative import compose_narrative, format_narrative
from .semantics_n2 import build_personality_model
from .narrative_n2 import compose_narrative_n2, format_narrative_n2
from .local_llm import generate_local_n2, LocalModelError


class _LocalN2Worker(QThread):
    produced = Signal(str)
    failed = Signal(str)

    def __init__(self, narrative, port, parent=None):
        super().__init__(parent)
        self.narrative = narrative
        self.port = port

    def run(self):
        try:
            text = generate_local_n2(self.narrative, port=self.port)
        except LocalModelError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("שגיאה לא צפויה בהפעלת המודל המקומי")
        else:
            self.produced.emit(text)


class RuleInterpretationDialog(QDialog):
    def __init__(self, chart, parent=None, pack=None):
        super().__init__(parent)
        self.setWindowTitle("פרשנות אופי אסטרולוגית — גרסת ניסוי")
        self.setMinimumSize(670, 510)
        self.resize(790, 625)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.report = interpret_chart(chart, pack)
        self.synthesis_report = synthesize(chart, self.report)
        self.narrative_report = compose_narrative(self.synthesis_report)
        self.semantic_n2_report = build_personality_model(self.synthesis_report, self.report)
        self.narrative_n2_report = compose_narrative_n2(self.semantic_n2_report)
        self.structured_payload = {
            **model_input(chart, self.report),
            "synthesis": self.synthesis_report,
            "narrative": self.narrative_report,
            "personality_n2": {"semantics": self.semantic_n2_report,
                               "narrative": self.narrative_n2_report},
        }
        self.readable = format_interpretation(self.report)
        self.synthesis_readable = format_synthesis(self.synthesis_report)
        self.narrative_readable = format_narrative(self.narrative_report)
        self.narrative_n2_readable = format_narrative_n2(self.narrative_n2_report)
        self._local_worker = None

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
        self.n2_view = QTextEdit()
        self.n2_view.setObjectName("interpretationPersonalN2")
        self.n2_view.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.n2_view.setReadOnly(True)
        self.n2_view.setPlainText(self.narrative_n2_readable)
        self.tabs.addTab(self.n2_view, "פרשנות אישית (N2)")
        self.local_view = QTextEdit()
        self.local_view.setObjectName("interpretationLocalDicta")
        self.local_view.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.local_view.setReadOnly(True)
        self.local_view.setPlainText(
            "המודל המקומי אינו מופעל אוטומטית. אפשר לבקש ניסוח עברי "
            "של פרשנות N2 בלבד, לאחר אישור מפורש. הפרשנות המקורית נשמרת.")
        self.tabs.addTab(self.local_view, "ניסוח Dicta מקומי")
        self.narrative_view = QTextEdit()
        self.narrative_view.setObjectName("interpretationNarrative")
        self.narrative_view.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.narrative_view.setReadOnly(True)
        self.narrative_view.setPlainText(self.narrative_readable)
        self.tabs.addTab(self.narrative_view, "קריאה רציפה (N1)")
        self.synthesis_view = QTextEdit()
        self.synthesis_view.setObjectName("interpretationSynthesis")
        self.synthesis_view.setReadOnly(True)
        self.synthesis_view.setPlainText(self.synthesis_readable)
        self.tabs.addTab(self.synthesis_view, "סינתזה — תמונה כללית")
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
        self.proof_view = QTextEdit()
        self.proof_view.setObjectName("interpretationSynthesisProof")
        self.proof_view.setReadOnly(True)
        self.proof_view.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.proof_view.setPlainText(json.dumps({
            "nodes": self.synthesis_report["nodes"],
            "factor_conditions": self.synthesis_report["factor_conditions"],
            "tensions": self.synthesis_report["tensions"],
            "top_feature_ids": self.synthesis_report["top_feature_ids"],
        }, ensure_ascii=False, indent=2))
        self.tabs.addTab(self.proof_view, "שרשראות הסקה")
        self.payload = QTextEdit()
        self.payload.setReadOnly(True)
        self.payload.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.payload.setObjectName("interpretationModelData")
        self.payload.setPlainText(
            json.dumps(self.structured_payload, ensure_ascii=False, indent=2))
        self.tabs.addTab(self.payload, "מבנה נתונים למודל")
        layout.addWidget(self.tabs, 1)
        model_controls = QHBoxLayout()
        model_controls.addWidget(QLabel("יציאת llama-server:"))
        self.local_port = QSpinBox()
        self.local_port.setObjectName("localDictaPort")
        self.local_port.setRange(1, 65535)
        self.local_port.setValue(8080)
        model_controls.addWidget(self.local_port)
        self.local_generate_button = QPushButton("נסח עם Dicta המקומי")
        self.local_generate_button.setObjectName("localDictaGenerate")
        self.local_generate_button.clicked.connect(self._start_local_generation)
        model_controls.addWidget(self.local_generate_button)
        self.local_copy_button = QPushButton("העתק ניסוח Dicta")
        self.local_copy_button.setObjectName("localDictaCopy")
        self.local_copy_button.setEnabled(False)
        self.local_copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.local_view.toPlainText()))
        model_controls.addWidget(self.local_copy_button)
        self.local_status = QLabel("לא נוצר חיבור למודל")
        self.local_status.setObjectName("localDictaStatus")
        self.local_status.setWordWrap(True)
        model_controls.addWidget(self.local_status, 1)
        layout.addLayout(model_controls)
        buttons = QHBoxLayout()
        self.copy_n2_button = QPushButton("העתק פרשנות אישית N2")
        self.copy_n2_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.narrative_n2_readable))
        buttons.addWidget(self.copy_n2_button)
        self.copy_narrative_button = QPushButton("העתק קריאה רציפה")
        self.copy_narrative_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.narrative_readable))
        buttons.addWidget(self.copy_narrative_button)
        self.copy_synthesis_button = QPushButton("העתק סינתזה")
        self.copy_synthesis_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.synthesis_readable))
        buttons.addWidget(self.copy_synthesis_button)
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
        self.close_button = close
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _start_local_generation(self):
        if self._local_worker is not None:
            return
        answer = QMessageBox.question(
            self, "חיבור למודל המקומי",
            "להעביר רק את טקסט הפרשנות הסמנטית של N2 אל "
            "llama-server ב־127.0.0.1? לא יישלחו תאריך לידה, מקום לידה "
            "או נתוני המפה הגולמיים. השתמש רק בשרת מקומי שאתה סומך עליו. "
            "הניסוח שיוחזר לא יאומת אוטומטית.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.local_copy_button.setEnabled(False)
        self.local_generate_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.local_status.setText("מנסח באמצעות מודל מקומי...")
        self.local_view.setPlainText("ממתין לתשובת המודל המקומי...")
        self.tabs.setCurrentWidget(self.local_view)
        self._local_worker = _LocalN2Worker(
            self.narrative_n2_report, self.local_port.value(), self)
        self._local_worker.produced.connect(self._local_generated)
        self._local_worker.failed.connect(self._local_failed)
        self._local_worker.finished.connect(self._local_finished)
        self._local_worker.start()

    def _local_generated(self, text):
        self.local_view.setPlainText(
            "ניסוח בעזרת מודל שפה מקומי — לא אומת אוטומטית. "
            "המקור המחייב הוא לשונית פרשנות אישית (N2). "
            "זו קריאה אסטרולוגית סמלית, לא אבחון מדעי.\n"
            + ("שעת הלידה אינה ידועה; אין לראות נתונים תלויי שעה כוודאיים.\n"
               if self.narrative_n2_report["time_mode"] == "unknown" else
               "שעת הלידה משוערת; נתונים תלויי שעה אינם ודאיים.\n"
               if self.narrative_n2_report["time_mode"] == "estimated" else "")
            + "\n" + text)
        self.local_copy_button.setEnabled(True)
        self.local_status.setText("הניסוח התקבל מ־llama-server המקומי")

    def _local_failed(self, message):
        self.local_view.setPlainText(
            "המודל המקומי לא השלים ניסוח. מוצג כאן המקור המקורי של N2:\n\n"
            + self.narrative_n2_readable)
        self.local_status.setText(message + " — N2 המקורי לא השתנה")

    def _local_finished(self):
        self.local_generate_button.setEnabled(True)
        self.close_button.setEnabled(True)
        worker = self._local_worker
        self._local_worker = None
        if worker is not None:
            worker.deleteLater()

    def reject(self):
        if self._local_worker is not None and self._local_worker.isRunning():
            self.local_status.setText(
                "הפעולה המקומית עדיין מתבצעת. הסגירה תתאפשר בסיומה.")
            return
        super().reject()

    def accept(self):
        if self._local_worker is not None and self._local_worker.isRunning():
            return
        super().accept()

    def closeEvent(self, event):
        if self._local_worker is not None and self._local_worker.isRunning():
            event.ignore()
            self.local_status.setText(
                "הפעולה המקומית עדיין מתבצעת. הסגירה תתאפשר בסיומה.")
            return
        super().closeEvent(event)
