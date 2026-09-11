# © MNELAB developers
#
# License: BSD (3-clause)

import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from mnelab.widgets import FlatDoubleSpinBox, set_tooltip


class CropDialog(QDialog):
    def __init__(
        self, parent, start, stop, events=None, event_mapping=None, sfreq=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Crop Data")
        self._max_stop = stop
        self._events = events if events is not None else np.empty((0, 3), dtype=int)
        self._event_mapping = event_mapping or {}
        self._sfreq = sfreq

        vbox = QVBoxLayout(self)

        # manual time range
        self.manual_radio = QRadioButton("Manual Time Range")
        self.manual_radio.setChecked(True)
        vbox.addWidget(self.manual_radio)

        self.manual_widget = QWidget()
        grid = QGridLayout(self.manual_widget)
        grid.setContentsMargins(20, 0, 0, 10)
        self.start_checkbox = QCheckBox("Start Time:")
        self.start_checkbox.setChecked(True)
        self.start_checkbox.stateChanged.connect(self.toggle_start)
        grid.addWidget(self.start_checkbox, 0, 0)
        self._start = FlatDoubleSpinBox()
        self._start.setMaximum(stop)
        self._start.setValue(start)
        self._start.setDecimals(2)
        self._start.setSuffix(" s")
        self._start.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._start.setMinimumWidth(140)
        set_tooltip("Crop data from this time", self.start_checkbox, self._start)
        grid.addWidget(self._start, 0, 1)

        self.stop_checkbox = QCheckBox("Stop Time:")
        self.stop_checkbox.setChecked(True)
        self.stop_checkbox.stateChanged.connect(self.toggle_stop)
        grid.addWidget(self.stop_checkbox, 1, 0)
        self._stop = FlatDoubleSpinBox()
        self._stop.setMaximum(stop)
        self._stop.setValue(stop)
        self._stop.setDecimals(2)
        self._stop.setSuffix(" s")
        self._stop.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._stop.setMinimumWidth(140)
        set_tooltip("Crop data until this time", self.stop_checkbox, self._stop)
        grid.addWidget(self._stop, 1, 1)
        vbox.addWidget(self.manual_widget)

        # event range
        self.event_radio = QRadioButton("From Event Range")
        vbox.addWidget(self.event_radio)

        self.crop_mode_group = QButtonGroup(self)
        self.crop_mode_group.addButton(self.manual_radio)
        self.crop_mode_group.addButton(self.event_radio)

        self.event_widget = QWidget()
        event_grid = QGridLayout(self.event_widget)
        event_grid.setContentsMargins(20, 0, 0, 0)
        event_grid.setColumnStretch(1, 1)

        event_label = QLabel("Event:")
        event_grid.addWidget(event_label, 0, 0)
        self.event_combo = QComboBox()
        self.event_combo.addItem("All Events", None)
        for event_id in sorted({int(e) for e in self._events[:, 2]}):
            label = self._event_mapping.get(event_id, "")
            text = f"{label} ({event_id})" if label else f"Event {event_id}"
            self.event_combo.addItem(text, event_id)
        event_grid.addWidget(self.event_combo, 0, 1)
        set_tooltip(
            "Use only events of this type to determine the crop range",
            event_label,
            self.event_combo,
        )

        before_label = QLabel("Before First Event:")
        event_grid.addWidget(before_label, 1, 0)
        self.before_spin = FlatDoubleSpinBox()
        self.before_spin.setMinimum(0)
        self.before_spin.setDecimals(2)
        self.before_spin.setValue(0.1)
        self.before_spin.setSingleStep(0.1)
        self.before_spin.setSuffix(" s")
        self.before_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        event_grid.addWidget(self.before_spin, 1, 1)
        set_tooltip(
            "Start cropping this many seconds before the first selected event",
            before_label,
            self.before_spin,
        )

        after_label = QLabel("After Last Event:")
        event_grid.addWidget(after_label, 2, 0)
        self.after_spin = FlatDoubleSpinBox()
        self.after_spin.setMinimum(0)
        self.after_spin.setDecimals(2)
        self.after_spin.setValue(0.5)
        self.after_spin.setSingleStep(0.1)
        self.after_spin.setSuffix(" s")
        self.after_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        event_grid.addWidget(self.after_spin, 2, 1)
        set_tooltip(
            "Stop cropping this many seconds after the last selected event",
            after_label,
            self.after_spin,
        )
        vbox.addWidget(self.event_widget)

        has_events = self._events.shape[0] > 0
        self.event_radio.setEnabled(has_events)
        if not has_events:
            self.event_radio.setToolTip("No events available")

        buttonbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        vbox.addWidget(buttonbox)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        self.crop_mode_group.buttonToggled.connect(self._update_mode)
        self._update_mode()

        vbox.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self.setFocus()

    @Slot()
    def _update_mode(self):
        is_event_mode = self.event_radio.isChecked()
        self.manual_widget.setEnabled(not is_event_mode)
        self.event_widget.setEnabled(is_event_mode)

    def _selected_event_times(self):
        event_id = self.event_combo.currentData()
        events = self._events
        if event_id is not None:
            events = events[events[:, 2] == event_id]
        times = events[:, 0] / self._sfreq
        return times.min(), times.max()

    @property
    def start(self):
        if self.event_radio.isChecked():
            first, _ = self._selected_event_times()
            return max(first - self.before_spin.value(), 0.0)
        if self.start_checkbox.isChecked():
            return self._start.value()
        else:
            return None

    @property
    def stop(self):
        if self.event_radio.isChecked():
            _, last = self._selected_event_times()
            return min(last + self.after_spin.value(), self._max_stop)
        if self.stop_checkbox.isChecked():
            return self._stop.value()
        else:
            return None

    @Slot()
    def toggle_start(self):
        if self.start_checkbox.isChecked():
            self._start.setEnabled(True)
        else:
            self._start.setEnabled(False)

    @Slot()
    def toggle_stop(self):
        if self.stop_checkbox.isChecked():
            self._stop.setEnabled(True)
        else:
            self._stop.setEnabled(False)
