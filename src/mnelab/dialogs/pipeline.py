# © MNELAB developers
#
# License: BSD (3-clause)

from collections.abc import Callable
from dataclasses import dataclass, field

import mne
import numpy as np
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mnelab.dialogs.channel_properties import ChannelPropertiesDialog
from mnelab.dialogs.crop import CropDialog
from mnelab.dialogs.drop_bad_epochs import DropBadEpochsDialog
from mnelab.dialogs.epoch import EpochDialog
from mnelab.dialogs.filter import FilterDialog
from mnelab.dialogs.montage import MontageDialog
from mnelab.dialogs.reference import ReferenceDialog
from mnelab.dialogs.remove_line_noise import RemoveLineNoiseDialog
from mnelab.dialogs.rename_channels import RenameChannelsDialog
from mnelab.dialogs.resample import ResampleDialog
from mnelab.dialogs.run_ica import RunICADialog
from mnelab.utils import count_locations, have, natural_sort


def _identity_preset(params):
    return dict(params)


@dataclass
class StepSpec:
    """Everything the pipeline dialog and executor need to know about a step kind."""

    label: str
    available: Callable[["_PipelineStageWidget"], bool]
    add: Callable[["_PipelineStageWidget"], None]
    run: Callable[["MainWindow"], None]  # noqa: F821
    to_preset: Callable[[dict], dict] = _identity_preset
    from_preset: Callable[[dict], dict] = _identity_preset


@dataclass
class PipelineStep:
    """A single configured step of a preprocessing pipeline."""

    kind: str
    label: str
    params: dict = field(default_factory=dict)


@dataclass
class StageContext:
    """The state a pipeline stage starts from.

    This is the model's original state for the first stage, or the state produced
    by every step queued in the previous stage for any later one.
    """

    data: object
    info: object
    dtype: str
    sfreq: float
    nchan: int
    highpass: float
    montage: object
    times: object
    annot: bool
    events: object
    event_mapping: dict


def _run_montage_step(view, params):
    view.model.set_montage(**params)


def _run_bads_step(view, params):
    view.model.set_channel_properties(**params)


def _run_rename_step(view, params):
    view.model.rename_channels(**params)


def _run_interpolate_bads_step(view, params):
    view.model.interpolate_bads()


def _run_reference_step(view, params):
    view.model.change_reference(**params)


def _run_remove_line_noise_step(view, params):
    view.model.remove_line_noise(**params)


def _run_filter_step(view, params):
    view.model.filter(**params)


def _run_resample_step(view, params):
    view.model.resample(**params)


def _run_crop_step(view, params):
    view.model.crop(**params)


def _run_events_from_annotations_step(view, params):
    view.model.events_from_annotations()


def _run_epoch_data_step(view, params):
    view.model.epoch_data(**params)


def _run_drop_bad_epochs_step(view, params):
    view.model.drop_bad_epochs(**params)


def _run_run_ica_step(view, params):
    view._fit_ica(**params)


def _reject_fields_to_dict(fields):
    """Turn a mapping of channel type to `QLineEdit` into a threshold dict."""
    result = {}
    for channel_type_name, field_widget in fields.items():
        if field_widget.text():
            result[channel_type_name] = float(field_widget.text())
    return result


