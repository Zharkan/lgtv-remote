from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PinDialog(QDialog):
    def __init__(self, app_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PIN Required")
        self.setObjectName("pinDialog")
        self.setFixedSize(320, 200)
        self.pin = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel(f"Enter PIN for {app_name}")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("This app is locked with a PIN")
        subtitle.setStyleSheet("color: #7a9e94; font-size: 10px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self._pin_edit = QLineEdit()
        self._pin_edit.setMaxLength(4)
        self._pin_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{0,4}"), self)
        )
        self._pin_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_edit.setPlaceholderText("····")
        self._pin_edit.textChanged.connect(self._on_text_changed)
        self._pin_edit.returnPressed.connect(self._on_ok)
        layout.addWidget(self._pin_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._ok_btn = QPushButton("Unlock")
        self._ok_btn.setObjectName("pinOkButton")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(self._ok_btn)
        layout.addLayout(btn_row)

        self._pin_edit.setFocus()

    def _on_text_changed(self, text: str) -> None:
        self._ok_btn.setEnabled(len(text) == 4 and text.isdigit())

    def _on_ok(self) -> None:
        text = self._pin_edit.text()
        if len(text) != 4 or not text.isdigit():
            return
        self.pin = text
        self.accept()
