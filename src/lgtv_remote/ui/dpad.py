from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtCore import QEvent
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CircularDPad(QWidget):
    button_pressed = Signal(str)

    _OK_COLOR = QColor("#2ecc71")
    _OK_HOVER = QColor("#27ae60")
    _OK_PRESSED = QColor("#1e8c4e")
    _ARROW = QColor("#8faba5")
    _ARROW_HOVER = QColor("#e0e0e0")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(210, 210)
        self._hover: str | None = None
        self._pressed: str | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _region(self, pos) -> str | None:
        cx, cy = self.width() / 2, self.height() / 2
        dx, dy = pos.x() - cx, pos.y() - cy
        dist = math.hypot(dx, dy)
        r = min(cx, cy) - 2

        if dist <= r * 0.34:
            return "ENTER"
        if dist > r:
            return None

        angle = math.atan2(dy, dx)
        if -3 * math.pi / 4 < angle <= -math.pi / 4:
            return "UP"
        if -math.pi / 4 < angle <= math.pi / 4:
            return "RIGHT"
        if math.pi / 4 < angle <= 3 * math.pi / 4:
            return "DOWN"
        return "LEFT"

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = self._region(event.position())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            region = self._region(event.position())
            if region and region == self._pressed:
                self.button_pressed.emit(region)
            self._pressed = None
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        region = self._region(event.position())
        if region != self._hover:
            self._hover = region
            self.update()

    def leaveEvent(self, event: QEvent) -> None:
        self._hover = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        r = min(cx, cy) - 2

        # Outer circle with border
        p.setPen(QPen(QColor("#1e4442"), 1.5))
        p.setBrush(QColor("#152b2a"))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Radial glow from center
        glow = QRadialGradient(cx, cy, r * 0.75)
        glow.setColorAt(0.0, QColor(30, 68, 66, 120))
        glow.setColorAt(0.5, QColor(26, 56, 54, 60))
        glow.setColorAt(1.0, QColor(21, 43, 42, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), r - 1, r - 1)

        # Inner circle (subtle lighter ring)
        inner_r = r * 0.58
        inner_grad = QRadialGradient(cx, cy, inner_r)
        inner_grad.setColorAt(0.0, QColor("#1d3f3d"))
        inner_grad.setColorAt(1.0, QColor("#19352f"))
        p.setBrush(inner_grad)
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        # OK ring (dark border around OK button)
        ok_r = r * 0.34
        ring_r = ok_r + 4
        p.setBrush(QColor("#0e201e"))
        p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # OK button
        if self._pressed == "ENTER":
            p.setBrush(self._OK_PRESSED)
        elif self._hover == "ENTER":
            p.setBrush(self._OK_HOVER)
        else:
            p.setBrush(self._OK_COLOR)
        p.drawEllipse(QPointF(cx, cy), ok_r, ok_r)

        # OK text
        p.setPen(QColor("#0d1f1e"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            QRectF(cx - ok_r, cy - ok_r, ok_r * 2, ok_r * 2),
            Qt.AlignmentFlag.AlignCenter,
            "OK",
        )

        self._draw_arrows(p, cx, cy, r)
        p.end()

    def _draw_arrows(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        dist = r * 0.80
        sz = 7

        arrows = {
            "UP":    (cx, cy - dist, -sz, sz, sz, sz),
            "DOWN":  (cx, cy + dist, -sz, -sz, sz, -sz),
            "LEFT":  (cx - dist, cy, sz, -sz, sz, sz),
            "RIGHT": (cx + dist, cy, -sz, -sz, -sz, sz),
        }

        for name, (ax, ay, x1, y1, x2, y2) in arrows.items():
            color = self._ARROW_HOVER if self._hover == name else self._ARROW
            pen = QPen(color, 2.0, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(ax + x1, ay + y1)
            path.lineTo(ax, ay)
            path.lineTo(ax + x2, ay + y2)
            p.drawPath(path)


class DPadWidget(QWidget):
    button_pressed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(14)

        outer.addSpacing(10)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(16)
        controls_row.addStretch()

        self._circular_dpad = CircularDPad()
        self._circular_dpad.button_pressed.connect(self.button_pressed)
        controls_row.addWidget(
            self._circular_dpad, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #1e4442;")
        controls_row.addWidget(sep)

        controls_row.addLayout(self._build_numpad())
        controls_row.addStretch()
        outer.addLayout(controls_row)

        outer.addSpacing(10)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        for label, name, obj in [
            ("← Back", "BACK", "navButton"),
            ("⌂ Home", "HOME", "homeButton"),
            ("✕ Exit", "EXIT", "navButton"),
        ]:
            btn = self._make_btn(label, name, w=0, h=40)
            btn.setObjectName(obj)
            nav_row.addWidget(btn)
        outer.addLayout(nav_row)

        media_card = QWidget()
        media_card.setObjectName("mediaCard")
        media_layout = QHBoxLayout(media_card)
        media_layout.setContentsMargins(12, 8, 12, 8)
        media_layout.setSpacing(0)
        for symbol, name, obj, w, h in [
            ("⏮", "REWIND", "mediaButton", 44, 36),
            ("⏸", "PAUSE", "mediaButton", 44, 36),
            ("▶", "PLAY", "playButton", 52, 52),
            ("⏹", "STOP", "mediaButton", 44, 36),
            ("⏭", "FASTFORWARD", "mediaButton", 44, 36),
        ]:
            if obj != "playButton":
                media_layout.addStretch()
            btn = self._make_btn(symbol, name, w=w, h=h)
            btn.setObjectName(obj)
            media_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            if obj != "playButton":
                media_layout.addStretch()
            else:
                media_layout.insertStretch(media_layout.count() - 1)
                media_layout.addStretch()
        outer.addWidget(media_card)

    def _build_numpad(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(8)

        for i in range(1, 10):
            row, col = divmod(i - 1, 3)
            btn = self._make_btn(str(i), str(i), w=42, h=42)
            btn.setObjectName("numButton")
            grid.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        btn_0 = self._make_btn("0", "0", w=42, h=42)
        btn_0.setObjectName("numButton")
        grid.addWidget(btn_0, 3, 1, Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(grid)
        return layout

    def _make_btn(
        self, label: str, button_name: str, w: int = 52, h: int = 40
    ) -> QPushButton:
        btn = QPushButton(label)
        if w > 0:
            btn.setFixedSize(w, h)
        else:
            btn.setFixedHeight(h)
        btn.clicked.connect(lambda: self.button_pressed.emit(button_name))
        return btn
