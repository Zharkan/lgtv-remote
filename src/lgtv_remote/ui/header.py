from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lgtv_remote.config import ConfigStore
from lgtv_remote.connection import ConnectionState
from lgtv_remote.protocols import TvState

_STATE_LABELS = {
    ConnectionState.UNCONFIGURED: "No TV",
    ConnectionState.OFFLINE: "Offline",
    ConnectionState.CONNECTING: "Connecting…",
    ConnectionState.PAIRING: "Pairing…",
    ConnectionState.CONNECTED: "Connected",
}

_STATE_COLORS = {
    ConnectionState.CONNECTED: "#4caf50",
    ConnectionState.CONNECTING: "#ff9800",
    ConnectionState.PAIRING: "#2196f3",
    ConnectionState.OFFLINE: "#f44336",
    ConnectionState.UNCONFIGURED: "#9e9e9e",
}


class HeaderWidget(QWidget):
    power_clicked = Signal()
    tv_selected = Signal(str)
    settings_clicked = Signal()

    def __init__(self, config: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        label_col = QVBoxLayout()
        label_col.setSpacing(0)

        self._tv_subtitle = QLabel("LG WEBOS")
        sub_font = QFont()
        sub_font.setPointSize(8)
        sub_font.setBold(True)
        self._tv_subtitle.setFont(sub_font)
        self._tv_subtitle.setStyleSheet("color: #7a9e94;")
        label_col.addWidget(self._tv_subtitle)

        self._tv_label = QLabel("LG TV Remote")
        label_font = QFont()
        label_font.setPointSize(13)
        label_font.setBold(True)
        self._tv_label.setFont(label_font)
        self._tv_label.setMinimumWidth(80)
        self._tv_label.setMaximumWidth(220)
        label_col.addWidget(self._tv_label)

        layout.addLayout(label_col)

        self._status_pill = QLabel("Offline")
        self._status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_pill.setFixedHeight(22)
        self._status_pill.setMinimumWidth(86)
        self._update_pill(ConnectionState.UNCONFIGURED)
        layout.addWidget(self._status_pill)

        layout.addStretch()

        self._tv_combo = QComboBox()
        self._tv_combo.setMinimumWidth(120)
        self._refresh_tv_list()
        self._tv_combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._tv_combo)

        self._power_btn = QPushButton("⏻")
        self._power_btn.setObjectName("powerButton")
        self._power_btn.setFixedSize(36, 36)
        self._power_btn.setToolTip("Power on / off")
        power_font = QFont()
        power_font.setPointSize(14)
        self._power_btn.setFont(power_font)
        self._power_btn.clicked.connect(self.power_clicked.emit)
        layout.addWidget(self._power_btn)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("settingsButton")
        self._settings_btn.setFixedSize(36, 36)
        self._settings_btn.setToolTip("Settings")
        settings_font = QFont()
        settings_font.setPointSize(14)
        self._settings_btn.setFont(settings_font)
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self._settings_btn)

    def set_connection_state(self, state: ConnectionState) -> None:
        self._update_pill(state)

    def update_state(self, state: TvState) -> None:
        tv = self._config.active_tv
        if tv:
            self._tv_label.setText(tv.label)

    def refresh_tv_list(self) -> None:
        self._refresh_tv_list()

    def _refresh_tv_list(self) -> None:
        self._tv_combo.blockSignals(True)
        self._tv_combo.clear()
        for tv in self._config.config.tvs:
            self._tv_combo.addItem(tv.label, tv.id)
        active = self._config.active_tv
        if active:
            idx = self._tv_combo.findData(active.id)
            if idx >= 0:
                self._tv_combo.setCurrentIndex(idx)
        self._tv_combo.setVisible(len(self._config.config.tvs) > 1)
        self._tv_combo.blockSignals(False)

    def _on_combo_changed(self, index: int) -> None:
        tv_id = self._tv_combo.itemData(index)
        if tv_id:
            self.tv_selected.emit(tv_id)

    def _update_pill(self, state: ConnectionState) -> None:
        label = _STATE_LABELS.get(state, "Unknown")
        color = _STATE_COLORS.get(state, "#9e9e9e")
        self._status_pill.setText(label)
        self._status_pill.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 11px;"
            f" padding: 2px 10px; font-size: 11px; font-weight: bold;"
        )
