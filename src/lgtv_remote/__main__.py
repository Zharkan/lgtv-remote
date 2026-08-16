from __future__ import annotations

import os

os.environ["QT_API"] = "pyside6"

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from qasync import QEventLoop

from lgtv_remote.config import ConfigStore
from lgtv_remote.connection import ConnectionManager
from lgtv_remote.ui.main_window import MainWindow
from lgtv_remote.ui.style import load_stylesheet
from lgtv_remote.ui.tray_icon import TrayIcon


def _inject_mock_tvs(config_store: ConfigStore) -> None:
    from lgtv_remote.config import TvConfig
    from lgtv_remote.constants import MOCK_CLIENT_KEY
    from lgtv_remote.mock_client import MOCK_TV_PRESETS

    cfg = config_store.config
    cfg.tvs = [
        TvConfig(
            id=f"mock-{host.replace('.', '-')}",
            label=preset["label"],
            host=host,
            mac="AA:BB:CC:DD:EE:FF",
            client_key=MOCK_CLIENT_KEY,
        )
        for host, preset in MOCK_TV_PRESETS.items()
    ]
    cfg.active_tv_id = cfg.tvs[0].id


def main() -> None:
    parser = argparse.ArgumentParser(description="LG webOS TV Remote")
    parser.add_argument("--mock", action="store_true", help="Use mock TV client")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("lgtv-remote")
    app.setDesktopFileName("lgtv-remote")
    app.setStyleSheet(load_stylesheet())

    if args.mock:
        mock_dir = Path(tempfile.mkdtemp(prefix="lgtv-mock-"))
        config_store = ConfigStore(path=mock_dir)
        _inject_mock_tvs(config_store)
    else:
        config_store = ConfigStore()
    conn_manager = ConnectionManager(config_store, mock=args.mock)
    window = MainWindow(conn_manager, config_store)

    tray: TrayIcon | None = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon(conn_manager, config_store, window)
        tray.quit_requested.connect(window.request_quit)
        tray.setVisible(config_store.config.minimize_to_tray)
        window.tray_toggled.connect(tray.setVisible)
    else:
        config_store.config.minimize_to_tray = False

    window.show()

    loop = QEventLoop(app)
    with loop:
        loop.run_until_complete(_run(conn_manager, window))


async def _run(conn_manager: ConnectionManager, window: MainWindow) -> None:
    conn_manager.start()
    await window.wait_closed()


if __name__ == "__main__":
    main()
