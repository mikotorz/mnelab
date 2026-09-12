# © MNELAB developers
#
# License: BSD (3-clause)

from types import SimpleNamespace

import mne
import numpy as np
import pytest
from edfio import Edf, EdfSignal
from PySide6.QtCore import Qt

from mnelab.dialogs.crop import CropDialog
from mnelab.dialogs.drop_bad_epochs import DropBadEpochsDialog
from mnelab.dialogs.filter import FilterDialog
from mnelab.dialogs.montage import MontageDialog
from mnelab.dialogs.pipeline import PipelineDialog, PipelineStep
from mnelab.dialogs.reference import ReferenceDialog
from mnelab.dialogs.remove_line_noise import RemoveLineNoiseDialog
from mnelab.dialogs.rename_channels import RenameChannelsDialog
from mnelab.dialogs.resample import ResampleDialog
from mnelab.mainwindow import MainWindow
from mnelab.model import Model


def _load_edf_model(tmp_path, name="sample.edf", duration=30, fs=256, label="EEG"):
    """Load a single-channel EDF file of the given duration into a fresh Model."""
    signal = np.zeros(duration * fs)
    path = tmp_path / name
    Edf([EdfSignal(signal, sampling_frequency=fs, label=label)]).write(path)
    model = Model()
    model.load(path)
    return model


@pytest.fixture
def model_with_data(tmp_path):
    """Model with a single 30-second, one-channel EDF file loaded."""
    return _load_edf_model(tmp_path)


@pytest.fixture
def model_with_annotated_data(tmp_path):
    """Model with a single annotation on the loaded raw data.

    The description is deliberately not "bad"/"edge"-prefixed: MNE's
    `events_from_annotations` excludes those by default, so a description like
    that would never turn into a real event.
    """
    model = _load_edf_model(tmp_path, name="annotated.edf")
    model.current["data"].set_annotations(
        mne.Annotations(onset=[1.0], duration=[0.5], description=["stimulus"])
    )
    return model


@pytest.fixture
def model_with_cz(tmp_path):
    """Model with a single 5-second EDF file with one channel named Cz."""
    fs = 100
    signal = np.zeros(5 * fs)
    path = tmp_path / "cz.edf"
    Edf([EdfSignal(signal, sampling_frequency=fs, label="Cz")]).write(path)
    model = Model()
    model.load(path)
    return model


@pytest.fixture
def model_with_eeg_cz(tmp_path):
    """Model with a single 5-second EDF file with one channel named 'EEG Cz'."""
    fs = 100
    signal = np.zeros(5 * fs)
    path = tmp_path / "eeg_cz.edf"
    Edf([EdfSignal(signal, sampling_frequency=fs, label="EEG Cz")]).write(path)
    model = Model()
    model.load(path)
    return model


def _step_availability(stage):
    """Map each available-step kind to whether it is currently enabled."""
    available = {}
    for i in range(stage.available_list.count()):
        item = stage.available_list.item(i)
        kind = item.data(Qt.ItemDataRole.UserRole)
        available[kind] = bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)
    return available


def test_step_availability_gating(qtbot, model_with_data, model_with_annotated_data):
    """Crop/events-from-annotations are only offered when applicable."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    available = _step_availability(dialog.stages[0])
    assert available["crop"] is True
    assert available["resample"] is True
    assert available["events_from_annotations"] is False

    annotated_dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(annotated_dialog)
    assert (
        _step_availability(annotated_dialog.stages[0])["events_from_annotations"]
        is True
    )


def test_step_list_management(qtbot, model_with_data):
    """Steps can be appended, reordered, and removed."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    assert not dialog.run_button.isEnabled()

    stage._append_step(PipelineStep("filter", "Filter Data: <30 Hz", {}))
    stage._append_step(PipelineStep("crop", "Crop Data: 0-10 s", {}))
    assert [s.kind for s in dialog.steps] == ["filter", "crop"]
    assert dialog.run_button.isEnabled()

    stage.steps_list.setCurrentRow(1)
    stage._move_step_up()
    assert [s.kind for s in dialog.steps] == ["crop", "filter"]
    assert [stage.steps_list.item(i).text() for i in range(2)] == [
        "Crop Data: 0-10 s",
        "Filter Data: <30 Hz",
    ]

    stage.steps_list.setCurrentRow(0)
    stage._move_step_down()
    assert [s.kind for s in dialog.steps] == ["filter", "crop"]

    stage.steps_list.setCurrentRow(0)
    stage._remove_step()
    assert [s.kind for s in dialog.steps] == ["crop"]

    stage.steps_list.setCurrentRow(0)
    stage._remove_step()
    assert dialog.steps == []
    assert not dialog.run_button.isEnabled()


