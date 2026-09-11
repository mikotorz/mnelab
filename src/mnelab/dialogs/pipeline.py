# © MNELAB developers
#
# License: BSD (3-clause)

from dataclasses import dataclass, field

import mne
from mne import channel_type
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from mnelab.dialogs.channel_properties import ChannelPropertiesDialog
from mnelab.dialogs.crop import CropDialog
from mnelab.dialogs.filter import FilterDialog
from mnelab.dialogs.montage import MontageDialog
from mnelab.dialogs.rename_channels import RenameChannelsDialog
from mnelab.dialogs.resample import ResampleDialog
from mnelab.dialogs.run_ica import RunICADialog
from mnelab.utils import have, natural_sort

STEP_DEFINITIONS = [
    ("montage", "Apply Montage..."),
    ("bads", "Mark Bad Channels..."),
    ("rename", "Rename Channels..."),
    ("filter", "Filter Data..."),
    ("resample", "Resample Data..."),
    ("crop", "Crop Data..."),
    ("events_from_annotations", "Events from Annotations"),
    ("run_ica", "Run ICA..."),
]


@dataclass
class PipelineStep:
    """A single configured step of a preprocessing pipeline."""

    kind: str
    label: str
    params: dict = field(default_factory=dict)


class PipelineDialog(QDialog):
    """Build an ordered sequence of preprocessing steps to run in one go."""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.setWindowTitle("Preprocessing Pipeline")
        self.resize(560, 420)

        data = model.current["data"]
        self._info = data.info
        self._ch_names = data.info["ch_names"]
        self._dtype = model.current["dtype"]
        self._sfreq = data.info["sfreq"]
        self._nchan = data.info["nchan"]
        self._highpass = data.info["highpass"]
        self._current_montage = model.current["montage"]
        self._times = data.times if self._dtype == "raw" else None
        self._annot = bool(data.annotations) if self._dtype == "raw" else False
        self._events = model.current["events"]
        self._event_mapping = model.current["event_mapping"]

        self.steps: list[PipelineStep] = []

        hbox = QHBoxLayout()

        available_vbox = QVBoxLayout()
        available_vbox.addWidget(QLabel("Available Steps"))
        self.available_list = QListWidget()
        for kind, label in STEP_DEFINITIONS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, kind)
            if not self._is_step_available(kind):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.available_list.addItem(item)
        self.available_list.itemDoubleClicked.connect(self._add_selected_step)
        available_vbox.addWidget(self.available_list)
        self.add_button = QPushButton("Add Step →")
        self.add_button.clicked.connect(self._add_selected_step)
        available_vbox.addWidget(self.add_button)
        hbox.addLayout(available_vbox)

        steps_vbox = QVBoxLayout()
        steps_vbox.addWidget(QLabel("Pipeline Steps"))
        self.steps_list = QListWidget()
        self.steps_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        steps_vbox.addWidget(self.steps_list)
        buttons_hbox = QHBoxLayout()
        self.up_button = QPushButton("Move Up")
        self.up_button.clicked.connect(self._move_step_up)
        self.down_button = QPushButton("Move Down")
        self.down_button.clicked.connect(self._move_step_down)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_step)
        buttons_hbox.addWidget(self.up_button)
        buttons_hbox.addWidget(self.down_button)
        buttons_hbox.addWidget(self.remove_button)
        steps_vbox.addLayout(buttons_hbox)
        hbox.addLayout(steps_vbox)

        vbox = QVBoxLayout(self)
        vbox.addLayout(hbox)

        self.buttonbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.run_button = self.buttonbox.button(QDialogButtonBox.StandardButton.Ok)
        self.run_button.setText("Run")
        self.run_button.setEnabled(False)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        vbox.addWidget(self.buttonbox)

        self.setFocus()

    def _is_step_available(self, kind):
        if kind == "resample":
            return self._dtype in ("raw", "epochs")
        if kind == "crop":
            return self._dtype == "raw"
        if kind == "events_from_annotations":
            return self._dtype == "raw" and self._annot
        return True

    def _effective_info(self):
        """Return channel info as it will be once queued steps have run."""
        info = self._info.copy()
        for step in self.steps:
            if step.kind == "rename":
                mne.rename_channels(info, step.params["mapping"])
            elif step.kind == "bads":
                bads = step.params.get("bads")
                if bads is not None:
                    info["bads"] = bads
                names = step.params.get("names")
                if names:
                    mne.rename_channels(info, names)
                types = step.params.get("types")
                if types:
                    info.set_channel_types(types)
        return info

    def _effective_ch_names(self):
        """Return channel names as they will be once queued steps have run."""
        return self._effective_info()["ch_names"]

    def _effective_highpass(self):
        """Return the high-pass cutoff as it will be once queued steps have run."""
        highpass = self._highpass
        for step in self.steps:
            if step.kind == "filter":
                lower = step.params.get("lower")
                if lower is not None:
                    highpass = max(highpass, lower)
        return highpass

    def _add_selected_step(self):
        item = self.available_list.currentItem()
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        kind = item.data(Qt.ItemDataRole.UserRole)
        if kind == "montage":
            self._add_montage_step()
        elif kind == "bads":
            self._add_bads_step()
        elif kind == "rename":
            self._add_rename_step()
        elif kind == "filter":
            self._add_filter_step()
        elif kind == "resample":
            self._add_resample_step()
        elif kind == "crop":
            self._add_crop_step()
        elif kind == "events_from_annotations":
            self._add_events_from_annotations_step()
        elif kind == "run_ica":
            self._add_run_ica_step()

    def _add_montage_step(self):
        montages = natural_sort(mne.channels.get_builtin_montages())
        dialog = MontageDialog(self, montages, current_montage=self._current_montage)
        if not dialog.exec():
            return
        montage = dialog.montage
        if montage is None:
            self._append_step(
                PipelineStep("montage", "Apply Montage: none", {"montage": None})
            )
            return
        if not set(self._effective_ch_names()) & set(montage.montage.ch_names):
            QMessageBox.critical(
                self,
                "No matching channel names",
                "Channel names defined in the montage do not match any channel name"
                " in the data.",
            )
            return
        params = {
            "montage": montage,
            "match_case": dialog.match_case.isChecked(),
            "match_alias": dialog.match_alias.isChecked(),
            "on_missing": "ignore" if dialog.ignore_missing.isChecked() else "raise",
        }
        self._append_step(
            PipelineStep("montage", f"Apply Montage: {montage.name}", params)
        )

    def _add_bads_step(self):
        info = self._effective_info()
        ch_names = info["ch_names"]
        dialog = ChannelPropertiesDialog(self, info, title="Mark Bad Channels")
        if not dialog.exec():
            return
        dialog.model.sort(0)
        bads = []
        renamed = {}
        types = {}
        for i in range(dialog.model.rowCount()):
            new_label = dialog.model.item(i, 1).data(Qt.ItemDataRole.DisplayRole)
            old_label = ch_names[i]
            if new_label != old_label:
                renamed[old_label] = new_label
            new_type = dialog.model.item(i, 2).data(Qt.ItemDataRole.DisplayRole).lower()
            old_type = channel_type(info, i).lower()
            if new_type != old_type:
                types[new_label] = new_type
            if dialog.model.item(i, 3).checkState() == Qt.CheckState.Checked:
                bads.append(ch_names[i])
        label = f"Mark Bad Channels: {', '.join(bads) if bads else 'none'}"
        params = {"bads": bads, "names": renamed, "types": types}
        self._append_step(PipelineStep("bads", label, params))

    def _add_rename_step(self):
        ch_names = self._effective_ch_names()
        dialog = RenameChannelsDialog(self, ch_names)
        if not dialog.exec():
            return
        if dialog.new_names == ch_names:
            return
        params = {
            "mapping": dialog.mapping,
            "history_mapping": dialog.history_mapping,
        }
        label = f"Rename Channels: {dialog.history_mapping}"
        self._append_step(PipelineStep("rename", label, params))

    def _add_filter_step(self):
        dialog = FilterDialog(self)
        if not dialog.exec():
            return
        params = {"lower": dialog.lower, "upper": dialog.upper, "notch": dialog.notch}
        parts = []
        if dialog.lower is not None and dialog.upper is not None:
            parts.append(f"{dialog.lower:g}-{dialog.upper:g} Hz")
        elif dialog.lower is not None:
            parts.append(f">{dialog.lower:g} Hz")
        elif dialog.upper is not None:
            parts.append(f"<{dialog.upper:g} Hz")
        if dialog.notch is not None:
            parts.append(f"notch {dialog.notch:g} Hz")
        label = f"Filter Data: {', '.join(parts)}"
        self._append_step(PipelineStep("filter", label, params))

    def _add_resample_step(self):
        dialog = ResampleDialog(self, self._sfreq)
        if not dialog.exec():
            return
        label = f"Resample Data: {dialog.new_sfreq:g} Hz"
        self._append_step(PipelineStep("resample", label, {"sfreq": dialog.new_sfreq}))

    def _add_crop_step(self):
        stop = self._times[-1]
        dialog = CropDialog(
            self,
            0,
            stop,
            events=self._events,
            event_mapping=self._event_mapping,
            sfreq=self._sfreq,
        )
        if not dialog.exec():
            return
        start = max(dialog.start, 0) if dialog.start is not None else 0
        end = min(dialog.stop, stop) if dialog.stop is not None else stop
        label = f"Crop Data: {start:g}-{end:g} s"
        self._append_step(PipelineStep("crop", label, {"start": start, "stop": end}))

    def _add_events_from_annotations_step(self):
        self._append_step(
            PipelineStep("events_from_annotations", "Events from Annotations", {})
        )

    def _add_run_ica_step(self):
        methods = ["Infomax"]
        if have["python-picard"]:
            methods.insert(0, "Picard")
        if have["scikit-learn"]:
            methods.append("FastICA")
        dialog = RunICADialog(self, self._nchan, self._effective_highpass(), methods)
        if not dialog.exec():
            return
        method = dialog.method.currentText().lower()
        n_components = dialog.n_components.value()
        exclude_bad_segments = dialog.exclude_bad_segments.isChecked()
        fit_params = {}
        if dialog.extended.isEnabled():
            fit_params["extended"] = dialog.extended.isChecked()
        if dialog.ortho.isEnabled():
            fit_params["ortho"] = dialog.ortho.isChecked()
        params = {
            "method": method,
            "n_components": n_components,
            "fit_params": fit_params,
            "exclude_bad_segments": exclude_bad_segments,
        }
        label = f"Run ICA: {method}, {n_components} components"
        self._append_step(PipelineStep("run_ica", label, params))

    def _append_step(self, step):
        self.steps.append(step)
        self.steps_list.addItem(QListWidgetItem(step.label))
        self.run_button.setEnabled(True)

    def _move_step_up(self):
        row = self.steps_list.currentRow()
        if row <= 0:
            return
        self.steps[row - 1], self.steps[row] = self.steps[row], self.steps[row - 1]
        self._refresh_steps_list(selected_row=row - 1)

    def _move_step_down(self):
        row = self.steps_list.currentRow()
        if row < 0 or row >= len(self.steps) - 1:
            return
        self.steps[row + 1], self.steps[row] = self.steps[row], self.steps[row + 1]
        self._refresh_steps_list(selected_row=row + 1)

    def _remove_step(self):
        row = self.steps_list.currentRow()
        if row < 0:
            return
        del self.steps[row]
        self._refresh_steps_list()
        self.run_button.setEnabled(bool(self.steps))

    def _refresh_steps_list(self, selected_row=None):
        self.steps_list.clear()
        for step in self.steps:
            self.steps_list.addItem(QListWidgetItem(step.label))
        if selected_row is not None and 0 <= selected_row < self.steps_list.count():
            self.steps_list.setCurrentRow(selected_row)
