from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from lgtv_remote.config import ConfigStore, TvConfig
from lgtv_remote.connection import ConnectionManager
from lgtv_remote.protocols import TvClient
from lgtv_remote.constants import SCREENSHOT_HEIGHT, SCREENSHOT_WIDTH

_log = logging.getLogger(__name__)

_CAPTURE_URI = "com.webos.service.capture/executeOneShot"
_CAPTURE_PAYLOAD = {
    "path": "/tmp/screenshot.jpg",
    "method": "DISPLAY",
    "format": "JPEG",
    "width": SCREENSHOT_WIDTH,
    "height": SCREENSHOT_HEIGHT,
}
_DEFAULT_SSH_PORT = 9922
_DEFAULT_SSH_USER = "prisoner"


class ScreenshotService(QObject):
    screenshot_ready = Signal(QPixmap)
    screenshot_cleared = Signal()

    def __init__(
        self,
        conn: ConnectionManager,
        config: ConfigStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._config = config
        self._capturing = False
        self._active = False
        self._had_screenshot = False
        self._interval: int = 0
        self._interval_task: asyncio.Task[None] | None = None

        xdg = os.environ.get(
            "XDG_CACHE_HOME", str(Path.home() / ".cache")
        )
        self._cache_dir = Path(xdg) / "lgtv-remote"
        self._cache_path = self._cache_dir / "screenshot.jpg"

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.capture_once()
            self._start_interval_loop()
        else:
            self._stop_interval_loop()
            if self._had_screenshot:
                self._had_screenshot = False
                self.screenshot_cleared.emit()

    def capture_once(self, delay: float = 0) -> None:
        if self._active:
            asyncio.ensure_future(self._capture(delay))

    def set_interval(self, seconds: int) -> None:
        self._interval = seconds
        if self._active:
            self._stop_interval_loop()
            self._start_interval_loop()

    def stop(self) -> None:
        self._active = False
        self._stop_interval_loop()

    def _start_interval_loop(self) -> None:
        self._stop_interval_loop()
        if self._interval > 0:
            self._interval_task = asyncio.ensure_future(self._interval_loop())

    def _stop_interval_loop(self) -> None:
        if self._interval_task is not None:
            self._interval_task.cancel()
            self._interval_task = None

    async def _interval_loop(self) -> None:
        try:
            while self._active and self._interval > 0:
                await asyncio.sleep(self._interval)
                if self._active and self._interval > 0:
                    await self._capture()
        except asyncio.CancelledError:
            pass

    async def _capture(self, delay: float = 0) -> None:
        if delay > 0:
            await asyncio.sleep(delay)

        if self._capturing:
            return

        tv = self._config.active_tv
        if not tv or not tv.ssh_enabled:
            if self._had_screenshot:
                self._had_screenshot = False
                self.screenshot_cleared.emit()
            return

        client = self._conn.client
        if not client or not client.is_connected():
            return

        self._capturing = True
        try:
            await self._do_capture(tv, client)
        except Exception:
            _log.debug("screenshot capture failed", exc_info=True)
        finally:
            self._capturing = False

    async def _do_capture(self, tv: TvConfig, client: TvClient) -> None:
        await client.request(_CAPTURE_URI, dict(_CAPTURE_PAYLOAD))

        host = tv.ssh_host or tv.host
        port = str(tv.ssh_port or _DEFAULT_SSH_PORT)
        user = tv.ssh_user or _DEFAULT_SSH_USER

        cmd = [
            "scp",
            "-P", port,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=5",
        ]
        if tv.ssh_key_path:
            cmd.extend(["-i", tv.ssh_key_path])

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cmd.append(f"{user}@{host}:/tmp/screenshot.jpg")
        cmd.append(str(self._cache_path))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            _log.warning(
                "scp failed (rc=%d): %s",
                proc.returncode,
                stderr.decode(errors="replace").strip(),
            )
            return

        pixmap = QPixmap(str(self._cache_path))
        if pixmap.isNull():
            _log.warning("failed to load screenshot pixmap from %s", self._cache_path)
            return

        self._had_screenshot = True
        self.screenshot_ready.emit(pixmap)
