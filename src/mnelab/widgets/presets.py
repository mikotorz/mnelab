# © MNELAB developers
#
# License: BSD (3-clause)

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from mnelab import presets
from mnelab.widgets.utils import set_tooltip


class PresetBar(QWidget):
    """A row of controls for saving, loading, and deleting named dialog presets.

    Selecting a preset from the combo box applies it immediately. The combo box reflects
    the last preset applied, not the dialog's current field values, so editing fields
    after loading a preset does not clear the selection.
    """

    def __init__(self, parent, category, get_values, set_values, defaults):
        super().__init__(parent)
        self.category = category
        self._get_values = get_values
        self._set_values = set_values
        self._defaults = defaults

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Preset:")
        self.combo = QComboBox()
        self.combo.setPlaceholderText("Select Preset...")
        set_tooltip("Load a saved preset", label, self.combo)
        self.combo.activated.connect(self._apply_selected)
        self.combo.currentIndexChanged.connect(self._update_delete_button)

        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Save the current values as a named preset")
        self.save_button.clicked.connect(self._save)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setToolTip("Delete the selected preset")
        self.delete_button.clicked.connect(self._delete)

        self.restore_button = QPushButton("Restore Defaults")
        self.restore_button.setToolTip("Reset all fields to their built-in defaults")
        self.restore_button.clicked.connect(self._restore_defaults)

        hbox.addWidget(label)
        hbox.addWidget(self.combo, 1)
        hbox.addWidget(self.save_button)
        hbox.addWidget(self.delete_button)
        hbox.addWidget(self.restore_button)

        self._reload_presets()

    def _reload_presets(self, select=None):
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(presets.list_presets(self.category))
        self.combo.setCurrentIndex(self.combo.findText(select) if select else -1)
        self.combo.blockSignals(False)
        self._update_delete_button()

    def _apply_selected(self, index):
        name = self.combo.itemText(index)
        self._set_values(presets.load_preset(self.category, name))

    def _update_delete_button(self):
        self.delete_button.setEnabled(bool(self.combo.currentText()))

    def _save(self):
        name, ok = QInputDialog.getText(
            self, "Save Preset", "Preset name:", text=self.combo.currentText()
        )
        name = name.strip()
        if not ok or not name:
            return
        if name in presets.list_presets(self.category):
            reply = QMessageBox.question(
                self,
                "Overwrite preset",
                f'A preset named "{name}" already exists. Overwrite it?',
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        presets.save_preset(self.category, name, self._get_values())
        self._reload_presets(select=name)

    def _delete(self):
        name = self.combo.currentText()
        if not name:
            return
        reply = QMessageBox.question(self, "Delete preset", f'Delete preset "{name}"?')
        if reply != QMessageBox.StandardButton.Yes:
            return
        presets.delete_preset(self.category, name)
        self._reload_presets()

    def _restore_defaults(self):
        self._set_values(self._defaults)
        self.combo.setCurrentIndex(-1)