def test_add_rename_step(qtbot, model_with_data, monkeypatch):
    """Adding a rename step records the selected renaming function."""

    def fake_exec(self):
        self.method.setCurrentText("Delete characters")
        self.begin_slice_num.setValue(1)
        self.update_preview()
        return True

    monkeypatch.setattr(RenameChannelsDialog, "exec", fake_exec)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_rename_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "rename"
    assert step.params["history_mapping"] == "lambda name: name[1:len(name) - 0]"
    assert step.params["mapping"]("EEG") == "EG"


def test_add_rename_step_noop_not_added(qtbot, model_with_data, monkeypatch):
    """A rename step that would not change any channel name is not added."""
    monkeypatch.setattr(RenameChannelsDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_rename_step()

    assert dialog.steps == []


def test_add_filter_step(qtbot, model_with_data, monkeypatch):
    """Adding a filter step records the dialog's configured parameters."""
    monkeypatch.setattr(FilterDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_filter_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "filter"
    assert step.params == {"lower": None, "upper": 30.0, "notch": None}


def test_add_resample_step(qtbot, model_with_data, monkeypatch):
    """Adding a resample step records the dialog's target sampling frequency."""
    monkeypatch.setattr(ResampleDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_resample_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "resample"
    assert step.params["sfreq"] == pytest.approx(128.0)


def test_add_crop_step(qtbot, model_with_data, monkeypatch):
    """Adding a crop step records the dialog's start/stop times."""
    monkeypatch.setattr(CropDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stop = dialog.stages[0]._context.times[-1]

    dialog.stages[0]._add_crop_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "crop"
    assert step.params == {"start": 0.0, "stop": pytest.approx(stop)}


def test_add_events_from_annotations_step(qtbot, model_with_annotated_data):
    """Adding an events-from-annotations step requires no configuration."""
    dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_events_from_annotations_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "events_from_annotations"
    assert step.params == {}


def test_add_montage_step_success(qtbot, model_with_cz, monkeypatch):
    """A montage step is added when at least one channel name matches."""

    def fake_exec(self):
        for i in range(self.montages.count()):
            if self.montages.item(i).name == "standard_1020":
                self.montages.setCurrentRow(i)
                break
        self.accept()
        return True

    monkeypatch.setattr(MontageDialog, "exec", fake_exec)
    dialog = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_montage_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "montage"
    assert step.params["montage"].name == "standard_1020"


def test_add_montage_step_no_match(qtbot, model_with_data, monkeypatch):
    """A montage step is rejected when no channel name matches."""

    def fake_exec(self):
        for i in range(self.montages.count()):
            if self.montages.item(i).name == "standard_1020":
                self.montages.setCurrentRow(i)
                break
        self.accept()
        return True

    monkeypatch.setattr(MontageDialog, "exec", fake_exec)
    critical_calls = []
    monkeypatch.setattr(
        "mnelab.dialogs.pipeline.QMessageBox.critical",
        lambda *args, **kwargs: critical_calls.append(args),
    )
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_montage_step()

    assert dialog.steps == []
    assert len(critical_calls) == 1


def test_add_montage_step_after_rename_step(qtbot, model_with_eeg_cz, monkeypatch):
    """A queued rename step is taken into account when validating a montage step."""

    def fake_rename_exec(self):
        self.method.setCurrentText("Delete characters")
        self.begin_slice_num.setValue(4)  # strips the "EEG " prefix, leaving "Cz"
        self.update_preview()
        return True

    def fake_montage_exec(self):
        for i in range(self.montages.count()):
            if self.montages.item(i).name == "standard_1020":
                self.montages.setCurrentRow(i)
                break
        self.accept()
        return True

    monkeypatch.setattr(RenameChannelsDialog, "exec", fake_rename_exec)
    monkeypatch.setattr(MontageDialog, "exec", fake_montage_exec)
    dialog = PipelineDialog(None, model_with_eeg_cz)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    stage._add_rename_step()
    assert [s.kind for s in dialog.steps] == ["rename"]

    # without taking the queued rename step into account, "EEG Cz" would not
    # match any standard_1020 channel name and this would be wrongly rejected
    stage._add_montage_step()

    assert [s.kind for s in dialog.steps] == ["rename", "montage"]
    assert dialog.steps[-1].params["montage"].name == "standard_1020"


def test_add_bads_step_after_rename_step(qtbot, model_with_data, monkeypatch):
    """A queued rename step is reflected in a subsequently configured bads step."""

    def fake_rename_exec(self):
        self.method.setCurrentText("Delete characters")
        self.begin_slice_num.setValue(1)
        self.update_preview()
        return True

    monkeypatch.setattr(RenameChannelsDialog, "exec", fake_rename_exec)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    stage._add_rename_step()
    assert dialog.steps[-1].params["mapping"]("EEG") == "EG"

    seen_labels = []

    def fake_bads_exec(self):
        seen_labels.append(self.model.item(0, 1).data(Qt.ItemDataRole.DisplayRole))
        return False

    monkeypatch.setattr(
        "mnelab.dialogs.pipeline.ChannelPropertiesDialog.exec", fake_bads_exec
    )
    stage._add_bads_step()

    assert seen_labels == ["EG"]


def test_run_ica_step_uses_effective_highpass(qtbot, model_with_data, monkeypatch):
    """A queued filter step's cutoff is reflected in the Run ICA dialog's hint."""

    def fake_filter_exec(self):
        self.upper_check.setChecked(False)
        self.lower_check.setChecked(True)
        self.lower_edit.setValue(2.0)
        return True

    monkeypatch.setattr(FilterDialog, "exec", fake_filter_exec)

    recorded = {}

    class FakeRunICADialog:
        def __init__(self, parent, nchan, highpass, methods):
            recorded["highpass"] = highpass

        def exec(self):
            return False

    monkeypatch.setattr("mnelab.dialogs.pipeline.RunICADialog", FakeRunICADialog)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]
    assert stage._effective_highpass() == 0

    stage._add_filter_step()
    stage._add_run_ica_step()

    assert recorded["highpass"] == pytest.approx(2.0)


def test_run_pipeline_applies_steps_to_single_duplicated_dataset(
    qtbot, model_with_data, monkeypatch
):
    """Running a pipeline duplicates once and applies all steps in order."""
    view = MainWindow(model_with_data)
    model_with_data.view = view
    qtbot.addWidget(view)

    filter_params = {"lower": None, "upper": 30.0, "notch": None}
    steps = [
        PipelineStep("filter", "Filter Data: <30 Hz", filter_params),
        PipelineStep("crop", "Crop Data: 0-10 s", {"start": 0.0, "stop": 10.0}),
    ]

    class FakePipelineDialog:
        def __init__(self, parent, model):
            self.steps = steps

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.mainwindow.PipelineDialog", FakePipelineDialog)

    n_before = len(model_with_data.data)
    view.run_pipeline()

    assert len(model_with_data.data) == n_before + 1
    data = model_with_data.current["data"]
    assert data.times[-1] == pytest.approx(10.0, abs=0.05)
    assert "data.filter(None, 30.0)" in model_with_data.history
    assert "data.crop(0.0, 10.0)" in model_with_data.history


def test_run_pipeline_rename_step(qtbot, model_with_data, monkeypatch):
    """A rename pipeline step renames channels via Model.rename_channels."""
    view = MainWindow(model_with_data)
    model_with_data.view = view
    qtbot.addWidget(view)

    steps = [
        PipelineStep(
            "rename",
            "Rename Channels: lambda name: name[1:]",
            {
                "mapping": lambda name: name[1:],
                "history_mapping": "lambda name: name[1:]",
            },
        )
    ]

    class FakePipelineDialog:
        def __init__(self, parent, model):
            self.steps = steps

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.mainwindow.PipelineDialog", FakePipelineDialog)

    view.run_pipeline()

    assert model_with_data.current["data"].info["ch_names"] == ["EG"]
    assert (
        "mne.rename_channels(data.info, lambda name: name[1:])"
        in model_with_data.history
    )


def test_run_pipeline_stops_after_failing_step(qtbot, model_with_data, monkeypatch):
    """A failing step stops the remaining ones but keeps earlier steps applied."""
    view = MainWindow(model_with_data)
    model_with_data.view = view
    qtbot.addWidget(view)

    steps = [
        PipelineStep("crop", "Crop Data: 0-10 s", {"start": 0.0, "stop": 10.0}),
        PipelineStep("crop", "Crop Data: bad", {"start": 100.0, "stop": 200.0}),
        PipelineStep("resample", "Resample Data: 64 Hz", {"sfreq": 64.0}),
    ]

    class FakePipelineDialog:
        def __init__(self, parent, model):
            self.steps = steps

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.mainwindow.PipelineDialog", FakePipelineDialog)
    critical_calls = []
    monkeypatch.setattr(
        "mnelab.mainwindow.QMessageBox.critical",
        lambda *args, **kwargs: critical_calls.append(args),
    )

    view.run_pipeline()

    assert len(critical_calls) == 1
    data = model_with_data.current["data"]
    # the first crop step was applied, the invalid second crop stopped the pipeline
    assert data.times[-1] == pytest.approx(10.0, abs=0.05)
    assert data.info["sfreq"] == pytest.approx(256.0)


def test_add_interpolate_bads_step(qtbot, model_with_data):
    """Adding an interpolate-bads step requires no configuration."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_interpolate_bads_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "interpolate_bads"
    assert step.params == {}


def test_interpolate_bads_availability(qtbot, model_with_cz, monkeypatch):
    """Interpolate Bad Channels becomes available once locations and bad channels
    are queued, even though the original dataset has neither."""

    def fake_montage_exec(self):
        for i in range(self.montages.count()):
            if self.montages.item(i).name == "standard_1020":
                self.montages.setCurrentRow(i)
                break
        self.accept()
        return True

    monkeypatch.setattr(MontageDialog, "exec", fake_montage_exec)
    dialog = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    assert stage._available_interpolate_bads() is False
    assert _step_availability(stage)["interpolate_bads"] is False

    stage._add_montage_step()
    assert stage._available_interpolate_bads() is False  # no bad channels queued yet

    stage._append_step(
        PipelineStep(
            "bads", "Mark Bad Channels: Cz", {"bads": ["Cz"], "names": {}, "types": {}}
        )
    )

    assert stage._available_interpolate_bads() is True
    assert _step_availability(stage)["interpolate_bads"] is True


def test_add_reference_step(qtbot, model_with_data, monkeypatch):
    """Adding a Change Reference step records the dialog's configured choice."""

    def fake_exec(self):
        self.reref_group.setChecked(True)
        self.reref_average.setChecked(True)
        return True

    monkeypatch.setattr(ReferenceDialog, "exec", fake_exec)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_reference_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "reference"
    assert step.params == {"add": [], "ref": "average"}


def test_add_remove_line_noise_step(qtbot, model_with_data, monkeypatch):
    """Adding a Remove Line Noise step records the dialog's configured parameters."""

    def fake_exec(self):
        self._line_frequency.setValue(60.0)
        self.include_harmonics.setChecked(False)
        return True

    monkeypatch.setattr(RemoveLineNoiseDialog, "exec", fake_exec)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_remove_line_noise_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "remove_line_noise"
    assert step.params == {"line_freq": 60.0, "include_harmonics": False}


def test_remove_line_noise_unavailable_after_epoch_data_queued(qtbot, model_with_data):
    """Remove Line Noise is raw-only, so it is gated off once epoching is queued."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    assert stage._available_remove_line_noise() is True

    stage._append_step(PipelineStep("epoch_data", "Create Epochs: 1 event type(s)", {}))

    assert stage._available_remove_line_noise() is False
    assert _step_availability(stage)["remove_line_noise"] is False


def test_add_epoch_data_step(qtbot, model_with_annotated_data, monkeypatch):
    """Adding a Create Epochs step records the dialog's configured parameters."""

    class FakeEpochDialog:
        def __init__(self, parent, event_types):
            self.tmin = SimpleNamespace(value=lambda: -0.2)
            self.tmax = SimpleNamespace(value=lambda: 0.2)
            self.baseline = SimpleNamespace(isChecked=lambda: False)
            self.selected_events = [1]

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.dialogs.pipeline.EpochDialog", FakeEpochDialog)
    dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(dialog)

    dialog.stages[0]._add_epoch_data_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "epoch_data"
    assert step.params == {
        "event_id": [1],
        "tmin": -0.2,
        "tmax": 0.2,
        "baseline": None,
    }


def test_epoch_data_availability_and_dtype_flip(qtbot, model_with_annotated_data):
    """Create Epochs becomes available once events-from-annotations is queued, and
    queuing Create Epochs itself flips availability of later, dtype-sensitive steps."""
    dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    assert stage._available_epoch_data() is False  # no events yet

    stage._append_step(
        PipelineStep("events_from_annotations", "Events from Annotations", {})
    )
    assert stage._available_epoch_data() is True

    stage._append_step(PipelineStep("epoch_data", "Create Epochs: 1 event type(s)", {}))

    assert stage._effective_dtype() == "epochs"
    assert stage._available_crop() is False
    assert stage._available_remove_line_noise() is False
    assert stage._available_events_from_annotations() is False
    assert stage._available_resample() is True
    assert stage._available_drop_bad_epochs() is True

    available = _step_availability(stage)
    assert available["crop"] is False
    assert available["drop_bad_epochs"] is True


def test_add_drop_bad_epochs_step(qtbot, model_with_data, monkeypatch):
    """Adding a Drop Bad Epochs step records the dialog's configured thresholds."""

    def fake_exec(self):
        self.reject_box.setChecked(True)
        next(iter(self.reject_fields.values())).setText("100e-6")
        return True

    monkeypatch.setattr(DropBadEpochsDialog, "exec", fake_exec)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stage = dialog.stages[0]

    stage._add_drop_bad_epochs_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "drop_bad_epochs"
    ch_type = stage._effective_channel_types()[0]
    assert step.params == {"reject": {ch_type: 100e-6}, "flat": None}


def test_run_pipeline_interpolate_bads_step_calls_model(
    qtbot, model_with_data, monkeypatch
):
    """The interpolate_bads pipeline step calls through to Model.interpolate_bads."""
    view = MainWindow(model_with_data)
    model_with_data.view = view
    qtbot.addWidget(view)

    calls = []
    monkeypatch.setattr(Model, "interpolate_bads", lambda self: calls.append(True))

    steps = [PipelineStep("interpolate_bads", "Interpolate Bad Channels", {})]

    class FakePipelineDialog:
        def __init__(self, parent, model):
            self.steps = steps

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.mainwindow.PipelineDialog", FakePipelineDialog)
    monkeypatch.setattr(
        "mnelab.mainwindow.QMessageBox.critical",
        lambda *args, **kwargs: pytest.fail("Pipeline step unexpectedly failed"),
    )

    view.run_pipeline()

    assert calls == [True]


def test_run_pipeline_reference_and_remove_line_noise_steps(
    qtbot, model_with_data, monkeypatch
):
    """Reference and line-noise pipeline steps call through to the Model."""
    view = MainWindow(model_with_data)
    model_with_data.view = view
    qtbot.addWidget(view)

    steps = [
        PipelineStep(
            "reference", "Change Reference: average", {"add": [], "ref": "average"}
        ),
        PipelineStep(
            "remove_line_noise",
            "Remove Line Noise: 50 Hz",
            {"line_freq": 50.0, "include_harmonics": True},
        ),
    ]

    class FakePipelineDialog:
        def __init__(self, parent, model):
            self.steps = steps

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.mainwindow.PipelineDialog", FakePipelineDialog)
    monkeypatch.setattr(
        "mnelab.mainwindow.QMessageBox.critical",
        lambda *args, **kwargs: pytest.fail("Pipeline step unexpectedly failed"),
    )

    view.run_pipeline()

    assert model_with_data.current["reference"] == "average"
    assert "remove_line_noise(data, 50.0, include_harmonics=True)" in (
        model_with_data.history
    )


def test_run_pipeline_epoch_and_drop_bad_epochs_steps(
    qtbot, model_with_annotated_data, monkeypatch
):
    """A pipeline chaining events-from-annotations, epoching, and epoch rejection in
    a single run ends up with an epochs dataset."""
    model = model_with_annotated_data
    view = MainWindow(model)
    model.view = view
    qtbot.addWidget(view)

    steps = [
        PipelineStep("events_from_annotations", "Events from Annotations", {}),
        PipelineStep(
            "epoch_data",
            "Create Epochs: 1 event type(s)",
            {"event_id": [1], "tmin": -0.2, "tmax": 0.2, "baseline": None},
        ),
        PipelineStep(
            "drop_bad_epochs",
            "Drop Bad Epochs: reject",
            {"reject": {"eeg": 1.0}, "flat": None},
        ),
    ]

    class FakePipelineDialog:
        def __init__(self, parent, model):
            self.steps = steps

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.mainwindow.PipelineDialog", FakePipelineDialog)
    monkeypatch.setattr(
        "mnelab.mainwindow.QMessageBox.critical",
        lambda *args, **kwargs: pytest.fail("Pipeline step unexpectedly failed"),
    )

    view.run_pipeline()

    assert model.current["dtype"] == "epochs"
    assert len(model.current["data"]) == 1


# -- multi-stage pipelines ------------------------------------------------------


def test_new_dialog_has_exactly_one_stage(qtbot, model_with_data):
    """A freshly opened Pipeline dialog starts with a single stage."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    assert len(dialog.stages) == 1
    assert dialog.tabs.count() == 1
    assert dialog.tabs.tabText(0) == "Stage 1"
    assert not dialog.remove_stage_button.isEnabled()


def test_add_and_remove_stage(qtbot, model_with_data):
    """Stages can be added and removed, but at least one must remain."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog._add_stage()

    assert len(dialog.stages) == 2
    assert dialog.tabs.count() == 2
    assert dialog.tabs.tabText(1) == "Stage 2"
    assert dialog.remove_stage_button.isEnabled()

    dialog.tabs.setCurrentIndex(1)
    dialog._remove_stage()

    assert len(dialog.stages) == 1
    assert dialog.tabs.count() == 1
    assert not dialog.remove_stage_button.isEnabled()

    # removing the last remaining stage is a no-op
    dialog._remove_stage()
    assert len(dialog.stages) == 1


def test_epoch_data_in_one_stage_gates_later_stage(
    qtbot, model_with_annotated_data, monkeypatch
):
    """Once a stage queues Create Epochs, that stage and every later one start
    seeing an epochs data type: Drop Bad Epochs becomes available, and raw-only
    steps are gated off -- in the stage that queued Create Epochs and beyond."""

    class FakeEpochDialog:
        def __init__(self, parent, event_types):
            self.tmin = SimpleNamespace(value=lambda: -0.2)
            self.tmax = SimpleNamespace(value=lambda: 0.2)
            self.baseline = SimpleNamespace(isChecked=lambda: False)
            self.selected_events = [1]

        def exec(self):
            return True

    monkeypatch.setattr("mnelab.dialogs.pipeline.EpochDialog", FakeEpochDialog)
    dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(dialog)
    stage1 = dialog.stages[0]

    stage1._append_step(
        PipelineStep("events_from_annotations", "Events from Annotations", {})
    )
    stage1._add_epoch_data_step()
    assert [s.kind for s in stage1.steps] == ["events_from_annotations", "epoch_data"]

    # stage 1 itself already offers Drop Bad Epochs, since Create Epochs was
    # queued within it
    assert stage1._available_drop_bad_epochs() is True

    dialog._add_stage()
    stage2 = dialog.stages[1]

    assert stage2._context.dtype == "epochs"
    assert stage2._available_drop_bad_epochs() is True
    assert stage2._available_crop() is False
    assert stage2._available_remove_line_noise() is False

    available2 = _step_availability(stage2)
    assert available2["drop_bad_epochs"] is True
    assert available2["crop"] is False


def test_stage_context_resyncs_when_earlier_stage_changes(
    qtbot, model_with_annotated_data
):
    """Removing an epoching step from an earlier stage un-gates Drop Bad Epochs in a
    later stage that was already built on top of it."""
    dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(dialog)
    stage1 = dialog.stages[0]

    stage1._append_step(
        PipelineStep("events_from_annotations", "Events from Annotations", {})
    )
    stage1._append_step(
        PipelineStep("epoch_data", "Create Epochs: 1 event type(s)", {})
    )

    dialog._add_stage()
    stage2 = dialog.stages[1]
    assert stage2._context.dtype == "epochs"
    assert stage2._available_drop_bad_epochs() is True

    # remove the epoching step from stage 1
    stage1.steps_list.setCurrentRow(1)
    stage1._remove_step()

    assert stage2._context.dtype == "raw"
    assert stage2._available_drop_bad_epochs() is False
    assert stage2._available_crop() is True


def test_dialog_steps_flattens_stages_in_order(qtbot, model_with_data):
    """`dialog.steps` is every stage's steps, concatenated in stage order."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stage1 = dialog.stages[0]

    stage1._append_step(PipelineStep("filter", "Filter Data: <30 Hz", {}))

    dialog._add_stage()
    stage2 = dialog.stages[1]
    stage2._append_step(
        PipelineStep("resample", "Resample Data: 128 Hz", {"sfreq": 128.0})
    )

    assert [s.kind for s in dialog.steps] == ["filter", "resample"]
