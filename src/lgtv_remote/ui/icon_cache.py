from __future__ import annotations

import hashlib
import os
from pathlib import Path

import aiohttp
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap


class IconCache(QObject):
    icon_ready = Signal(str, QPixmap)

    ICON_SIZE = 64

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        xdg = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        self._cache_dir = Path(xdg) / "lgtv-remote" / "icons"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, QPixmap] = {}

    def get(self, app_id: str) -> QPixmap | None:
        return self._mem.get(app_id)

    def _cache_path(self, app_id: str) -> Path:
        h = hashlib.md5(app_id.encode()).hexdigest()
        return self._cache_dir / f"{h}.png"

    async def ensure(self, app_id: str, icon_url: str) -> None:
        if app_id in self._mem:
            return

        cache_file = self._cache_path(app_id)
        if cache_file.exists():
            pm = QPixmap(str(cache_file))
            if not pm.isNull():
                pm = pm.scaled(
                    self.ICON_SIZE,
                    self.ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._mem[app_id] = pm
                self.icon_ready.emit(app_id, pm)
                return

        if not icon_url:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    icon_url,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    data = await resp.read()
            pm = QPixmap()
            pm.loadFromData(data)
            if pm.isNull():
                return
            pm = pm.scaled(
                self.ICON_SIZE,
                self.ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pm.save(str(cache_file), "PNG")
            self._mem[app_id] = pm
            self.icon_ready.emit(app_id, pm)
        except Exception:
            pass
