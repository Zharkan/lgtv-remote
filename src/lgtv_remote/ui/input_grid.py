from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from lgtv_remote.constants import HDMI_APP_PREFIX
from lgtv_remote.protocols import TvState
from lgtv_remote.ui.all_apps_dialog import AllAppsDialog
from lgtv_remote.ui.icon_cache import IconCache

_APP_CARD_SIZE = 90
_APP_CARD_SPACING = 6
_APP_ICON_SIZE = 40
_APP_ICON_RADIUS = 10


def _round_pixmap(pm: QPixmap, size: int, radius: int) -> QPixmap:
    scaled = pm.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(scaled.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, scaled.width(), scaled.height(), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled)
    p.end()
    return out


class InputGridWidget(QWidget):
    app_clicked = Signal(str)

    def __init__(self, icon_cache: IconCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_cache = icon_cache
        self._buttons: dict[str, QPushButton] = {}
        self._icon_labels: dict[str, QLabel] = {}
        self._current_app_id: str | None = None
        self._all_apps: list[dict[str, Any]] = []
        self._last_apps: dict[str, Any] = {}
        self._last_inputs: dict[str, Any] = {}
        self._last_visible_count: int = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 0, 8, 0)
        outer.setSpacing(4)

        inputs_header = QLabel("INPUTS")
        inputs_header.setFont(self._section_font())
        inputs_header.setObjectName("sectionHeader")
        outer.addWidget(inputs_header)

        inputs_scroll = QScrollArea()
        inputs_scroll.setWidgetResizable(True)
        inputs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inputs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        inputs_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inputs_scroll.setFixedHeight(62)
        self._inputs_widget = QWidget()
        self._inputs_layout = QHBoxLayout(self._inputs_widget)
        self._inputs_layout.setSpacing(6)
        self._inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_scroll.setWidget(self._inputs_widget)
        outer.addWidget(inputs_scroll)

        apps_header_row = QHBoxLayout()
        apps_header_row.setSpacing(0)
        apps_label = QLabel("APPS")
        apps_label.setFont(self._section_font())
        apps_label.setObjectName("sectionHeader")
        apps_header_row.addWidget(apps_label)
        apps_header_row.addStretch()
        self._see_all_btn = QPushButton("See all ›")
        self._see_all_btn.setObjectName("seeAllButton")
        self._see_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._see_all_btn.clicked.connect(self._show_all_apps)
        self._see_all_btn.setVisible(False)
        apps_header_row.addWidget(self._see_all_btn)
        outer.addLayout(apps_header_row)

        self._apps_container = QWidget()
        self._apps_layout = QHBoxLayout(self._apps_container)
        self._apps_layout.setSpacing(_APP_CARD_SPACING)
        self._apps_layout.setContentsMargins(0, 0, 0, 0)
        self._apps_container.setFixedHeight(96)
        outer.addWidget(self._apps_container)

        icon_cache.icon_ready.connect(self._on_icon_ready)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        new_count = self._max_visible_apps()
        if new_count != self._last_visible_count and self._all_apps:
            self._clear_layout(self._apps_layout)
            self._build_apps(self._last_apps, self._last_inputs)

    @staticmethod
    def _section_font() -> QFont:
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        return f

    def update_state(self, state: TvState) -> None:
        self._last_apps = state.apps or {}
        self._last_inputs = state.inputs or {}
        self._current_app_id = state.current_app_id
        self._rebuild(self._last_apps, self._last_inputs)

    def _rebuild(self, apps: dict[str, Any], inputs: dict[str, Any]) -> None:
        self._clear_layout(self._inputs_layout)
        self._clear_layout(self._apps_layout)
        self._buttons.clear()
        self._icon_labels.clear()

        self._build_inputs(apps, inputs)
        self._build_apps(apps, inputs)

    @staticmethod
    def _short_label(inp: dict[str, Any]) -> str:
        spd = inp.get("spdProductDescription", "")
        if spd:
            return spd
        for sub in inp.get("subList", []):
            name = sub.get("brandName") or sub.get("labelName")
            if name:
                return name
        return inp.get("label", "")

    def _build_inputs(
        self, apps: dict[str, Any], inputs: dict[str, Any]
    ) -> None:
        input_entries: list[tuple[str, str, str, bool]] = []

        for app_id, inp in inputs.items():
            if app_id.startswith(HDMI_APP_PREFIX):
                num = app_id.replace(HDMI_APP_PREFIX, "")
                port_name = f"HDMI {num}"
            else:
                port_name = inp.get("id", app_id)

            short = self._short_label(inp)
            connected = inp.get("connected", False)
            input_entries.append((app_id, port_name, short, connected))

        for app_id, info in apps.items():
            if app_id == "com.webos.app.livetv" and app_id not in inputs:
                input_entries.append(
                    (app_id, info.get("title", "TV Tuner"), "", True)
                )

        input_entries.sort(key=lambda e: e[0])

        for app_id, port_name, user_label, connected in input_entries:
            display_label = (
                user_label if user_label and user_label != port_name else ""
            )

            btn = QPushButton()
            btn.setObjectName("inputButton")
            btn.setFixedSize(100, 50)
            btn.setToolTip(app_id)

            label_widget = QWidget()
            label_widget.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            label_layout = QVBoxLayout(label_widget)
            label_layout.setContentsMargins(2, 2, 2, 2)
            label_layout.setSpacing(0)

            port_lbl = QLabel(port_name)
            port_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            port_lbl.setObjectName("inputPortLabel")
            port_lbl.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            label_layout.addWidget(port_lbl)

            if display_label:
                name_lbl = QLabel(display_label)
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl.setObjectName("inputNameLabel")
                name_lbl.setMaximumWidth(92)
                name_lbl.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents
                )
                label_layout.addWidget(name_lbl)

            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(label_widget)

            if app_id == self._current_app_id:
                btn.setProperty("active", True)

            btn.clicked.connect(
                lambda checked, aid=app_id: self.app_clicked.emit(aid)
            )
            self._buttons[app_id] = btn
            self._inputs_layout.addWidget(btn)

        self._inputs_layout.addStretch()

    def _max_visible_apps(self) -> int:
        w = self._apps_container.width()
        if w <= 0:
            return 4
        return max(1, w // (_APP_CARD_SIZE + _APP_CARD_SPACING))

    def _build_apps(
        self, apps: dict[str, Any], inputs: dict[str, Any]
    ) -> None:
        input_ids = set(inputs.keys())
        streaming = [
            info
            for app_id, info in apps.items()
            if app_id not in input_ids
            and not app_id.startswith(HDMI_APP_PREFIX)
            and app_id != "com.webos.app.livetv"
        ]
        streaming.sort(key=lambda a: a.get("title", ""))
        self._all_apps = streaming

        max_vis = self._max_visible_apps()
        self._last_visible_count = max_vis
        self._see_all_btn.setVisible(len(streaming) > max_vis)

        visible = streaming[:max_vis]
        for app_info in visible:
            self._add_app_card(app_info, self._apps_layout)

        self._apps_layout.addStretch()

    def _add_app_card(
        self, app_info: dict[str, Any], layout: QHBoxLayout, size: int = _APP_CARD_SIZE
    ) -> QPushButton:
        app_id = app_info.get("id", "")
        title = app_info.get("title", app_id)

        btn = QPushButton()
        btn.setObjectName("appCardButton")
        btn.setToolTip(app_id)
        btn.setFixedSize(size, size)

        card_widget = QWidget()
        card_widget.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        card_layout = QVBoxLayout(card_widget)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(4)

        card_layout.addStretch()

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(_APP_ICON_SIZE, _APP_ICON_SIZE)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setObjectName("appIconLabel")
        icon_lbl.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        card_layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        pm = self._icon_cache.get(app_id)
        if pm:
            icon_lbl.setPixmap(_round_pixmap(pm, _APP_ICON_SIZE, _APP_ICON_RADIUS))

        icon_url = app_info.get("icon", "") or app_info.get("largeIcon", "")
        if icon_url and not self._icon_cache.get(app_id):
            asyncio.ensure_future(self._icon_cache.ensure(app_id, icon_url))

        name_lbl = QLabel(title)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setObjectName("appNameLabel")
        name_lbl.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        card_layout.addWidget(name_lbl)

        card_layout.addStretch()

        btn_layout = QVBoxLayout(btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(card_widget)

        if "appLock" in app_info.get("badges", []):
            lock_lbl = QLabel("🔒", btn)
            lock_lbl.setStyleSheet("font-size: 10px; background: transparent;")
            lock_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lock_lbl.move(size - 18, 4)

        if app_id == self._current_app_id:
            btn.setProperty("active", True)

        btn.clicked.connect(
            lambda checked, aid=app_id: self.app_clicked.emit(aid)
        )
        self._buttons[app_id] = btn
        self._icon_labels[app_id] = icon_lbl
        layout.addWidget(btn)
        return btn

    def _show_all_apps(self) -> None:
        dlg = AllAppsDialog(
            self._all_apps, self._current_app_id,
            self._icon_cache, self.window(),
        )
        dlg.app_selected.connect(self.app_clicked.emit)
        dlg.exec()

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_icon_ready(self, app_id: str, pixmap: QPixmap) -> None:
        icon_lbl = self._icon_labels.get(app_id)
        if icon_lbl:
            icon_lbl.setPixmap(_round_pixmap(pixmap, _APP_ICON_SIZE, _APP_ICON_RADIUS))
