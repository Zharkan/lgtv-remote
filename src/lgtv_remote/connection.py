from __future__ import annotations

import asyncio
import enum
import logging
import random
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from PySide6.QtCore import QObject, Signal

from lgtv_remote.config import ConfigStore
from lgtv_remote.protocols import TvClient, TvState
from lgtv_remote.constants import (
    DISCONNECT_THRESHOLD,
    POLL_INTERVAL_SECS,
    PROBE_TIMEOUT_SECS,
    WEBOS_PORT,
)
from lgtv_remote.network import send_wol

log = logging.getLogger(__name__)


class ConnectionState(enum.Enum):
    UNCONFIGURED = "unconfigured"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    PAIRING = "pairing"
    CONNECTED = "connected"


class ConnectionManager(QObject):
    state_changed = Signal(object)
    tv_state_updated = Signal(object)
    pairing_required = Signal()
    connection_error = Signal(str)

    def __init__(self, config_store: ConfigStore, mock: bool = False) -> None:
        super().__init__()
        self._config = config_store
        self._mock = mock
        self._client: TvClient | None = None
        self._state = ConnectionState.UNCONFIGURED
        self._connect_task: asyncio.Task[None] | None = None
        self._last_tv_state: TvState | None = None
        self._backoff = _ExponentialBackoff()
        self._shutting_down = False

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def tv_state(self) -> TvState | None:
        return self._last_tv_state

    @property
    def client(self) -> TvClient | None:
        return self._client

    def start(self) -> None:
        if not self._config.active_tv:
            self._set_state(ConnectionState.UNCONFIGURED)
            return
        self._schedule_connect()

    def switch_tv(self, tv_id: str) -> None:
        self._config.set_active(tv_id)
        self._cancel_connect()
        self._client = None
        self._last_tv_state = None
        self._backoff.reset()
        self._schedule_connect()

    def set_unconfigured(self) -> None:
        self._cancel_connect()
        self._client = None
        self._last_tv_state = None
        self._set_state(ConnectionState.UNCONFIGURED)

    def _set_state(self, state: ConnectionState) -> None:
        if self._state != state:
            self._state = state
            self.state_changed.emit(state)

    def _schedule_connect(self) -> None:
        self._cancel_connect()
        self._connect_task = asyncio.ensure_future(self._connect_loop())

    def _cancel_connect(self) -> None:
        if self._connect_task and not self._connect_task.done():
            self._connect_task.cancel()
            self._connect_task = None

    async def _connect_loop(self) -> None:
        from aiowebostv import WebOsClient, WebOsTvPairError

        from lgtv_remote.mock_client import MockTvClient

        tv = self._config.active_tv
        if not tv:
            self._set_state(ConnectionState.UNCONFIGURED)
            return

        while not self._shutting_down:
            if not self._mock and not await self._probe_reachable(tv.host):
                self._set_state(ConnectionState.OFFLINE)
                delay = self._backoff.next_delay()
                await asyncio.sleep(delay)
                continue

            self._set_state(ConnectionState.CONNECTING)
            try:
                if self._mock:
                    self._client = MockTvClient(tv.host, client_key=tv.client_key)
                else:
                    self._client = WebOsClient(tv.host, client_key=tv.client_key)

                await self._client.register_state_update_callback(
                    self._on_state_update
                )
                await self._client.connect()

                if self._client.client_key != tv.client_key:
                    tv.client_key = self._client.client_key
                    self._config.update_tv(tv)

                self._set_state(ConnectionState.CONNECTED)
                self._backoff.reset()

                consecutive_fails = 0
                while not self._shutting_down:
                    await asyncio.sleep(POLL_INTERVAL_SECS)
                    if not self._client.is_connected():
                        consecutive_fails += 1
                        if consecutive_fails >= DISCONNECT_THRESHOLD:
                            break
                    else:
                        consecutive_fails = 0

            except Exception as exc:
                if isinstance(exc, WebOsTvPairError):
                    self._set_state(ConnectionState.PAIRING)
                    self.pairing_required.emit()
                else:
                    log.debug("Connection error: %s", exc)
                    self.connection_error.emit(str(exc))

            with suppress(Exception):
                if self._client:
                    await self._client.disconnect()
            self._client = None
            self._set_state(ConnectionState.OFFLINE)
            delay = self._backoff.next_delay()
            await asyncio.sleep(delay)

    async def _on_state_update(self, state: TvState) -> None:
        self._last_tv_state = state
        self.tv_state_updated.emit(state)

    async def _probe_reachable(self, host: str, port: int = WEBOS_PORT) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=PROBE_TIMEOUT_SECS
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, TimeoutError, asyncio.TimeoutError):
            return False

    async def _send(self, method: str, *args: Any, **kwargs: Any) -> None:
        if self._client and self._client.is_connected():
            await getattr(self._client, method)(*args, **kwargs)

    async def power_on(self) -> None:
        tv = self._config.active_tv
        if not tv or not tv.mac:
            return
        send_wol(tv.mac, tv.host)
        self._backoff.reset()
        self._schedule_connect()

    async def power_off(self) -> None:
        if self._client and self._client.is_connected():
            with suppress(Exception):
                await self._client.power_off()

    async def launch_app(self, app_id: str) -> None:
        await self._send("launch_app", app_id)

    async def set_volume(self, level: int) -> None:
        await self._send("set_volume", level)

    async def set_mute(self, muted: bool) -> None:
        await self._send("set_mute", muted)

    async def send_button(self, name: str) -> None:
        await self._send("button", name)

    async def play(self) -> None:
        await self._send("play")

    async def pause(self) -> None:
        await self._send("pause")

    async def stop(self) -> None:
        await self._send("stop")

    async def rewind(self) -> None:
        await self._send("rewind")

    async def fast_forward(self) -> None:
        await self._send("fast_forward")

    async def send_toast(self, message: str) -> None:
        await self._send("send_message", message)

    async def shutdown(self) -> None:
        self._shutting_down = True
        self._cancel_connect()
        if self._client:
            with suppress(Exception):
                await self._client.disconnect()
            self._client = None


class _ExponentialBackoff:
    def __init__(
        self, base: float = 1.0, factor: float = 2.0, max_delay: float = 30.0
    ) -> None:
        self._base = base
        self._factor = factor
        self._max_delay = max_delay
        self._attempt = 0

    def next_delay(self) -> float:
        delay = min(self._base * (self._factor**self._attempt), self._max_delay)
        jitter = random.uniform(0, delay * 0.3)
        self._attempt += 1
        return delay + jitter

    def reset(self) -> None:
        self._attempt = 0