class _PipelineStageWidget(QWidget):
    """One stage of a preprocessing pipeline: an Available/Steps two-list editor.

    A stage starts from a `StageContext` describing the state produced by every
    earlier stage (or the model's actual current state, for the first stage), and
    offers/records steps against that state rather than the model's original one.
    """

    def __init__(self, parent_dialog, context):
        super().__init__(parent_dialog)
        self._parent_dialog = parent_dialog
        self._context = context
        self.steps: list[PipelineStep] = []

        hbox = QHBoxLayout(self)

        available_vbox = QVBoxLayout()
        available_vbox.addWidget(QLabel("Available Steps"))
        self.available_list = QListWidget()
        for kind, spec in STEP_REGISTRY.items():
            item = QListWidgetItem(spec.label)
            item.setData(Qt.ItemDataRole.UserRole, kind)
            if not spec.available(self):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.available_list.addItem(item)
        self.available_list.itemDoubleClicked.connect(self._add_selected_step)
        available_vbox.addWidget(self.available_list)
        self.add_button = QPushButton("Add Step →")
        self.add_button.clicked.connect(self._add_selected_step)
        available_vbox.addWidget(self.add_button)
        hbox.addLayout(available_vbox)

        steps_vbox = QVBoxLayout()
        steps_vbox.addWidget(QLabel("Stage Steps"))
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

    def set_context(self, context):
        """Update the state this stage starts from (an earlier stage changed)."""
        self._context = context
        self._refresh_available_list()

    def ending_context(self):
        """Return the state produced once this stage's queued steps have run."""
        montage = self._context.montage
        sfreq = self._context.sfreq
        for step in self.steps:
            if step.kind == "montage":
                montage = step.params.get("montage")
            elif step.kind == "resample":
                sfreq = step.params["sfreq"]
        info = self._effective_info()
        return StageContext(
            data=self._context.data,
            info=info,
            dtype=self._effective_dtype(),
            sfreq=sfreq,
            nchan=info["nchan"],
            highpass=self._effective_highpass(),
            montage=montage,
            times=self._context.times,
            annot=self._context.annot,
            events=self._effective_events(),
            event_mapping=self._context.event_mapping,
        )

    # -- effective state (reflects steps already queued, not yet applied) ----------

    def _effective_info(self):
        """Return channel info as it will be once queued steps have run."""
        info = self._context.info.copy()
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
        highpass = self._context.highpass
        for step in self.steps:
            if step.kind == "filter":
                lower = step.params.get("lower")
                if lower is not None:
                    highpass = max(highpass, lower)
        return highpass

    def _effective_dtype(self):
        """Return the data type ("raw" or "epochs") as it will be once queued steps
        have run."""
        if any(step.kind == "epoch_data" for step in self.steps):
            return "epochs"
        return self._context.dtype

    def _effective_events(self):
        """Return the events array as it will be once queued steps have run."""
        events = self._context.events
        if (events is None or not len(events)) and any(
            step.kind == "events_from_annotations" for step in self.steps
        ):
            try:
                events, _ = mne.events_from_annotations(self._context.data)
            except ValueError:
                # e.g. every annotation is a "bad"/"edge" marker MNE excludes by
                # default, so there would be no events to convert
                events = None
        return events

    def _effective_has_events(self):
        """Return whether events will be available once queued steps have run."""
        events = self._effective_events()
        return events is not None and len(events) > 0

    def _effective_event_types(self):
        """Return the event type labels available once queued steps have run."""
        events = self._effective_events()
        if events is not None and len(events):
            return np.unique(events[:, 2]).astype(str).tolist()
        return []

    def _effective_channel_types(self):
        """Return the channel types present once queued steps have run."""
        info = self._effective_info()
        return sorted({channel_type(info, i) for i in range(info["nchan"])})

    def _effective_has_locations(self):
        """Return whether channel positions will be set once queued steps have run."""
        for step in reversed(self.steps):
            if step.kind == "montage":
                return step.params.get("montage") is not None
        return bool(count_locations(self._context.info) > 0)

    # -- availability ---------------------------------------------------------------

    def _available_montage(self):
        return True

    def _available_bads(self):
        return True

    def _available_interpolate_bads(self):
        return self._effective_has_locations() and bool(self._effective_info()["bads"])

    def _available_rename(self):
        return True

    def _available_reference(self):
        return True

    def _available_remove_line_noise(self):
        return self._effective_dtype() == "raw"

    def _available_filter(self):
        return True

    def _available_resample(self):
        return self._effective_dtype() in ("raw", "epochs")

    def _available_crop(self):
        return self._effective_dtype() == "raw"

    def _available_events_from_annotations(self):
        return self._effective_dtype() == "raw" and self._context.annot

    def _available_epoch_data(self):
        return self._effective_dtype() == "raw" and self._effective_has_events()

    def _available_drop_bad_epochs(self):
        return self._effective_dtype() == "epochs" and self._effective_has_events()

    def _available_run_ica(self):
        return True

    def _refresh_available_list(self):
        """Re-evaluate which available steps are enabled given the queued steps."""
        for i in range(self.available_list.count()):
            item = self.available_list.item(i)
            kind = item.data(Qt.ItemDataRole.UserRole)
            flags = item.flags()
            if STEP_REGISTRY[kind].available(self):
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)

    # -- adding steps -------------------------------------------------------------

    def _add_selected_step(self):
        item = self.available_list.currentItem()
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        kind = item.data(Qt.ItemDataRole.UserRole)
        STEP_REGISTRY[kind].add(self)

    def _add_montage_step(self):
        montages = natural_sort(mne.channels.get_builtin_montages())
        dialog = MontageDialog(self, montages, current_montage=self._context.montage)
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

    def _add_interpolate_bads_step(self):
        self._append_step(
            PipelineStep("interpolate_bads", "Interpolate Bad Channels", {})
        )

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

    def _add_reference_step(self):
        dialog = ReferenceDialog(self, self._effective_ch_names())
        if not dialog.exec():
            return
        if dialog.add_group.isChecked():
            add = [c.strip() for c in dialog.add_channellist.text().split(",")]
        else:
            add = []
        if dialog.reref_group.isChecked():
            if dialog.reref_average.isChecked():
                ref = "average"
            else:
                ref = [c.text() for c in dialog.reref_channellist.selectedItems()]
        else:
            ref = None
        parts = []
        if add:
            parts.append(f"add {', '.join(add)}")
        if ref == "average":
            parts.append("average")
        elif ref:
            parts.append(", ".join(ref))
        label = f"Change Reference: {'; '.join(parts) if parts else 'none'}"
        self._append_step(PipelineStep("reference", label, {"add": add, "ref": ref}))

    def _add_remove_line_noise_step(self):
        dialog = RemoveLineNoiseDialog(self, self._context.sfreq)
        if not dialog.exec():
            return
        params = {
            "line_freq": dialog.line_frequency,
            "include_harmonics": dialog.include_harmonics.isChecked(),
        }
        label = f"Remove Line Noise: {dialog.line_frequency:g} Hz"
        self._append_step(PipelineStep("remove_line_noise", label, params))

    def _add_filter_step(self):
        dialog = FilterDialog(self)
        if not dialog.exec():
            return
        params = {"lower": dialog.lower, "upper": dialog.upper, "notch": dialog.notch}
        parts = []
        if dialog.lower is not None and dialog.upper is not None:
            parts.append(f"{dialog.lower:g}-{dialog.upper:g} Hz")
        elif dialog.lower is not None:
            parts.append(f">{dialog.lower:g} Hz")
        elif dialog.upper is not None:
            parts.append(f"<{dialog.upper:g} Hz")
        if dialog.notch is not None:
            parts.append(f"notch {dialog.notch:g} Hz")
        label = f"Filter Data: {', '.join(parts)}"
        self._append_step(PipelineStep("filter", label, params))

    def _add_resample_step(self):
        dialog = ResampleDialog(self, self._context.sfreq)
        if not dialog.exec():
            return
        label = f"Resample Data: {dialog.new_sfreq:g} Hz"
        self._append_step(PipelineStep("resample", label, {"sfreq": dialog.new_sfreq}))

    def _add_crop_step(self):
        stop = self._context.times[-1]
        dialog = CropDialog(
            self,
            0,
            stop,
            events=self._context.events,
            event_mapping=self._context.event_mapping,
            sfreq=self._context.sfreq,
        )
        if not dialog.exec():
            return
        start = max(dialog.start, 0) if dialog.start is not None else 0
        end = min(dialog.stop, stop) if dialog.stop is not None else stop
        label = f"Crop Data: {start:g}-{end:g} s"
        self._append_step(PipelineStep("crop", label, {"start": start, "stop": end}))

    def _add_events_from_annotations_step(self):
        self._append_step(
            PipelineStep("events_from_annotations", "Events from Annotations", {})
        )

    def _add_epoch_data_step(self):
        event_types = self._effective_event_types()
        dialog = EpochDialog(self, event_types)
        if not dialog.exec():
            return
        tmin = dialog.tmin.value()
        tmax = dialog.tmax.value()
        if dialog.baseline.isChecked():
            baseline = (dialog.a.value(), dialog.b.value())
        else:
            baseline = None
        params = {
            "event_id": dialog.selected_events,
            "tmin": tmin,
            "tmax": tmax,
            "baseline": baseline,
        }
        label = f"Create Epochs: {len(dialog.selected_events)} event type(s)"
        self._append_step(PipelineStep("epoch_data", label, params))

    def _add_drop_bad_epochs_step(self):
        types = self._effective_channel_types()
        dialog = DropBadEpochsDialog(self, types)
        if not dialog.exec():
            return
        reject = None
        flat = None
        if dialog.reject_box.isChecked():
            reject = _reject_fields_to_dict(dialog.reject_fields)
        if dialog.flat_box.isChecked():
            flat = _reject_fields_to_dict(dialog.flat_fields)
        if reject is None and flat is None:
            return
        parts = []
        if reject:
            parts.append("reject")
        if flat:
            parts.append("flat")
        label = f"Drop Bad Epochs: {', '.join(parts) if parts else 'none'}"
        self._append_step(
            PipelineStep("drop_bad_epochs", label, {"reject": reject, "flat": flat})
        )

    def _add_run_ica_step(self):
        methods = ["Infomax"]
        if have["python-picard"]:
            methods.insert(0, "Picard")
        if have["scikit-learn"]:
            methods.append("FastICA")
        dialog = RunICADialog(
            self, self._context.nchan, self._effective_highpass(), methods
        )
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

    # -- list management --------------------------------------------------------

    def _append_step(self, step):
        self.steps.append(step)
        self.steps_list.addItem(QListWidgetItem(step.label))
        self._refresh_available_list()
        self._parent_dialog._on_stage_changed(self)

    def _move_step_up(self):
        row = self.steps_list.currentRow()
        if row <= 0:
            return
        self.steps[row - 1], self.steps[row] = self.steps[row], self.steps[row - 1]
        self._refresh_steps_list(selected_row=row - 1)
        self._parent_dialog._on_stage_changed(self)

    def _move_step_down(self):
        row = self.steps_list.currentRow()
        if row < 0 or row >= len(self.steps) - 1:
            return
        self.steps[row + 1], self.steps[row] = self.steps[row], self.steps[row + 1]
        self._refresh_steps_list(selected_row=row + 1)
        self._parent_dialog._on_stage_changed(self)

    def _remove_step(self):
        row = self.steps_list.currentRow()
        if row < 0:
            return
        del self.steps[row]
        self._refresh_steps_list()
        self._refresh_available_list()
        self._parent_dialog._on_stage_changed(self)

    def _refresh_steps_list(self, selected_row=None):
        self.steps_list.clear()
        for step in self.steps:
            self.steps_list.addItem(QListWidgetItem(step.label))
        if selected_row is not None and 0 <= selected_row < self.steps_list.count():
            self.steps_list.setCurrentRow(selected_row)


