from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPaintEvent, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from lgtv_remote.constants import HDMI_APP_PREFIX
from lgtv_remote.protocols import TvState

_KNOWN_APPS = {
    "com.webos.app.home": "Home",
    "com.webos.app.livetv": "TV Tuner",
    "com.webos.app.browser": "Web Browser",
    "com.webos.app.mediadiscovery": "Media Player",
    "com.webos.app.photovideo": "Photos & Videos",
    "com.webos.app.music": "Music",
    "com.webos.app.settings": "Settings",
    "com.webos.app.notificationcenter": "Notifications",
    "com.webos.app.connectionwizard": "Connection Wizard",
    "com.webos.app.miracast": "Screen Share",
    "com.webos.app.camera": "Camera",
}


class _ScreenshotFrame(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._screenshot: QPixmap | None = None

    def set_screenshot(self, pixmap: QPixmap) -> None:
        self._screenshot = pixmap
        self.update()

    def clear_screenshot(self) -> None:
        self._screenshot = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self._screenshot is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        p.setClipPath(clip)

        p.setOpacity(0.25)
        scaled = self._screenshot.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - self.width()) // 2
        y = (scaled.height() - self.height()) // 2
        p.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
        p.end()


class NowPlayingCard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_app_id: str | None = None
        self._apps: dict[str, Any] = {}
        self._inputs: dict[str, Any] = {}

        self._frame = _ScreenshotFrame(self)
        self._frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._frame.setObjectName("nowPlayingFrame")
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(16, 14, 16, 14)
        self._title_label = QLabel("No input")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        frame_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("")
        sub_font = QFont()
        sub_font.setPointSize(10)
        self._subtitle_label.setFont(sub_font)
        self._subtitle_label.setObjectName("nowPlayingSub")
        frame_layout.addWidget(self._subtitle_label)

        self._port_label = QLabel("")
        port_font = QFont()
        port_font.setPointSize(9)
        self._port_label.setFont(port_font)
        self._port_label.setObjectName("nowPlayingPort")
        frame_layout.addWidget(self._port_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._frame)

    def set_screenshot(self, pixmap: QPixmap) -> None:
        self._frame.set_screenshot(pixmap)

    def clear_screenshot(self) -> None:
        self._frame.clear_screenshot()

    def update_state(self, state: TvState) -> None:
        self._apps = state.apps or {}
        self._inputs = state.inputs or {}
        app_id = state.current_app_id
        self._current_app_id = app_id
        self._refresh_display()

    def set_stale(self, stale: bool) -> None:
        self.setProperty("stale", stale)
        self.style().unpolish(self)
        self.style().polish(self)

    def _refresh_display(self) -> None:
        app_id = self._current_app_id
        if not app_id:
            self._title_label.setText("No input")
            self._subtitle_label.setText("")
            self._port_label.setText("")
            return

        title, subtitle, port_info = self._resolve_labels(app_id)
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)
        self._port_label.setText(port_info)

    def _resolve_labels(self, app_id: str) -> tuple[str, str, str]:
        is_hdmi = app_id.startswith(HDMI_APP_PREFIX)

        if is_hdmi:
            num = app_id.replace(HDMI_APP_PREFIX, "")
            port_name = f"HDMI {num}"
            user_label = ""
            connected = False
            detail_parts: list[str] = []

            if app_id in self._inputs:
                inp = self._inputs[app_id]
                user_label = inp.get("label", "")
                connected = inp.get("connected", False)

                device_type = inp.get("spdSourceDeviceInfo", "")
                if device_type:
                    type_map = {
                        "GAME": "Game Console",
                        "RECORDING": "Recorder",
                        "TUNER": "Tuner",
                        "PLAYBACK": "Player",
                    }
                    detail_parts.append(type_map.get(device_type, device_type))

                if connected:
                    detail_parts.append("Connected")

            if user_label and user_label != port_name:
                title = user_label
                subtitle = f"ACTIVE · {port_name}"
            else:
                title = port_name
                subtitle = "ACTIVE SOURCE"

            detail = " · ".join(detail_parts)
            return title, subtitle, detail

        if app_id == "com.webos.app.livetv":
            return "TV Tuner", "ACTIVE · Live TV", ""

        app_title = app_id
        if app_id in self._apps:
            app_title = self._apps[app_id].get("title", app_id)
        elif app_id in _KNOWN_APPS:
            app_title = _KNOWN_APPS[app_id]
        return app_title, "APPLICATION", app_id if app_title != app_id else ""

