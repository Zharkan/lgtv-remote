from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget
from qasync import asyncSlot

from lgtv_remote.config import ConfigStore
from lgtv_remote.connection import ConnectionManager, ConnectionState
from lgtv_remote.constants import HDMI_APP_PREFIX
from lgtv_remote.protocols import TvState

_ICON_PATH = Path(__file__).resolve().parent.parent / "resources" / "lgtv-remote.svg"
_ICON_SIZE = 64


def _build_icons() -> tuple[QIcon, QIcon]:
    from PySide6.QtGui import QColor, QPainter

    renderer = QSvgRenderer(str(_ICON_PATH))
    img = QImage(_ICON_SIZE, _ICON_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()

    icon_on = QIcon(QPixmap.fromImage(img))

    grey = img.copy()
    for y in range(grey.height()):
        for x in range(grey.width()):
            c = grey.pixelColor(x, y)
            g = int(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
            grey.setPixelColor(x, y, QColor(g, g, g, c.alpha()))

    icon_off = QIcon(QPixmap.fromImage(grey))
    return icon_on, icon_off


class TrayIcon(QSystemTrayIcon):
    quit_requested = Signal()

    def __init__(
        self,
        conn: ConnectionManager,
        config: ConfigStore,
        window: QWidget,
    ) -> None:
        icon_on, icon_off = _build_icons()
        super().__init__(icon_off, window)
        self._icon_on = icon_on
        self._icon_off = icon_off
        self._tv_is_on = False
        self._conn = conn
        self._config = config
        self._window = window

        self._menu = QMenu()
        self._build_menu()
        self.setContextMenu(self._menu)
        self.setToolTip("LG TV Remote")

        self.activated.connect(self._on_activated)
        conn.state_changed.connect(self._on_conn_state_changed)
        conn.tv_state_updated.connect(self._on_tv_state_updated)

    def _build_menu(self) -> None:
        m = self._menu

        self._status_action = m.addAction("LG TV Remote")
        self._status_action.setEnabled(False)
        m.addSeparator()

        self._show_action = m.addAction("Show", self._on_show_hide)
        m.addSeparator()

        self._power_action = m.addAction("Power On", self._on_power_toggle)
        self._mute_action = m.addAction("Mute", self._on_mute_toggle)
        m.addSeparator()

        self._volume_menu = m.addMenu("Volume")
        self._volume_menu.addAction("Volume Up", self._on_volume_up)
        self._volume_menu.addAction("Volume Down", self._on_volume_down)
        m.addSeparator()

        self._inputs_menu = m.addMenu("Inputs")
        self._inputs_menu.aboutToShow.connect(self._rebuild_inputs_menu)
        m.addSeparator()

        self._tvs_menu = m.addMenu("TVs")
        self._tvs_menu.aboutToShow.connect(self._rebuild_tvs_menu)
        m.addSeparator()

        self._media_menu = m.addMenu("Media")
        self._media_menu.addAction("Play", self._on_play)
        self._media_menu.addAction("Pause", self._on_pause)
        self._media_menu.addAction("Stop", self._on_stop)
        m.addSeparator()

        m.addAction("Quit", self._on_quit)

        self._set_tv_actions_enabled(False)
        self._tvs_menu.menuAction().setVisible(len(self._config.config.tvs) > 1)

    def _set_tv_actions_enabled(self, enabled: bool) -> None:
        self._mute_action.setEnabled(enabled)
        self._volume_menu.setEnabled(enabled)
        self._inputs_menu.setEnabled(enabled)
        self._media_menu.setEnabled(enabled)

    def _update_icon(self, is_on: bool) -> None:
        if is_on == self._tv_is_on:
            return
        self._tv_is_on = is_on
        self.setIcon(self._icon_on if is_on else self._icon_off)

    def _on_conn_state_changed(self, state: ConnectionState) -> None:
        connected = state == ConnectionState.CONNECTED
        self._set_tv_actions_enabled(connected)
        self._power_action.setEnabled(
            state in (ConnectionState.CONNECTED, ConnectionState.OFFLINE)
        )

        if connected:
            self._power_action.setText("Power Off")
        else:
            self._power_action.setText("Power On")
            self._update_icon(False)

        tv = self._config.active_tv
        label = tv.label if tv else "No TV"
        state_label = state.value.capitalize()
        self._status_action.setText(f"{label} — {state_label}")
        self.setToolTip(f"LG TV Remote\n{label} — {state_label}")

    def _on_tv_state_updated(self, state: TvState) -> None:
        self._update_icon(state.is_on)

        if state.muted is not None:
            self._mute_action.setText("Unmute" if state.muted else "Mute")
            self._mute_action.setEnabled(True)
        else:
            self._mute_action.setText("Mute")
            self._mute_action.setEnabled(False)

        if state.is_on:
            self._power_action.setText("Power Off")
        else:
            self._power_action.setText("Power On")

        tv = self._config.active_tv
        label = tv.label if tv else "No TV"
        parts = [f"LG TV Remote", f"{label} — Connected"]
        if state.volume is not None:
            vol = f"Vol: {state.volume}"
            if state.muted:
                vol += " (muted)"
            parts.append(vol)
        if state.current_app_id:
            app_name = self._resolve_app_name(state, state.current_app_id)
            parts.append(app_name)
        self.setToolTip("\n".join(parts))
        self._tvs_menu.menuAction().setVisible(len(self._config.config.tvs) > 1)

    @staticmethod
    def _resolve_app_name(state: TvState, app_id: str) -> str:
        if app_id.startswith(HDMI_APP_PREFIX):
            num = app_id.replace(HDMI_APP_PREFIX, "")
            inputs = state.inputs or {}
            inp = inputs.get(app_id, {})
            spd = inp.get("spdProductDescription", "")
            if spd:
                return f"HDMI {num} — {spd}"
            return f"HDMI {num}"
        apps = state.apps or {}
        app_info = apps.get(app_id, {})
        return app_info.get("title", app_id)

    def _rebuild_inputs_menu(self) -> None:
        self._inputs_menu.clear()
        ts = self._conn.tv_state
        if not ts:
            return

        inputs = ts.inputs or {}
        apps = ts.apps or {}
        entries: list[tuple[str, str]] = []

        for app_id, inp in inputs.items():
            if app_id.startswith(HDMI_APP_PREFIX):
                num = app_id.replace(HDMI_APP_PREFIX, "")
                port_name = f"HDMI {num}"
            else:
                port_name = inp.get("id", app_id)
            spd = inp.get("spdProductDescription", "")
            display = f"{port_name} — {spd}" if spd else port_name
            entries.append((app_id, display))

        if "com.webos.app.livetv" in apps and "com.webos.app.livetv" not in inputs:
            entries.append(("com.webos.app.livetv", "TV Tuner"))

        entries.sort(key=lambda e: e[0])

        for app_id, display in entries:
            action = self._inputs_menu.addAction(display)
            action.setCheckable(True)
            action.setChecked(app_id == ts.current_app_id)
            action.triggered.connect(
                lambda checked, aid=app_id: self._on_launch_input(aid)
            )

    def _rebuild_tvs_menu(self) -> None:
        self._tvs_menu.clear()
        active_id = self._config.config.active_tv_id
        for tv in self._config.config.tvs:
            action = self._tvs_menu.addAction(tv.label)
            action.setCheckable(True)
            action.setChecked(tv.id == active_id)
            action.triggered.connect(
                lambda checked, tid=tv.id: self._on_switch_tv(tid)
            )

    def _on_show_hide(self) -> None:
        if self._window.isVisible() and not self._window.isMinimized():
            self._window.hide()
            self._show_action.setText("Show")
        else:
            self._window.showNormal()
            self._window.raise_()
            self._window.activateWindow()
            self._show_action.setText("Hide")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_show_hide()

    def _on_power_toggle(self) -> None:
        self._window._on_power()

    @asyncSlot()
    async def _on_mute_toggle(self) -> None:
        ts = self._conn.tv_state
        if ts and ts.muted is not None:
            await self._conn.set_mute(not ts.muted)

    @asyncSlot()
    async def _on_volume_up(self) -> None:
        ts = self._conn.tv_state
        if ts and ts.volume is not None:
            await self._conn.set_volume(min(100, ts.volume + 2))

    @asyncSlot()
    async def _on_volume_down(self) -> None:
        ts = self._conn.tv_state
        if ts and ts.volume is not None:
            await self._conn.set_volume(max(0, ts.volume - 2))

    @asyncSlot()
    async def _on_launch_input(self, app_id: str) -> None:
        await self._conn.launch_app(app_id)

    def _on_switch_tv(self, tv_id: str) -> None:
        self._conn.switch_tv(tv_id)

    @asyncSlot()
    async def _on_play(self) -> None:
        await self._conn.play()

    @asyncSlot()
    async def _on_pause(self) -> None:
        await self._conn.pause()

    @asyncSlot()
    async def _on_stop(self) -> None:
        await self._conn.stop()

    def _on_quit(self) -> None:
        self.quit_requested.emit()