class PipelineDialog(QDialog):
    """Build an ordered, possibly multi-stage sequence of preprocessing steps to run
    in one go.

    Each stage is its own Available/Steps editor. A stage's Available Steps reflect
    the state produced by every earlier stage -- most importantly, once a stage
    queues a Create Epochs step, every later stage starts from an epochs data type
    instead of raw, which changes which steps are offered.
    """

    def __init__(self, parent, model):
        super().__init__(parent)
        self.setWindowTitle("Preprocessing Pipeline")
        self.resize(640, 460)

        data = model.current["data"]
        dtype = model.current["dtype"]
        self._initial_context = StageContext(
            data=data,
            info=data.info,
            dtype=dtype,
            sfreq=data.info["sfreq"],
            nchan=data.info["nchan"],
            highpass=data.info["highpass"],
            montage=model.current["montage"],
            times=data.times if dtype == "raw" else None,
            annot=bool(data.annotations) if dtype == "raw" else False,
            events=model.current["events"],
            event_mapping=model.current["event_mapping"],
        )

        self.stages: list[_PipelineStageWidget] = []

        vbox = QVBoxLayout(self)
        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        stage_controls = QHBoxLayout()
        self.add_stage_button = QPushButton("+ Add Stage")
        self.add_stage_button.setToolTip(
            "Add a stage for steps that must run after this stage's, e.g. once raw"
            " data has been turned into epochs"
        )
        self.add_stage_button.clicked.connect(self._add_stage)
        self.remove_stage_button = QPushButton("Remove Stage")
        self.remove_stage_button.clicked.connect(self._remove_stage)
        stage_controls.addWidget(self.add_stage_button)
        stage_controls.addWidget(self.remove_stage_button)
        stage_controls.addStretch()
        vbox.addLayout(stage_controls)

        self.buttonbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.run_button = self.buttonbox.button(QDialogButtonBox.StandardButton.Ok)
        self.run_button.setText("Run")
        self.run_button.setEnabled(False)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        vbox.addWidget(self.buttonbox)

        self._add_stage()
        self.setFocus()

    @property
    def steps(self):
        """Every queued step across all stages, in order. Read-only: stages are the
        source of truth, this is a flattened view for the executor."""
        return [step for stage in self.stages for step in stage.steps]

    def _add_stage(self):
        context = (
            self.stages[-1].ending_context() if self.stages else self._initial_context
        )
        stage = _PipelineStageWidget(self, context)
        self.stages.append(stage)
        index = self.tabs.addTab(stage, f"Stage {len(self.stages)}")
        self.tabs.setCurrentIndex(index)
        self.remove_stage_button.setEnabled(len(self.stages) > 1)
        self.run_button.setEnabled(bool(self.steps))

    def _remove_stage(self):
        if len(self.stages) <= 1:
            return
        index = self.tabs.currentIndex()
        self.tabs.removeTab(index)
        del self.stages[index]
        for i in range(self.tabs.count()):
            self.tabs.setTabText(i, f"Stage {i + 1}")
        self.remove_stage_button.setEnabled(len(self.stages) > 1)
        self._resync_contexts_from(index)
        self.run_button.setEnabled(bool(self.steps))

    def _on_stage_changed(self, stage):
        """Called by a stage widget whenever its queued steps change."""
        self._resync_contexts_from(self.stages.index(stage))
        self.run_button.setEnabled(bool(self.steps))

    def _resync_contexts_from(self, index):
        """Recompute the starting context of stage `index` and every later stage."""
        context = (
            self.stages[index - 1].ending_context()
            if index > 0
            else self._initial_context
        )
        for stage in self.stages[index:]:
            stage.set_context(context)
            context = stage.ending_context()


