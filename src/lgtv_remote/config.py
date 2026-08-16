from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lgtv_remote.constants import CONFIG_FILE_MODE


@dataclass
class TvConfig:
    id: str
    label: str
    host: str
    mac: str | None = None
    client_key: str | None = None
    ssh_enabled: bool = False
    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    screenshot_interval: int = 0

    @staticmethod
    def new(label: str, host: str, mac: str | None = None) -> TvConfig:
        return TvConfig(id=str(uuid.uuid4()), label=label, host=host, mac=mac)


@dataclass
class AppConfig:
    schema_version: int = 2
    active_tv_id: str | None = None
    tvs: list[TvConfig] = field(default_factory=list)
    minimize_to_tray: bool = False
    window_x: int | None = None
    window_y: int | None = None
    window_width: int | None = None
    window_height: int | None = None


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        self._dir = Path(path) if path else Path(xdg) / "lgtv-remote"
        self._file = self._dir / "config.json"
        self._config = self._load()

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def active_tv(self) -> TvConfig | None:
        if self._config.active_tv_id is None:
            return None
        for tv in self._config.tvs:
            if tv.id == self._config.active_tv_id:
                return tv
        return None

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        data = json.dumps(asdict(self._config), indent=2)
        fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            os.write(fd, data.encode())
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp, str(self._file))
            os.chmod(str(self._file), CONFIG_FILE_MODE)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def add_tv(self, tv: TvConfig) -> None:
        self._config.tvs.append(tv)
        if self._config.active_tv_id is None:
            self._config.active_tv_id = tv.id
        self.save()

    def remove_tv(self, tv_id: str) -> None:
        self._config.tvs = [t for t in self._config.tvs if t.id != tv_id]
        if self._config.active_tv_id == tv_id:
            self._config.active_tv_id = (
                self._config.tvs[0].id if self._config.tvs else None
            )
        self.save()

    def update_tv(self, tv: TvConfig) -> None:
        for i, t in enumerate(self._config.tvs):
            if t.id == tv.id:
                self._config.tvs[i] = tv
                break
        self.save()

    def set_active(self, tv_id: str) -> None:
        self._config.active_tv_id = tv_id
        self.save()

    def _load(self) -> AppConfig:
        if not self._file.exists():
            return AppConfig()
        try:
            config_data = json.loads(self._file.read_text())
            tvs = [TvConfig(**t) for t in config_data.get("tvs", [])]
            return AppConfig(
                schema_version=config_data.get("schema_version", 1),
                active_tv_id=config_data.get("active_tv_id"),
                tvs=tvs,
                minimize_to_tray=config_data.get("minimize_to_tray", False),
                window_x=config_data.get("window_x"),
                window_y=config_data.get("window_y"),
                window_width=config_data.get("window_width"),
                window_height=config_data.get("window_height"),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            return AppConfig()
