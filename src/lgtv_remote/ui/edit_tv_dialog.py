from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from lgtv_remote.config import TvConfig
from lgtv_remote.network import normalize_mac


class EditTvDialog(QDialog):
    def __init__(self, tv: TvConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit TV")
        self.setMinimumWidth(440)
        self.label = tv.label
        self.host = tv.host
        self.mac = tv.mac
        self.ssh_enabled = tv.ssh_enabled
        self.ssh_host = tv.ssh_host
        self.ssh_port = tv.ssh_port
        self.ssh_user = tv.ssh_user
        self.ssh_key_path = tv.ssh_key_path

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(QLabel("Label:"))
        self._label_edit = QLineEdit(tv.label)
        layout.addWidget(self._label_edit)

        layout.addWidget(QLabel("IP Address:"))
        self._ip_edit = QLineEdit(tv.host)
        layout.addWidget(self._ip_edit)

        layout.addWidget(QLabel("MAC Address:"))
        self._mac_edit = QLineEdit(tv.mac or "")
        layout.addWidget(self._mac_edit)

        ssh_group = QGroupBox("SSH Screenshot (Developer Mode)")
        ssh_layout = QVBoxLayout(ssh_group)
        ssh_layout.setSpacing(10)

        self._ssh_check = QCheckBox("Enable live screenshot")
        self._ssh_check.setChecked(tv.ssh_enabled)
        ssh_layout.addWidget(self._ssh_check)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(QLabel("Private key:"))
        self._key_edit = QLineEdit(tv.ssh_key_path or "")
        self._key_edit.setPlaceholderText("~/.ssh/id_ed25519")
        key_row.addWidget(self._key_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_key)
        key_row.addWidget(browse_btn)
        ssh_layout.addLayout(key_row)

        host_row = QHBoxLayout()
        host_row.setSpacing(8)
        host_row.addWidget(QLabel("Host:"))
        self._ssh_host_edit = QLineEdit(tv.ssh_host or "")
        self._ssh_host_edit.setPlaceholderText("TV IP (defaults to TV address)")
        host_row.addWidget(self._ssh_host_edit)
        ssh_layout.addLayout(host_row)

        user_port_row = QHBoxLayout()
        user_port_row.setSpacing(8)
        user_port_row.addWidget(QLabel("User:"))
        self._ssh_user_edit = QLineEdit(tv.ssh_user or "")
        self._ssh_user_edit.setPlaceholderText("prisoner")
        user_port_row.addWidget(self._ssh_user_edit)

        user_port_row.addWidget(QLabel("Port:"))
        self._ssh_port_spin = QSpinBox()
        self._ssh_port_spin.setRange(1, 65535)
        self._ssh_port_spin.setValue(tv.ssh_port or 9922)
        self._ssh_port_spin.setFixedWidth(90)
        user_port_row.addWidget(self._ssh_port_spin)
        ssh_layout.addLayout(user_port_row)

        info = QLabel(
            "Requires Developer Mode on the TV with SSH enabled or root access. "
            "If the key has a passphrase, load it in ssh-agent first."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #5a7a72; font-size: 8pt;")
        ssh_layout.addWidget(info)

        layout.addWidget(ssh_group)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Private Key",
            str(Path.home() / ".ssh"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._key_edit.setText(path)

    def _on_save(self) -> None:
        self.label = self._label_edit.text().strip()
        self.host = self._ip_edit.text().strip()
        mac_text = self._mac_edit.text().strip()
        if mac_text:
            try:
                self.mac = normalize_mac(mac_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid MAC", "Check the MAC address format.")
                return
        else:
            self.mac = None

        if not self.host:
            QMessageBox.warning(self, "Missing IP", "IP address is required.")
            return

        self.ssh_enabled = self._ssh_check.isChecked()
        key_text = self._key_edit.text().strip()
        if self.ssh_enabled and key_text and not Path(key_text).is_file():
            QMessageBox.warning(
                self, "Invalid Key", "SSH private key file not found."
            )
            return
        self.ssh_key_path = key_text or None

        user_text = self._ssh_user_edit.text().strip()
        self.ssh_user = user_text or None

        host_text = self._ssh_host_edit.text().strip()
        self.ssh_host = host_text or None

        self.ssh_port = self._ssh_port_spin.value()

        self.accept()
