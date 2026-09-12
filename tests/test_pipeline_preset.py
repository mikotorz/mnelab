# © MNELAB developers
#
# License: BSD (3-clause)

import json

import numpy as np
import pytest
from edfio import Edf, EdfSignal
from mne.channels import make_standard_montage

from mnelab.dialogs.pipeline import (
    PipelineDialog,
    PipelinePresetFormatError,
    PipelineStep,
)
from mnelab.model import Model
from mnelab.pipeline_preset import (
    PRESET_FORMAT_VERSION,
    load_pipeline_preset,
    save_pipeline_preset,
)
from mnelab.utils import Montage


def _load_edf_model(tmp_path, name="sample.edf", duration=30, fs=256, label="Cz"):
    """Load a single-channel EDF file of the given duration into a fresh Model."""
    signal = np.zeros(duration * fs)
    path = tmp_path / name
    Edf([EdfSignal(signal, sampling_frequency=fs, label=label)]).write(path)
    model = Model()
    model.load(path)
    return model


@pytest.fixture
def model_with_cz(tmp_path):
    """Model with a single 30-second, one-channel EDF file with a channel Cz."""
    return _load_edf_model(tmp_path)


def test_round_trip_preset_preserves_stages_and_steps(qtbot, model_with_cz, tmp_path):
    """Saving and reloading a multi-stage preset preserves every step's kind and
    params, including montage and rename steps whose params hold live objects."""
    dialog = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(dialog)
    stage1 = dialog.stages[0]

    montage = Montage(make_standard_montage("standard_1020"), "standard_1020")
    stage1._append_step(
        PipelineStep(
            "montage",
            "Apply Montage: standard_1020",
            {
                "montage": montage,
                "match_case": False,
                "match_alias": False,
                "on_missing": "ignore",
            },
        )
    )
    stage1._append_step(
        PipelineStep(
            "rename",
            "Rename Channels: lambda name: name[1:]",
            {
                "mapping": lambda name: name[1:],
                "history_mapping": "lambda name: name[1:]",
                "method": "Delete characters",
                "begin_strip_chars": "",
                "end_strip_chars": "",
                "begin_slice_num": 1,
                "end_slice_num": 0,
            },
        )
    )
    filter_params = {"lower": None, "upper": 30.0, "notch": None}
    stage1._append_step(PipelineStep("filter", "Filter Data: <30 Hz", filter_params))

    dialog._add_stage()
    stage2 = dialog.stages[1]
    stage2._append_step(
        PipelineStep("resample", "Resample Data: 128 Hz", {"sfreq": 128.0})
    )

    stages_data = [
        (dialog.tabs.tabText(i), stage.steps) for i, stage in enumerate(dialog.stages)
    ]
    fname = tmp_path / "preset.json"
    save_pipeline_preset(stages_data, fname)

    loaded_stages, skipped = load_pipeline_preset(fname)

    assert skipped == []
    assert [name for name, _ in loaded_stages] == ["Stage 1", "Stage 2"]
    kinds = [[s.kind for s in steps] for _, steps in loaded_stages]
    assert kinds == [["montage", "rename", "filter"], ["resample"]]

    loaded_montage_step = loaded_stages[0][1][0]
    assert loaded_montage_step.params["montage"].name == "standard_1020"
    assert loaded_montage_step.params["montage"].embedded is False
    assert loaded_montage_step.params["on_missing"] == "ignore"

    loaded_rename_step = loaded_stages[0][1][1]
    assert loaded_rename_step.params["mapping"]("EEG") == "EG"
    assert (
        loaded_rename_step.params["history_mapping"]
        == "lambda name: name[1:len(name) - 0]"
    )

    loaded_filter_step = loaded_stages[0][1][2]
    assert loaded_filter_step.params == {"lower": None, "upper": 30.0, "notch": None}

    loaded_resample_step = loaded_stages[1][1][0]
    assert loaded_resample_step.params == {"sfreq": 128.0}


def test_load_preset_rejects_unsupported_format_version(tmp_path):
    """A preset file from an incompatible future/past format is rejected clearly."""
    fname = tmp_path / "preset.json"
    fname.write_text(json.dumps({"format_version": 999, "stages": []}))

    with pytest.raises(PipelinePresetFormatError, match="format version"):
        load_pipeline_preset(fname)


def test_load_preset_rejects_invalid_json(tmp_path):
    """A file that isn't valid JSON at all is rejected with a clear error."""
    fname = tmp_path / "preset.json"
    fname.write_text("not valid json{")

    with pytest.raises(PipelinePresetFormatError, match="not a valid"):
        load_pipeline_preset(fname)


