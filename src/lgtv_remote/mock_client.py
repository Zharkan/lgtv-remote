from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lgtv_remote.constants import MOCK_CLIENT_KEY, MOCK_CONNECT_DELAY_SECS

if TYPE_CHECKING:
    from lgtv_remote.protocols import TvClient, TvState


@dataclass
class MockTvState:
    power_state: dict[str, Any] = field(
        default_factory=lambda: {"state": "Active", "processing": "None"}
    )
    current_app_id: str | None = "com.webos.app.hdmi1"
    sound_output: str | None = "tv_speaker"
    muted: bool | None = False
    volume: int | None = 15
    apps: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    media_state: list[dict[str, Any]] = field(default_factory=list)
    current_channel: dict[str, Any] | None = None
    channel_info: dict[str, Any] | None = None
    channels: list[dict[str, Any]] | None = None
    is_on: bool = True
    is_screen_on: bool = True


@dataclass
class MockTvInfo:
    hello: dict[str, Any] = field(default_factory=lambda: {"deviceType": "TV"})
    system: dict[str, Any] = field(
        default_factory=lambda: {"modelName": "OLED55C3PSA"}
    )
    software: dict[str, Any] = field(
        default_factory=lambda: {"major_ver": "04", "minor_ver": "40.30"}
    )
    connection: dict[str, Any] = field(default_factory=dict)


MOCK_APPS: dict[str, dict[str, Any]] = {
    "com.webos.app.livetv": {
        "id": "com.webos.app.livetv",
        "title": "TV Tuner",
        "icon": "",
        "largeIcon": "",
    },
    "netflix": {
        "id": "netflix",
        "title": "Netflix",
        "icon": "",
        "largeIcon": "",
    },
    "youtube.leanback.v4": {
        "id": "youtube.leanback.v4",
        "title": "YouTube",
        "icon": "",
        "largeIcon": "",
    },
    "com.webos.app.disney": {
        "id": "com.webos.app.disney",
        "title": "Disney+",
        "icon": "",
        "largeIcon": "",
    },
    "amazon": {
        "id": "amazon",
        "title": "Prime Video",
        "icon": "",
        "largeIcon": "",
    },
    "com.webos.app.crunchyroll": {
        "id": "com.webos.app.crunchyroll",
        "title": "Crunchyroll",
        "icon": "",
        "largeIcon": "",
        "badges": ["appLock"],
    },
    "com.webos.app.spotify": {
        "id": "com.webos.app.spotify",
        "title": "Spotify",
        "icon": "",
        "largeIcon": "",
    },
}

MOCK_INPUTS: dict[str, dict[str, Any]] = {
    "com.webos.app.hdmi1": {
        "id": "HDMI_1",
        "appId": "com.webos.app.hdmi1",
        "label": "PS5 Console de jeu",
        "spdProductDescription": "PS5",
        "spdSourceDeviceInfo": "GAME",
        "connected": True,
        "subList": [{"brandName": "PS5", "labelName": "PS5"}],
    },
    "com.webos.app.hdmi2": {
        "id": "HDMI_2",
        "appId": "com.webos.app.hdmi2",
        "label": "Switch2 Console de jeu",
        "spdProductDescription": "Switch2",
        "spdSourceDeviceInfo": "GAME",
        "connected": True,
        "subList": [{"brandName": "Switch2", "labelName": "Switch2"}],
    },
    "com.webos.app.hdmi3": {
        "id": "HDMI_3",
        "appId": "com.webos.app.hdmi3",
        "label": "HDMI 3",
        "connected": False,
    },
    "com.webos.app.hdmi4": {
        "id": "HDMI_4",
        "appId": "com.webos.app.hdmi4",
        "label": "HDMI 4",
        "connected": False,
    },
}


class MockTvClient:
    def __init__(self, host: str, client_key: str | None = None, **kwargs: Any) -> None:
        self.host = host
        self.client_key = client_key or MOCK_CLIENT_KEY
        self._connected = False
        self._callbacks: list[Callable[[MockTvState], Awaitable[None]]] = []
        self.tv_state = MockTvState(
            apps=dict(MOCK_APPS),
            inputs=dict(MOCK_INPUTS),
        )
        self.tv_info = MockTvInfo()

    async def connect(self) -> bool:
        await asyncio.sleep(MOCK_CONNECT_DELAY_SECS)
        self._connected = True
        await self._notify()
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self.tv_state.is_on = False
        self.tv_state.is_screen_on = False
        self.tv_state.current_app_id = None
        await self._notify()

    def is_connected(self) -> bool:
        return self._connected

    def is_registered(self) -> bool:
        return self.client_key is not None

    async def register_state_update_callback(
        self, callback: Callable[[MockTvState], Awaitable[None]]
    ) -> None:
        self._callbacks.append(callback)

    def unregister_state_update_callback(
        self, callback: Callable[[MockTvState], Awaitable[None]]
    ) -> None:
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def clear_state_update_callbacks(self) -> None:
        self._callbacks.clear()

    async def power_off(self) -> None:
        self.tv_state.is_on = False
        self.tv_state.current_app_id = None
        self._connected = False
        await self._notify()

    async def power_on(self) -> dict[str, Any]:
        self.tv_state.is_on = True
        self.tv_state.is_screen_on = True
        self.tv_state.current_app_id = "com.webos.app.hdmi1"
        await self._notify()
        return {}

    async def launch_app(self, app: str) -> dict[str, Any]:
        self.tv_state.current_app_id = app
        await self._notify()
        return {}

    async def set_volume(self, volume: int) -> dict[str, Any]:
        self.tv_state.volume = max(0, min(100, volume))
        await self._notify()
        return {}

    async def volume_up(self) -> dict[str, Any]:
        return await self.set_volume((self.tv_state.volume or 0) + 1)

    async def volume_down(self) -> dict[str, Any]:
        return await self.set_volume((self.tv_state.volume or 0) - 1)

    async def set_mute(self, mute: bool) -> dict[str, Any]:
        self.tv_state.muted = mute
        await self._notify()
        return {}

    async def get_apps(self) -> dict[str, Any] | None:
        return self.tv_state.apps

    async def get_inputs(self) -> dict[str, Any] | None:
        return self.tv_state.inputs

    async def button(self, name: str) -> None:
        pass

    async def play(self) -> dict[str, Any]:
        return {}

    async def pause(self) -> dict[str, Any]:
        return {}

    async def stop(self) -> dict[str, Any]:
        return {}

    async def rewind(self) -> dict[str, Any]:
        return {}

    async def fast_forward(self) -> dict[str, Any]:
        return {}

    async def set_input(self, input_id: str) -> dict[str, Any]:
        return await self.launch_app(input_id)

    async def send_message(self, message: str, icon_path: str | None = None) -> dict[str, Any]:
        return {}

    async def request(self, uri: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        if uri == "com.webos.service.capture/executeOneShot":
            return {"returnValue": True}
        return {}

    async def _notify(self) -> None:
        for cb in self._callbacks:
            await cb(self.tv_state)


if TYPE_CHECKING:
    _: type[TvState] = MockTvState
    __: type[TvClient] = MockTvClient
