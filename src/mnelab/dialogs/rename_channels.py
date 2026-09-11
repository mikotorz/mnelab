# © MNELAB developers
#
# License: BSD (3-clause)

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from mnelab.dialogs.utils import set_header_alignments
from mnelab.widgets import FlatDoubleSpinBox


class RenameChannelsDialog(QDialog):
    def __init__(self, parent, channels):
        super().__init__(parent)
        self.setWindowTitle("Rename Channels")

        self.old_names = channels

        self.method = QComboBox()
        self.method.addItems(["Strip characters", "Delete characters"])
        self.method.setCurrentIndex(0)
        self.method.setToolTip("Choose how to remove characters from channel names")

        self.begin_strip_chars = QLineEdit()
        self.begin_strip_chars.setToolTip(
            "Enter characters to strip from the beginning of channel names"
        )
        self.begin_slice_num = FlatDoubleSpinBox()
        self.begin_slice_num.setMinimum(0)
        self.begin_slice_num.setDecimals(0)
        self.begin_slice_num.setToolTip(
            "Set the number of characters to remove from the beginning of channel names"
        )

        self.end_strip_chars = QLineEdit()
        self.end_strip_chars.setToolTip(
            "Enter characters to strip from the end of channel names"
        )
        self.end_slice_num = FlatDoubleSpinBox()
        self.end_slice_num.setMinimum(0)
        self.end_slice_num.setDecimals(0)
        self.end_slice_num.setToolTip(
            "Set the number of characters to remove from the end of channel names"
        )

        option_grid = QGridLayout()
        option_grid.setColumnStretch(0, 1)
        option_grid.setColumnStretch(1, 1)
        option_grid.addWidget(self.method, 0, 0, 1, 2)
        option_grid.addWidget(QLabel("From beginning"), 1, 0)
        option_grid.addWidget(self.begin_strip_chars, 1, 1)
        option_grid.addWidget(self.begin_slice_num, 1, 1)
        option_grid.addWidget(QLabel("From end"), 2, 0)
        option_grid.addWidget(self.end_strip_chars, 2, 1)
        option_grid.addWidget(self.end_slice_num, 2, 1)

        self.preview = QTableWidget(len(channels), 2)
        self.preview.setHorizontalHeaderLabels(["Before", "After"])
        set_header_alignments(self.preview, "ll")
        self.preview.horizontalHeader().setStretchLastSection(True)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setShowGrid(False)
        self.preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview.setColumnWidth(0, 190)
        self.preview.setColumnWidth(1, 190)
        self.preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        vbox = QVBoxLayout(self)
        vbox.addLayout(option_grid)
        vbox.addSpacing(10)
        header_font = QFont(QApplication.font())
        header_font.setPointSizeF(header_font.pointSizeF() * 0.85)
        header_font.setBold(True)
        preview_header = QLabel("Preview")
        preview_header.setFont(header_font)
        vbox.addWidget(preview_header)
        vbox.addWidget(self.preview)

        self.buttonbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        vbox.addWidget(self.buttonbox)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)

        self.method.currentTextChanged.connect(self.toggle_input)
        self.method.currentTextChanged.connect(self.update_preview)
        self.begin_strip_chars.textEdited.connect(self.update_preview)
        self.begin_slice_num.valueChanged.connect(self.update_preview)
        self.end_strip_chars.textEdited.connect(self.update_preview)
        self.end_slice_num.valueChanged.connect(self.update_preview)

        self.toggle_input()
        self.update_preview()
        self.setFixedSize(450, 480)
        self.setFocus()

    @property
    def mapping(self):
        """Return the selected channel renaming function."""
        if self.method.currentText() == "Strip characters":
            begin_chars = self.begin_strip_chars.text()
            end_chars = self.end_strip_chars.text()
            return lambda name: name.lstrip(begin_chars).rstrip(end_chars)

        begin_num = int(self.begin_slice_num.value())
        end_num = int(self.end_slice_num.value())
        return lambda name: name[begin_num : len(name) - end_num]

    @property
    def history_mapping(self):
        """Return the selected channel renaming function as history code."""
        if self.method.currentText() == "Strip characters":
            begin_chars = self.begin_strip_chars.text()
            end_chars = self.end_strip_chars.text()
            return f"lambda name: name.lstrip({begin_chars!r}).rstrip({end_chars!r})"

        begin_num = int(self.begin_slice_num.value())
        end_num = int(self.end_slice_num.value())
        return f"lambda name: name[{begin_num}:len(name) - {end_num}]"

    @Slot()
    def toggle_input(self):
        if self.method.currentText() == "Strip characters":
            self.begin_strip_chars.setVisible(True)
            self.begin_slice_num.setVisible(False)
            self.end_strip_chars.setVisible(True)
            self.end_slice_num.setVisible(False)
        elif self.method.currentText() == "Delete characters":
            self.begin_strip_chars.setVisible(False)
            self.begin_slice_num.setVisible(True)
            self.end_strip_chars.setVisible(False)
            self.end_slice_num.setVisible(True)

    @Slot()
    def update_preview(self):
        self.new_names = [self.mapping(name) for name in self.old_names]
        for row, (old, new) in enumerate(zip(self.old_names, self.new_names)):
            self.preview.setItem(row, 0, QTableWidgetItem(old))
            self.preview.setItem(row, 1, QTableWidgetItem(new))
