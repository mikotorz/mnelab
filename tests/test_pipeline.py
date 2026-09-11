# © MNELAB developers
#
# License: BSD (3-clause)

import mne
import numpy as np
import pytest
from edfio import Edf, EdfSignal
from PySide6.QtCore import Qt

from mnelab.dialogs.crop import CropDialog
from mnelab.dialogs.filter import FilterDialog
from mnelab.dialogs.montage import MontageDialog
from mnelab.dialogs.pipeline import PipelineDialog, PipelineStep
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
    """Model with a single annotation on the loaded raw data."""
    model = _load_edf_model(tmp_path, name="annotated.edf")
    model.current["data"].set_annotations(
        mne.Annotations(onset=[1.0], duration=[0.5], description=["BAD"])
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


def _step_availability(dialog):
    """Map each available-step kind to whether it is currently enabled."""
    available = {}
    for i in range(dialog.available_list.count()):
        item = dialog.available_list.item(i)
        kind = item.data(Qt.ItemDataRole.UserRole)
        available[kind] = bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)
    return available


def test_step_availability_gating(qtbot, model_with_data, model_with_annotated_data):
    """Crop/events-from-annotations are only offered when applicable."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    available = _step_availability(dialog)
    assert available["crop"] is True
    assert available["resample"] is True
    assert available["events_from_annotations"] is False

    annotated_dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(annotated_dialog)
    assert _step_availability(annotated_dialog)["events_from_annotations"] is True


def test_step_list_management(qtbot, model_with_data):
    """Steps can be appended, reordered, and removed."""
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    assert not dialog.run_button.isEnabled()

    dialog._append_step(PipelineStep("filter", "Filter Data: <30 Hz", {}))
    dialog._append_step(PipelineStep("crop", "Crop Data: 0-10 s", {}))
    assert [s.kind for s in dialog.steps] == ["filter", "crop"]
    assert dialog.run_button.isEnabled()

    dialog.steps_list.setCurrentRow(1)
    dialog._move_step_up()
    assert [s.kind for s in dialog.steps] == ["crop", "filter"]
    assert [dialog.steps_list.item(i).text() for i in range(2)] == [
        "Crop Data: 0-10 s",
        "Filter Data: <30 Hz",
    ]

    dialog.steps_list.setCurrentRow(0)
    dialog._move_step_down()
    assert [s.kind for s in dialog.steps] == ["filter", "crop"]

    dialog.steps_list.setCurrentRow(0)
    dialog._remove_step()
    assert [s.kind for s in dialog.steps] == ["crop"]

    dialog.steps_list.setCurrentRow(0)
    dialog._remove_step()
    assert dialog.steps == []
    assert not dialog.run_button.isEnabled()


def test_add_filter_step(qtbot, model_with_data, monkeypatch):
    """Adding a filter step records the dialog's configured parameters."""
    monkeypatch.setattr(FilterDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog._add_filter_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "filter"
    assert step.params == {"lower": None, "upper": 30.0, "notch": None}


def test_add_resample_step(qtbot, model_with_data, monkeypatch):
    """Adding a resample step records the dialog's target sampling frequency."""
    monkeypatch.setattr(ResampleDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)

    dialog._add_resample_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "resample"
    assert step.params["sfreq"] == pytest.approx(128.0)


def test_add_crop_step(qtbot, model_with_data, monkeypatch):
    """Adding a crop step records the dialog's start/stop times."""
    monkeypatch.setattr(CropDialog, "exec", lambda self: True)
    dialog = PipelineDialog(None, model_with_data)
    qtbot.addWidget(dialog)
    stop = dialog._times[-1]

    dialog._add_crop_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "crop"
    assert step.params == {"start": 0.0, "stop": pytest.approx(stop)}


def test_add_events_from_annotations_step(qtbot, model_with_annotated_data):
    """Adding an events-from-annotations step requires no configuration."""
    dialog = PipelineDialog(None, model_with_annotated_data)
    qtbot.addWidget(dialog)

    dialog._add_events_from_annotations_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "events_from_annotations"
    assert step.params == {}


def test_add_montage_step_success(qtbot, model_with_cz, monkeypatch):
    """A montage step is added when at least one channel name matches."""

    def fake_exec(self):
        for i in range(self.montages.count()):
            if self.montages.item(i).name == "spherical_1020":
                self.montages.setCurrentRow(i)
                break
        self.accept()
        return True

    monkeypatch.setattr(MontageDialog, "exec", fake_exec)
    dialog = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(dialog)

    dialog._add_montage_step()

    assert len(dialog.steps) == 1
    step = dialog.steps[0]
    assert step.kind == "montage"
    assert step.params["montage"].name == "spherical_1020"


def test_add_montage_step_no_match(qtbot, model_with_data, monkeypatch):
    """A montage step is rejected when no channel name matches."""

    def fake_exec(self):
        for i in range(self.montages.count()):
            if self.montages.item(i).name == "spherical_1020":
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

    dialog._add_montage_step()

    assert dialog.steps == []
    assert len(critical_calls) == 1


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
