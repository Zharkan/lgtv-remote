from __future__ import annotations

import asyncio
import uuid
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot

from lgtv_remote.config import TvConfig
from lgtv_remote.discovery import DiscoveredTv, discover_tvs, resolve_mac
from lgtv_remote.network import normalize_mac
from lgtv_remote.protocols import TvState


class SetupWizard(QDialog):
    tv_configured = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add TV")
        self.setMinimumSize(380, 400)
        self._discovered: list[DiscoveredTv] = []

        layout = QVBoxLayout(self)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._build_discovery_page()
        self._build_manual_page()
        self._build_pairing_page()
        self._build_done_page()

        self._stack.setCurrentIndex(0)
        asyncio.ensure_future(self._run_discovery())

    def _build_discovery_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Scanning for LG TVs on your network..."))
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        self._tv_list = QListWidget()
        layout.addWidget(self._tv_list)

        btn_row = QHBoxLayout()
        self._manual_btn = QPushButton("Enter manually")
        self._manual_btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        btn_row.addWidget(self._manual_btn)
        btn_row.addStretch()
        self._rescan_btn = QPushButton("Rescan")
        self._rescan_btn.clicked.connect(self._on_rescan)
        btn_row.addWidget(self._rescan_btn)
        self._select_btn = QPushButton("Select")
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._on_select_discovered)
        btn_row.addWidget(self._select_btn)
        layout.addLayout(btn_row)

        self._tv_list.currentRowChanged.connect(
            lambda r: self._select_btn.setEnabled(r >= 0)
        )
        self._stack.addWidget(page)

    def _build_manual_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Enter TV details:"))

        layout.addWidget(QLabel("Label:"))
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. Living Room TV")
        layout.addWidget(self._label_edit)

        layout.addWidget(QLabel("IP Address:"))
        self._ip_edit = QLineEdit()
        self._ip_edit.setPlaceholderText("e.g. 192.168.10.42")
        layout.addWidget(self._ip_edit)

        layout.addWidget(QLabel("MAC Address (for Wake-on-LAN):"))
        self._mac_edit = QLineEdit()
        self._mac_edit.setPlaceholderText("e.g. F8:01:B4:A5:D8:B2 (optional)")
        layout.addWidget(self._mac_edit)

        layout.addStretch()
        btn_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        pair_btn = QPushButton("Connect && Pair")
        pair_btn.clicked.connect(self._on_manual_pair)
        btn_row.addWidget(pair_btn)
        layout.addLayout(btn_row)
        self._stack.addWidget(page)

    def _build_pairing_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        self._pairing_label = QLabel(
            "Please accept the connection prompt\n"
            "on your TV screen using the physical remote."
        )
        self._pairing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pairing_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._pairing_label)
        self._pairing_progress = QProgressBar()
        self._pairing_progress.setRange(0, 0)
        layout.addWidget(self._pairing_progress)
        self._pairing_status = QLabel("Waiting for TV...")
        self._pairing_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pairing_status)
        layout.addStretch()
        self._stack.addWidget(page)

    def _build_done_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        self._done_label = QLabel("Connected!")
        self._done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self._done_label)
        layout.addStretch()
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn)
        self._stack.addWidget(page)

    @asyncSlot()
    async def _run_discovery(self) -> None:
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._tv_list.clear()

        def _on_progress(current: int, total: int) -> None:
            self._progress.setRange(0, total)
            self._progress.setValue(current)

        try:
            self._discovered = await discover_tvs(
                timeout=5.0, progress_callback=_on_progress
            )
        except Exception:
            self._discovered = []
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        if not self._discovered:
            self._tv_list.addItem("No TVs found. Try manual entry.")
        else:
            for tv in self._discovered:
                name = tv.friendly_name
                if tv.model_name:
                    name += f" ({tv.model_name})"
                item = QListWidgetItem(f"{name} - {tv.host}")
                self._tv_list.addItem(item)

    @asyncSlot()
    async def _on_rescan(self) -> None:
        await self._run_discovery()

    @asyncSlot()
    async def _on_select_discovered(self) -> None:
        row = self._tv_list.currentRow()
        if row < 0 or row >= len(self._discovered):
            return
        tv = self._discovered[row]
        mac = await resolve_mac(tv.host)
        await self._start_pairing(tv.host, tv.friendly_name, mac)

    @asyncSlot()
    async def _on_manual_pair(self) -> None:
        host = self._ip_edit.text().strip()
        label = self._label_edit.text().strip() or host
        mac_text = self._mac_edit.text().strip()

        if not host:
            QMessageBox.warning(self, "Missing IP", "Please enter the TV's IP address.")
            return

        mac: str | None = None
        if mac_text:
            try:
                mac = normalize_mac(mac_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid MAC", "Please check the MAC address format.")
                return
        else:
            mac = await resolve_mac(host)

        await self._start_pairing(host, label, mac)

    async def _start_pairing(
        self, host: str, label: str, mac: str | None
    ) -> None:
        self._stack.setCurrentIndex(2)
        self._pairing_status.setText("Connecting...")

        try:
            from aiowebostv import WebOsClient

            client = WebOsClient(host)
            await client.register_state_update_callback(self._noop_callback)
            await asyncio.wait_for(client.connect(), timeout=120)

            tv_config = TvConfig(
                id=str(uuid.uuid4()),
                label=label,
                host=host,
                mac=mac,
                client_key=client.client_key,
            )
            await client.disconnect()

            self._done_label.setText(f"Connected to {label}!")
            self._stack.setCurrentIndex(3)
            self.tv_configured.emit(tv_config)

        except TimeoutError:
            self._pairing_status.setText(
                "Timed out waiting for pairing.\n"
                "Make sure to accept the prompt on the TV."
            )
            self._pairing_progress.setRange(0, 1)
            self._pairing_progress.setValue(0)
        except Exception as e:
            self._pairing_status.setText(f"Connection failed: {e}")
            self._pairing_progress.setRange(0, 1)
            self._pairing_progress.setValue(0)

    async def _noop_callback(self, state: TvState) -> None:
        pass
