# © MNELAB developers
#
# License: BSD (3-clause)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QVBoxLayout,
)

from mnelab.widgets import FlatDoubleSpinBox, set_tooltip


class FilterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Data")
        vbox = QVBoxLayout(self)

        # frequency filter (lowpass/highpass/bandpass, via independent cutoffs)
        freq_groupbox = QGroupBox("Frequency Filter")
        freq_grid = QGridLayout()

        self.lower_check = QCheckBox("Lower Cutoff Frequency (Hz):")
        self.lower_edit = FlatDoubleSpinBox()
        self.lower_edit.setMinimum(0)
        self.lower_edit.setDecimals(2)
        self.lower_edit.setValue(1)
        self.lower_edit.setSingleStep(0.5)
        self.lower_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lower_edit.setEnabled(False)
        set_tooltip(
            "Frequencies below this cutoff are attenuated",
            self.lower_check,
            self.lower_edit,
        )

        self.upper_check = QCheckBox("Upper Cutoff Frequency (Hz):")
        self.upper_check.setChecked(True)
        self.upper_edit = FlatDoubleSpinBox()
        self.upper_edit.setMinimum(0)
        self.upper_edit.setDecimals(2)
        self.upper_edit.setValue(30)
        self.upper_edit.setSingleStep(0.5)
        self.upper_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        set_tooltip(
            "Frequencies above this cutoff are attenuated",
            self.upper_check,
            self.upper_edit,
        )

        freq_grid.addWidget(self.lower_check, 0, 0)
        freq_grid.addWidget(self.lower_edit, 0, 1)
        freq_grid.addWidget(self.upper_check, 1, 0)
        freq_grid.addWidget(self.upper_edit, 1, 1)

        freq_groupbox.setLayout(freq_grid)
        vbox.addWidget(freq_groupbox)

        # notch filter
        notch_groupbox = QGroupBox("Notch Filter")
        notch_grid = QGridLayout()

        self.notch_check = QCheckBox("Notch Frequency (Hz):")
        self.notch_edit = FlatDoubleSpinBox()
        self.notch_edit.setMinimum(0)
        self.notch_edit.setDecimals(2)
        self.notch_edit.setValue(50)
        self.notch_edit.setSingleStep(0.5)
        self.notch_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.notch_edit.setEnabled(False)
        set_tooltip(
            "Frequencies around this value are attenuated",
            self.notch_check,
            self.notch_edit,
        )

        notch_grid.addWidget(self.notch_check, 0, 0)
        notch_grid.addWidget(self.notch_edit, 0, 1)

        notch_groupbox.setLayout(notch_grid)
        vbox.addWidget(notch_groupbox)

        # buttons
        self.buttonbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = self.buttonbox.button(QDialogButtonBox.StandardButton.Ok)
        vbox.addWidget(self.buttonbox)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)

        self.lower_check.toggled.connect(self.lower_edit.setEnabled)
        self.upper_check.toggled.connect(self.upper_edit.setEnabled)
        self.notch_check.toggled.connect(self.notch_edit.setEnabled)

        self.lower_check.toggled.connect(self.validate_inputs)
        self.upper_check.toggled.connect(self.validate_inputs)
        self.notch_check.toggled.connect(self.validate_inputs)
        self.lower_edit.valueChanged.connect(self.validate_inputs)
        self.upper_edit.valueChanged.connect(self.validate_inputs)
        self.notch_edit.valueChanged.connect(self.validate_inputs)

        self.validate_inputs()
        vbox.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self.setFocus()

    def validate_inputs(self):
        freq_valid = True
        if self.lower_check.isChecked() and self.upper_check.isChecked():
            freq_valid = self.upper_edit.value() > self.lower_edit.value()
        elif self.lower_check.isChecked():
            freq_valid = self.lower_edit.value() > 0
        elif self.upper_check.isChecked():
            freq_valid = self.upper_edit.value() > 0

        notch_valid = not self.notch_check.isChecked() or self.notch_edit.value() > 0

        any_enabled = (
            self.lower_check.isChecked()
            or self.upper_check.isChecked()
            or self.notch_check.isChecked()
        )

        self.ok_button.setEnabled(any_enabled and freq_valid and notch_valid)

    @property
    def lower(self):
        return float(self.lower_edit.value()) if self.lower_check.isChecked() else None

    @property
    def upper(self):
        return float(self.upper_edit.value()) if self.upper_check.isChecked() else None

    @property
    def notch(self):
        return float(self.notch_edit.value()) if self.notch_check.isChecked() else None
