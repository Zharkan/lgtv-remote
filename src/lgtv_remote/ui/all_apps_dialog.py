from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from lgtv_remote.ui.icon_cache import IconCache

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


class AllAppsDialog(QDialog):
    app_selected = Signal(str)

    def __init__(
        self,
        apps: list[dict[str, Any]],
        current_app_id: str | None,
        icon_cache: IconCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("All Apps")
        self.setMinimumSize(400, 300)
        self.resize(460, 500)
        self._icon_cache = icon_cache
        self._icon_labels: dict[str, QLabel] = {}
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1f1e;
            }
            QScrollArea {
                background-color: #0d1f1e;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #0d1f1e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QLabel(f"APPS ({len(apps)})")
        header.setObjectName("sectionHeader")
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        header.setFont(f)
        header.setStyleSheet("color: #7a9e94;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        cols = 4
        for i, app_info in enumerate(apps):
            row, col = divmod(i, cols)
            app_id = app_info.get("id", "")
            title = app_info.get("title", app_id)

            btn = QPushButton()
            btn.setObjectName("appCardButton")
            btn.setToolTip(app_id)
            btn.setFixedSize(96, 96)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            card = QWidget()
            card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(4, 4, 4, 4)
            card_lay.setSpacing(4)

            card_lay.addStretch()

            icon_lbl = QLabel()
            icon_lbl.setFixedSize(_APP_ICON_SIZE, _APP_ICON_SIZE)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setObjectName("appIconLabel")
            icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            card_lay.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

            pm = icon_cache.get(app_id)
            if pm:
                icon_lbl.setPixmap(_round_pixmap(pm, _APP_ICON_SIZE, _APP_ICON_RADIUS))
            else:
                icon_url = app_info.get("largeIcon", "") or app_info.get("icon", "")
                if icon_url:
                    asyncio.ensure_future(icon_cache.ensure(app_id, icon_url))

            self._icon_labels[app_id] = icon_lbl

            name_lbl = QLabel(title)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setObjectName("appNameLabel")
            name_lbl.setStyleSheet("color: #e0e0e0; font-size: 8pt;")
            name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            card_lay.addWidget(name_lbl)

            card_lay.addStretch()

            btn_lay = QVBoxLayout(btn)
            btn_lay.setContentsMargins(0, 0, 0, 0)
            btn_lay.addWidget(card)

            if "appLock" in app_info.get("badges", []):
                lock_lbl = QLabel("🔒", btn)
                lock_lbl.setStyleSheet("font-size: 10px; background: transparent;")
                lock_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                lock_lbl.move(78, 4)

            if app_id == current_app_id:
                btn.setProperty("active", True)

            btn.clicked.connect(
                lambda checked, aid=app_id: self._on_app(aid)
            )
            grid.addWidget(btn, row, col)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)

        icon_cache.icon_ready.connect(self._on_icon_ready)

    def _on_icon_ready(self, app_id: str, pixmap: QPixmap) -> None:
        icon_lbl = self._icon_labels.get(app_id)
        if icon_lbl:
            icon_lbl.setPixmap(_round_pixmap(pixmap, _APP_ICON_SIZE, _APP_ICON_RADIUS))

    def _on_app(self, app_id: str) -> None:
        self.app_selected.emit(app_id)
        self.accept()
