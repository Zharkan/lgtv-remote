from __future__ import annotations

import asyncio

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QMoveEvent, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot

from lgtv_remote.config import ConfigStore, TvConfig
from lgtv_remote.connection import ConnectionManager, ConnectionState
from lgtv_remote.protocols import TvState
from lgtv_remote.constants import PIN_INITIAL_DELAY_MS, PIN_KEY_INTERVAL_MS, SETUP_WIZARD_DELAY_MS
from lgtv_remote.screenshot import ScreenshotService
from lgtv_remote.ui.dpad import DPadWidget
from lgtv_remote.ui.header import HeaderWidget
from lgtv_remote.ui.icon_cache import IconCache
from lgtv_remote.ui.input_grid import InputGridWidget
from lgtv_remote.ui.now_playing import NowPlayingCard
from lgtv_remote.ui.pin_dialog import PinDialog
from lgtv_remote.ui.settings_dialog import SettingsDialog
from lgtv_remote.ui.setup_wizard import SetupWizard
from lgtv_remote.ui.volume_row import VolumeRowWidget


class MainWindow(QMainWindow):
    def __init__(
        self,
        conn: ConnectionManager,
        config: ConfigStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("LG TV Remote")
        self.setMinimumSize(530, 920)

        self._conn = conn
        self._config = config
        self._icon_cache = IconCache(self)
        self._closed_event = asyncio.Event()
        self._closing = False
        self._pin_dialog: PinDialog | None = None
        self._pending_pin_keys: list[str] = []
        self._pin_key_index: int = 0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        self._header = HeaderWidget(config)
        layout.addWidget(self._header)

        self._body_stack = QStackedWidget()

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        self._now_playing = NowPlayingCard()
        controls_layout.addWidget(self._now_playing)

        self._input_grid = InputGridWidget(self._icon_cache)
        controls_layout.addWidget(self._input_grid)

        vol_card = QFrame()
        vol_card.setObjectName("volumeCard")
        vol_card_layout = QVBoxLayout(vol_card)
        vol_card_layout.setContentsMargins(0, 0, 0, 0)
        self._volume_row = VolumeRowWidget()
        vol_card_layout.addWidget(self._volume_row)
        controls_layout.addWidget(vol_card)

        self._dpad = DPadWidget()
        controls_layout.addWidget(self._dpad)
        controls_layout.addStretch()

        self._body_stack.addWidget(controls)

        self._offline_page = self._build_offline_page()
        self._body_stack.addWidget(self._offline_page)

        self._unconfigured_page = self._build_unconfigured_page()
        self._body_stack.addWidget(self._unconfigured_page)

        self._body_stack.setCurrentIndex(2 if not config.config.tvs else 1)
        layout.addWidget(self._body_stack)

        scroll.setWidget(central)
        self.setCentralWidget(scroll)

        conn.tv_state_updated.connect(self._on_tv_state)
        conn.state_changed.connect(self._on_conn_state)
        conn.pairing_required.connect(self._on_pairing_required)

        self._header.power_clicked.connect(self._on_power)
        self._header.tv_selected.connect(self._on_tv_switch)
        self._header.settings_clicked.connect(self._on_settings)
        self._volume_row.volume_changed.connect(self._on_volume)
        self._volume_row.mute_toggled.connect(self._on_mute)
        self._dpad.button_pressed.connect(self._on_button)
        self._input_grid.app_clicked.connect(self._on_launch_app)

        self._screenshot_svc = ScreenshotService(conn, config, self)
        self._sync_screenshot_interval()
        self._screenshot_svc.screenshot_ready.connect(
            self._now_playing.set_screenshot
        )
        self._screenshot_svc.screenshot_cleared.connect(
            self._now_playing.clear_screenshot
        )

        self._setup_shortcuts()
        self._restore_geometry()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_geometry)

        if not config.config.tvs:
            QTimer.singleShot(SETUP_WIZARD_DELAY_MS, self._show_setup_wizard)

    def _setup_shortcuts(self) -> None:
        nav = {
            Qt.Key.Key_Up: "UP",
            Qt.Key.Key_Down: "DOWN",
            Qt.Key.Key_Left: "LEFT",
            Qt.Key.Key_Right: "RIGHT",
            Qt.Key.Key_Return: "ENTER",
            Qt.Key.Key_Backspace: "BACK",
            Qt.Key.Key_Escape: "EXIT",
            Qt.Key.Key_Home: "HOME",
        }
        for key, name in nav.items():
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda n=name: self._on_button_shortcut(n))

        num_keys = {
            Qt.Key.Key_0: "0", Qt.Key.Key_1: "1", Qt.Key.Key_2: "2",
            Qt.Key.Key_3: "3", Qt.Key.Key_4: "4", Qt.Key.Key_5: "5",
            Qt.Key.Key_6: "6", Qt.Key.Key_7: "7", Qt.Key.Key_8: "8",
            Qt.Key.Key_9: "9",
        }
        for key, name in num_keys.items():
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda n=name: self._on_button_shortcut(n))

    @asyncSlot()
    async def _on_button_shortcut(self, name: str) -> None:
        await self._conn.send_button(name)

    def _on_tv_state(self, state: TvState) -> None:
        prev_app = getattr(self, "_last_app_id", None)
        cur_app = state.current_app_id
        self._last_app_id = cur_app

        self._header.update_state(state)
        self._now_playing.update_state(state)
        self._input_grid.update_state(state)
        self._volume_row.update_state(state)

        if cur_app and cur_app != prev_app:
            self._screenshot_svc.capture_once(delay=2.0)

    def _build_offline_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 0, 20, 0)

        lay.addStretch(2)

        icon = QLabel("⏻")
        icon.setObjectName("offlineIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)

        lay.addSpacing(12)

        self._offline_title = QLabel("TV Offline")
        self._offline_title.setObjectName("offlineTitle")
        self._offline_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._offline_title)

        lay.addSpacing(4)

        self._offline_subtitle = QLabel("Connect to start controlling your TV")
        self._offline_subtitle.setObjectName("offlineSubtitle")
        self._offline_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_subtitle.setWordWrap(True)
        lay.addWidget(self._offline_subtitle)

        lay.addSpacing(16)

        self._offline_progress = QProgressBar()
        self._offline_progress.setObjectName("offlineProgress")
        self._offline_progress.setRange(0, 0)
        self._offline_progress.setFixedWidth(200)
        self._offline_progress.hide()
        lay.addWidget(self._offline_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addSpacing(20)

        self._offline_power_btn = QPushButton("⏻  Wake Up")
        self._offline_power_btn.setObjectName("offlinePowerButton")
        self._offline_power_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._offline_power_btn.clicked.connect(self._on_power)
        lay.addWidget(self._offline_power_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addStretch(3)
        return page

    def _build_unconfigured_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 0, 20, 0)

        lay.addStretch(2)

        icon = QLabel("📺")
        icon.setObjectName("unconfiguredIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)

        lay.addSpacing(12)

        title = QLabel("No TV Configured")
        title.setObjectName("unconfiguredTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(4)

        subtitle = QLabel("Add a TV to start controlling it from here")
        subtitle.setObjectName("unconfiguredSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        lay.addSpacing(20)

        setup_btn = QPushButton("Add a TV")
        setup_btn.setObjectName("unconfiguredSetupButton")
        setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setup_btn.clicked.connect(self._on_settings)
        lay.addWidget(setup_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addStretch(3)
        return page

    _OFFLINE_MESSAGES = {
        ConnectionState.OFFLINE: ("TV Offline", "Press Wake Up to power on via Wake-on-LAN"),
        ConnectionState.CONNECTING: ("Connecting…", "Attempting to reach your TV"),
        ConnectionState.PAIRING: ("Pairing…", "Accept the prompt on your TV screen"),
    }

    def _on_conn_state(self, state: ConnectionState) -> None:
        self._header.set_connection_state(state)
        connected = state == ConnectionState.CONNECTED
        self._volume_row.set_enabled_state(connected)
        self._now_playing.set_stale(not connected)
        self._screenshot_svc.set_active(connected)

        if connected:
            self._offline_progress.hide()
            self._body_stack.setCurrentIndex(0)
        elif state == ConnectionState.UNCONFIGURED:
            self._offline_progress.hide()
            self._body_stack.setCurrentIndex(2)
        else:
            title, subtitle = self._OFFLINE_MESSAGES.get(
                state, ("TV Offline", "")
            )
            self._offline_title.setText(title)
            self._offline_subtitle.setText(subtitle)
            is_waiting = state in (
                ConnectionState.CONNECTING, ConnectionState.PAIRING,
            )
            self._offline_power_btn.setEnabled(not is_waiting)
            self._offline_power_btn.setText(
                "Connecting…" if is_waiting else "⏻  Wake Up"
            )
            if is_waiting:
                self._offline_progress.show()
            else:
                self._offline_progress.hide()
            self._body_stack.setCurrentIndex(1)

    def _on_pairing_required(self) -> None:
        pass

    @asyncSlot()
    async def _on_power(self) -> None:
        ts = self._conn.tv_state
        if ts and getattr(ts, "is_on", False):
            self._offline_title.setText("Turning Off…")
            self._offline_subtitle.setText("Waiting for TV to shut down")
            self._offline_power_btn.setEnabled(False)
            self._offline_power_btn.setText("⏻")
            self._offline_progress.show()
            self._body_stack.setCurrentIndex(1)
            await self._conn.power_off()
        else:
            self._offline_title.setText("Waking Up…")
            self._offline_subtitle.setText(
                "Magic packet sent — waiting for TV to come online"
            )
            self._offline_power_btn.setEnabled(False)
            self._offline_power_btn.setText("Connecting…")
            self._offline_progress.show()
            await self._conn.power_on()

    @asyncSlot(str)
    async def _on_tv_switch(self, tv_id: str) -> None:
        self._conn.switch_tv(tv_id)
        self._sync_screenshot_interval()

    @asyncSlot(int)
    async def _on_volume(self, value: int) -> None:
        await self._conn.set_volume(value)

    @asyncSlot(bool)
    async def _on_mute(self, muted: bool) -> None:
        await self._conn.set_mute(muted)

    @asyncSlot(str)
    async def _on_button(self, name: str) -> None:
        await self._conn.send_button(name)

    def _on_launch_app(self, app_id: str) -> None:
        ts = self._conn.tv_state
        apps = getattr(ts, "apps", {}) or {} if ts else {}
        app_info = apps.get(app_id, {})
        is_locked = "appLock" in app_info.get("badges", [])
        if is_locked:
            dlg = PinDialog(app_info.get("title", app_id), self)
            self._pin_dialog = dlg
            dlg.accepted.connect(lambda: self._launch_locked_app(app_id))
            dlg.rejected.connect(self._clear_pin_dialog)
            dlg.open()
            return
        asyncio.ensure_future(self._conn.launch_app(app_id))

    def _clear_pin_dialog(self) -> None:
        self._pin_dialog = None

    def _launch_locked_app(self, app_id: str) -> None:
        pin = self._pin_dialog.pin if self._pin_dialog else ""
        self._pin_dialog = None
        if not pin:
            return
        asyncio.ensure_future(self._conn.launch_app(app_id))
        self._pending_pin_keys = list(pin) + ["ENTER"]
        self._pin_key_index = 0
        QTimer.singleShot(PIN_INITIAL_DELAY_MS, self._send_next_pin_key)

    def _send_next_pin_key(self) -> None:
        if self._pin_key_index >= len(self._pending_pin_keys):
            self._pending_pin_keys = []
            return
        key = self._pending_pin_keys[self._pin_key_index]
        self._pin_key_index += 1
        self._dpad.button_pressed.emit(key)
        QTimer.singleShot(PIN_KEY_INTERVAL_MS, self._send_next_pin_key)

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._config, self)
        dlg.tv_added.connect(self._on_tv_added)
        dlg.tv_removed.connect(self._on_tv_removed)
        dlg.tv_updated.connect(lambda _: self._sync_screenshot_interval())
        dlg.exec()
        self._header.refresh_tv_list()

    def _sync_screenshot_interval(self) -> None:
        tv = self._config.active_tv
        self._screenshot_svc.set_interval(tv.screenshot_interval if tv else 0)

    def _on_tv_added(self, tv: TvConfig) -> None:
        self._conn.switch_tv(tv.id)

    def _on_tv_removed(self, tv_id: str) -> None:
        if self._config.active_tv:
            self._conn.switch_tv(self._config.active_tv.id)
        else:
            self._conn.set_unconfigured()

    def _show_setup_wizard(self) -> None:
        wizard = SetupWizard(self)
        wizard.tv_configured.connect(self._on_wizard_done)
        wizard.exec()

    def _on_wizard_done(self, tv: TvConfig) -> None:
        self._config.add_tv(tv)
        self._header.refresh_tv_list()
        self._conn.switch_tv(tv.id)

    def _restore_geometry(self) -> None:
        cfg = self._config.config
        if all(v is not None for v in (cfg.window_x, cfg.window_y, cfg.window_width, cfg.window_height)):
            rect = self.geometry()
            rect.setX(cfg.window_x)
            rect.setY(cfg.window_y)
            rect.setWidth(cfg.window_width)
            rect.setHeight(cfg.window_height)
            screen = QApplication.screenAt(rect.center())
            if screen and screen.availableGeometry().contains(rect.center()):
                self.setGeometry(rect)

    def _save_geometry(self) -> None:
        if self.isMinimized() or self.isMaximized():
            return
        geo = self.geometry()
        cfg = self._config.config
        cfg.window_x = geo.x()
        cfg.window_y = geo.y()
        cfg.window_width = geo.width()
        cfg.window_height = geo.height()
        self._config.save()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self._save_timer.start()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._save_timer.start()

    async def wait_closed(self) -> None:
        await self._closed_event.wait()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            return
        self._closing = True
        self._save_geometry()
        event.ignore()
        self.hide()
        self._screenshot_svc.stop()
        asyncio.ensure_future(self._async_close())

    async def _async_close(self) -> None:
        await self._conn.shutdown()
        self._closed_event.set()