STEP_REGISTRY: dict[str, StepSpec] = {
    "montage": StepSpec(
        "Apply Montage...",
        _PipelineStageWidget._available_montage,
        _PipelineStageWidget._add_montage_step,
        _run_montage_step,
    ),
    "bads": StepSpec(
        "Mark Bad Channels...",
        _PipelineStageWidget._available_bads,
        _PipelineStageWidget._add_bads_step,
        _run_bads_step,
    ),
    "interpolate_bads": StepSpec(
        "Interpolate Bad Channels",
        _PipelineStageWidget._available_interpolate_bads,
        _PipelineStageWidget._add_interpolate_bads_step,
        _run_interpolate_bads_step,
    ),
    "rename": StepSpec(
        "Rename Channels...",
        _PipelineStageWidget._available_rename,
        _PipelineStageWidget._add_rename_step,
        _run_rename_step,
    ),
    "reference": StepSpec(
        "Change Reference...",
        _PipelineStageWidget._available_reference,
        _PipelineStageWidget._add_reference_step,
        _run_reference_step,
    ),
    "remove_line_noise": StepSpec(
        "Remove Line Noise...",
        _PipelineStageWidget._available_remove_line_noise,
        _PipelineStageWidget._add_remove_line_noise_step,
        _run_remove_line_noise_step,
    ),
    "filter": StepSpec(
        "Filter Data...",
        _PipelineStageWidget._available_filter,
        _PipelineStageWidget._add_filter_step,
        _run_filter_step,
    ),
    "resample": StepSpec(
        "Resample Data...",
        _PipelineStageWidget._available_resample,
        _PipelineStageWidget._add_resample_step,
        _run_resample_step,
    ),
    "crop": StepSpec(
        "Crop Data...",
        _PipelineStageWidget._available_crop,
        _PipelineStageWidget._add_crop_step,
        _run_crop_step,
    ),
    "events_from_annotations": StepSpec(
        "Events from Annotations",
        _PipelineStageWidget._available_events_from_annotations,
        _PipelineStageWidget._add_events_from_annotations_step,
        _run_events_from_annotations_step,
    ),
    "epoch_data": StepSpec(
        "Create Epochs...",
        _PipelineStageWidget._available_epoch_data,
        _PipelineStageWidget._add_epoch_data_step,
        _run_epoch_data_step,
    ),
    "drop_bad_epochs": StepSpec(
        "Drop Bad Epochs...",
        _PipelineStageWidget._available_drop_bad_epochs,
        _PipelineStageWidget._add_drop_bad_epochs_step,
        _run_drop_bad_epochs_step,
    ),
    "run_ica": StepSpec(
        "Run ICA...",
        _PipelineStageWidget._available_run_ica,
        _PipelineStageWidget._add_run_ica_step,
        _run_run_ica_step,
    ),
}
