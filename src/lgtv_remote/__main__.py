from __future__ import annotations

import os

os.environ["QT_API"] = "pyside6"

import argparse
import asyncio
import logging
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from lgtv_remote.config import ConfigStore
from lgtv_remote.connection import ConnectionManager
from lgtv_remote.ui.main_window import MainWindow
from lgtv_remote.ui.style import load_stylesheet


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

    config_store = ConfigStore()
    conn_manager = ConnectionManager(config_store, mock=args.mock)
    window = MainWindow(conn_manager, config_store)
    window.show()

    loop = QEventLoop(app)
    with loop:
        loop.run_until_complete(_run(app, conn_manager))


async def _run(app: QApplication, conn_manager: ConnectionManager) -> None:
    stop_event = asyncio.Event()
    app.aboutToQuit.connect(stop_event.set)
    conn_manager.start()
    await stop_event.wait()
    await conn_manager.shutdown()


if __name__ == "__main__":
    main()
