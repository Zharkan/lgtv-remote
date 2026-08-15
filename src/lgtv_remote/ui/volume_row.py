from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from lgtv_remote.protocols import TvState


class VolumeRowWidget(QWidget):
    volume_changed = Signal(int)
    mute_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        header = QLabel("VOLUME")
        header.setFont(self._section_font())
        header.setObjectName("volumeLabel")
        top_row.addWidget(header)
        top_row.addStretch()

        self._vol_label = QLabel("0")
        self._vol_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        vol_font = QFont()
        vol_font.setPointSize(18)
        vol_font.setBold(True)
        self._vol_label.setFont(vol_font)
        top_row.addWidget(self._vol_label)
        layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self._mute_btn = QPushButton("\U0001f50a")
        self._mute_btn.setObjectName("muteButton")
        self._mute_btn.setFixedSize(36, 36)
        self._mute_btn.setCheckable(True)
        self._mute_btn.setToolTip("Mute")
        bottom_row.addWidget(self._mute_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(0)
        bottom_row.addWidget(self._slider)

        self._vol_down = QPushButton("−")
        self._vol_down.setObjectName("volButton")
        self._vol_down.setFixedSize(36, 36)
        self._vol_down.setToolTip("Volume down")
        bottom_row.addWidget(self._vol_down)

        self._vol_up = QPushButton("+")
        self._vol_up.setObjectName("volButton")
        self._vol_up.setFixedSize(36, 36)
        self._vol_up.setToolTip("Volume up")
        bottom_row.addWidget(self._vol_up)

        layout.addLayout(bottom_row)

        self._slider.sliderReleased.connect(self._on_slider_released)
        self._vol_down.clicked.connect(lambda: self._step_volume(-2))
        self._vol_up.clicked.connect(lambda: self._step_volume(2))
        self._mute_btn.toggled.connect(self._on_mute_toggled)

    @staticmethod
    def _section_font() -> QFont:
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        return f

    def update_state(self, state: TvState) -> None:
        vol = getattr(state, "volume", None)
        muted = getattr(state, "muted", None)
        self._updating = True
        if vol is not None:
            self._slider.setValue(vol)
            self._vol_label.setText(str(vol))
        if muted is not None:
            self._mute_btn.setChecked(muted)
            self._mute_btn.setText(
                "\U0001f507" if muted else "\U0001f50a"
            )
        self._updating = False

    def set_enabled_state(self, enabled: bool) -> None:
        self._slider.setEnabled(enabled)
        self._vol_down.setEnabled(enabled)
        self._vol_up.setEnabled(enabled)
        self._mute_btn.setEnabled(enabled)

    def _on_slider_released(self) -> None:
        if not self._updating:
            val = self._slider.value()
            self._vol_label.setText(str(val))
            self.volume_changed.emit(val)

    def _step_volume(self, delta: int) -> None:
        new = max(0, min(100, self._slider.value() + delta))
        self._slider.setValue(new)
        self._vol_label.setText(str(new))
        if not self._updating:
            self.volume_changed.emit(new)

    def _on_mute_toggled(self, checked: bool) -> None:
        if not self._updating:
            self.mute_toggled.emit(checked)
