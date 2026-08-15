from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lgtv_remote.config import ConfigStore, TvConfig
from lgtv_remote.ui.edit_tv_dialog import EditTvDialog
from lgtv_remote.ui.setup_wizard import SetupWizard


class SettingsDialog(QDialog):
    tv_added = Signal(object)
    tv_removed = Signal(str)
    tv_updated = Signal(object)

    def __init__(self, config: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(400, 350)
        self._config = config

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configured TVs:"))

        self._tv_list = QListWidget()
        layout.addWidget(self._tv_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add TV")
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(self._edit_btn)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)
        btn_row.addWidget(self._remove_btn)
        self._forget_btn = QPushButton("Forget Pairing")
        self._forget_btn.setEnabled(False)
        self._forget_btn.clicked.connect(self._on_forget)
        btn_row.addWidget(self._forget_btn)
        layout.addLayout(btn_row)

        self._connect_on_launch = QCheckBox("Connect on launch")
        self._connect_on_launch.setChecked(config.config.connect_on_launch)
        self._connect_on_launch.toggled.connect(self._on_connect_toggle)
        layout.addWidget(self._connect_on_launch)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._tv_list.currentRowChanged.connect(self._on_selection_changed)
        self._tv_list.itemDoubleClicked.connect(self._on_double_click)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._tv_list.clear()
        for tv in self._config.config.tvs:
            paired = "paired" if tv.client_key else "not paired"
            item = QListWidgetItem(f"{tv.label} ({tv.host}) [{paired}]")
            item.setData(Qt.ItemDataRole.UserRole, tv.id)
            self._tv_list.addItem(item)

    def _on_selection_changed(self, row: int) -> None:
        has_sel = row >= 0
        self._edit_btn.setEnabled(has_sel)
        self._remove_btn.setEnabled(has_sel)
        self._forget_btn.setEnabled(has_sel)

    def _selected_tv_id(self) -> str | None:
        item = self._tv_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self._on_edit()

    def _on_add(self) -> None:
        wizard = SetupWizard(self)
        wizard.tv_configured.connect(self._on_wizard_done)
        wizard.exec()

    def _on_wizard_done(self, tv: TvConfig) -> None:
        self._config.add_tv(tv)
        self._refresh_list()
        self.tv_added.emit(tv)

    def _on_edit(self) -> None:
        tv_id = self._selected_tv_id()
        if not tv_id:
            return
        tv = next((t for t in self._config.config.tvs if t.id == tv_id), None)
        if not tv:
            return

        dlg = EditTvDialog(tv, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tv.label = dlg.label
            tv.host = dlg.host
            tv.mac = dlg.mac
            tv.ssh_enabled = dlg.ssh_enabled
            tv.ssh_host = dlg.ssh_host
            tv.ssh_port = dlg.ssh_port
            tv.ssh_user = dlg.ssh_user
            tv.ssh_key_path = dlg.ssh_key_path
            tv.screenshot_interval = dlg.screenshot_interval
            self._config.update_tv(tv)
            self._refresh_list()
            self.tv_updated.emit(tv)

    def _on_remove(self) -> None:
        tv_id = self._selected_tv_id()
        if not tv_id:
            return
        reply = QMessageBox.question(
            self, "Remove TV", "Remove this TV from the configuration?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._config.remove_tv(tv_id)
            self._refresh_list()
            self.tv_removed.emit(tv_id)

    def _on_forget(self) -> None:
        tv_id = self._selected_tv_id()
        if not tv_id:
            return
        tv = next((t for t in self._config.config.tvs if t.id == tv_id), None)
        if tv:
            tv.client_key = None
            self._config.update_tv(tv)
            self._refresh_list()

    def _on_connect_toggle(self, checked: bool) -> None:
        self._config.config.connect_on_launch = checked
        self._config.save()