def test_save_preset_rejects_embedded_montage(tmp_path):
    """A montage embedded in a specific recording's own digitization cannot be
    generically reconstructed on future data, so saving it is rejected clearly."""
    montage = Montage(
        make_standard_montage("standard_1020"), "standard_1020", None, True
    )
    stages_data = [
        (
            "Stage 1",
            [
                PipelineStep(
                    "montage",
                    "Apply Montage: standard_1020",
                    {
                        "montage": montage,
                        "match_case": False,
                        "match_alias": False,
                        "on_missing": "ignore",
                    },
                )
            ],
        )
    ]

    with pytest.raises(PipelinePresetFormatError, match="embedded"):
        save_pipeline_preset(stages_data, tmp_path / "preset.json")


def test_load_preset_skips_step_with_missing_custom_montage_file(tmp_path):
    """A custom montage step whose file no longer exists is skipped and reported,
    rather than failing the entire preset load."""
    fname = tmp_path / "preset.json"
    fname.write_text(
        json.dumps(
            {
                "format_version": PRESET_FORMAT_VERSION,
                "stages": [
                    {
                        "name": "Stage 1",
                        "steps": [
                            {
                                "kind": "montage",
                                "label": "Apply Montage: custom.sfp",
                                "params": {
                                    "montage": {
                                        "name": "custom.sfp",
                                        "path": str(tmp_path / "missing.sfp"),
                                    },
                                    "match_case": False,
                                    "match_alias": False,
                                    "on_missing": "ignore",
                                },
                            },
                            {
                                "kind": "filter",
                                "label": "Filter Data: <30 Hz",
                                "params": {
                                    "lower": None,
                                    "upper": 30.0,
                                    "notch": None,
                                },
                            },
                        ],
                    }
                ],
            }
        )
    )

    stages, skipped = load_pipeline_preset(fname)

    assert [name for name, _ in stages] == ["Stage 1"]
    assert [s.kind for s in stages[0][1]] == ["filter"]
    assert len(skipped) == 1
    assert "no longer exists" in skipped[0]


def test_dialog_load_preset_skips_unavailable_step_and_reports(
    qtbot, model_with_cz, tmp_path, monkeypatch
):
    """Loading a preset onto data it doesn't apply to (here: no annotations) skips
    the inapplicable step and shows a summary instead of crashing or silently
    dropping it."""
    fname = tmp_path / "preset.json"
    fname.write_text(
        json.dumps(
            {
                "format_version": PRESET_FORMAT_VERSION,
                "stages": [
                    {
                        "name": "Stage 1",
                        "steps": [
                            {
                                "kind": "events_from_annotations",
                                "label": "Events from Annotations",
                                "params": {},
                            },
                            {
                                "kind": "filter",
                                "label": "Filter Data: <30 Hz",
                                "params": {
                                    "lower": None,
                                    "upper": 30.0,
                                    "notch": None,
                                },
                            },
                        ],
                    }
                ],
            }
        )
    )

    dialog = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(dialog)

    monkeypatch.setattr(
        "mnelab.dialogs.pipeline.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(fname), ""),
    )
    warnings = []
    monkeypatch.setattr(
        "mnelab.dialogs.pipeline.QMessageBox.warning",
        lambda parent, title, text: warnings.append(text),
    )

    dialog._load_preset()

    assert [s.kind for s in dialog.steps] == ["filter"]
    assert len(warnings) == 1
    assert "Events from Annotations" in warnings[0]


def test_dialog_save_and_load_preset_round_trip(
    qtbot, model_with_cz, tmp_path, monkeypatch
):
    """The dialog's Save/Load Preset buttons round-trip a real multi-stage pipeline
    built through the same append/add-stage calls a user's clicks would trigger."""
    dialog = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(dialog)
    filter_params = {"lower": None, "upper": 30.0, "notch": None}
    dialog.stages[0]._append_step(
        PipelineStep("filter", "Filter Data: <30 Hz", filter_params)
    )
    dialog._add_stage()
    dialog.stages[1]._append_step(
        PipelineStep("resample", "Resample Data: 128 Hz", {"sfreq": 128.0})
    )

    fname = tmp_path / "preset.json"
    monkeypatch.setattr(
        "mnelab.dialogs.pipeline.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(fname), ""),
    )
    dialog._save_preset()
    assert fname.exists()

    reloaded = PipelineDialog(None, model_with_cz)
    qtbot.addWidget(reloaded)
    monkeypatch.setattr(
        "mnelab.dialogs.pipeline.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(fname), ""),
    )
    reloaded._load_preset()

    assert [s.kind for s in reloaded.steps] == ["filter", "resample"]
    assert len(reloaded.stages) == 2
    assert reloaded.tabs.tabText(0) == "Stage 1"
    assert reloaded.tabs.tabText(1) == "Stage 2"
