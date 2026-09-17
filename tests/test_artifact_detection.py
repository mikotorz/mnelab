# © MNELAB developers
#
# License: BSD (3-clause)

import mne
import numpy as np
import pytest
from PySide6.QtWidgets import QInputDialog

from mnelab import presets
from mnelab.dialogs.artifact_detection import ArtifactDetectionDialog
from mnelab.utils.artifact_detection import (
    find_bad_epochs_amplitude,
    find_bad_epochs_kurtosis,
    find_bad_epochs_ptp,
)


@pytest.fixture(autouse=True)
def temp_presets(tmp_path, monkeypatch):
    """Redirect presets to a temporary file for tests."""
    monkeypatch.setattr(presets, "PRESETS_PATH", str(tmp_path / "mnelab_presets.json"))


@pytest.fixture
def clean_epochs():
    """Create clean EpochsArray for testing."""
    rng = np.random.default_rng(42)
    n_epochs = 30
    n_channels = 3
    n_times = 100
    sfreq = 100
    data = rng.standard_normal((n_epochs, n_channels, n_times)) * 1e-6
    info = mne.create_info(
        ch_names=[f"Ch{i}" for i in range(n_channels)], sfreq=sfreq, ch_types="eeg"
    )
    return mne.EpochsArray(data, info)


@pytest.mark.parametrize(
    "detection_func,threshold",
    [
        (find_bad_epochs_amplitude, 100e-6),
        (find_bad_epochs_ptp, 100e-6),
        (find_bad_epochs_kurtosis, 5.0),
    ],
)
def test_no_artifacts_detected(clean_epochs, detection_func, threshold):
    """Test that clean data with high thresholds produces no bad epochs."""
    bad_epochs = detection_func(clean_epochs, threshold=threshold)

    assert bad_epochs.shape == (30,)
    assert bad_epochs.dtype == bool
    assert not bad_epochs.any()


def test_find_bad_epochs_amplitude(clean_epochs):
    """Test amplitude-based artifact detection."""
    epochs_data = clean_epochs.get_data()
    bad_idx = [2, 8, 14]
    epochs_data[bad_idx, 0, 50] = 150e-6
    epochs = mne.EpochsArray(epochs_data, clean_epochs.info)

    bad_epochs = find_bad_epochs_amplitude(epochs, threshold=100e-6)
    np.testing.assert_array_equal(np.where(bad_epochs)[0], bad_idx)


def test_find_bad_epochs_ptp(clean_epochs):
    """Test peak-to-peak amplitude artifact detection."""
    epochs_data = clean_epochs.get_data()
    bad_idx = [3, 12, 21]
    epochs_data[bad_idx, 1, :50] = 100e-6
    epochs_data[bad_idx, 1, 50:] = -100e-6
    epochs = mne.EpochsArray(epochs_data, clean_epochs.info)

    bad_epochs = find_bad_epochs_ptp(epochs, threshold=150e-6)
    np.testing.assert_array_equal(np.where(bad_epochs)[0], bad_idx)


def test_find_bad_epochs_kurtosis(clean_epochs):
    """Test kurtosis-based artifact detection."""
    epochs_data = clean_epochs.get_data()
    bad_idx = [5, 15]

    for epoch_idx in bad_idx:
        for ch in range(epochs_data.shape[1]):
            epochs_data[epoch_idx, ch, [10, 30, 50, 70, 90]] = 100e-6

    epochs = mne.EpochsArray(epochs_data, clean_epochs.info)

    bad_epochs = find_bad_epochs_kurtosis(epochs, threshold=3.0)
    np.testing.assert_array_equal(np.where(bad_epochs)[0], bad_idx)


def test_initial_preset_values_match_hardcoded_defaults(qtbot, clean_epochs):
    dialog = ArtifactDetectionDialog(None, clean_epochs)
    qtbot.addWidget(dialog)

    expected = {
        method: {"enabled": False, **{p[0]: p[2] for p in details["parameters"]}}
        for method, details in dialog.detection_methods.items()
    }
    assert dialog.get_preset_values() == expected


def test_set_preset_values_round_trips(qtbot, clean_epochs):
    dialog = ArtifactDetectionDialog(None, clean_epochs)
    qtbot.addWidget(dialog)

    values = {
        "Extreme Values": {"enabled": True, "threshold": 200.0},
        "Peak-to-Peak": {"enabled": True, "threshold": 300.0},
        "Kurtosis": {"enabled": False, "threshold": 8.0},
    }
    if "AutoReject" in dialog.detection_methods:
        values["AutoReject"] = {"enabled": False}
    dialog.set_preset_values(values)

    assert dialog.get_preset_values() == values


def test_set_preset_values_skips_unavailable_method(qtbot, clean_epochs):
    dialog = ArtifactDetectionDialog(None, clean_epochs)
    qtbot.addWidget(dialog)

    # applying a preset that references a method not currently available (e.g. saved
    # while AutoReject was installed) must not raise
    dialog.set_preset_values({"Not A Real Method": {"enabled": True, "threshold": 1.0}})


def test_restore_defaults_resets_fields(qtbot, clean_epochs):
    dialog = ArtifactDetectionDialog(None, clean_epochs)
    qtbot.addWidget(dialog)
    dialog.set_preset_values(
        {
            "Extreme Values": {"enabled": True, "threshold": 200.0},
            "Peak-to-Peak": {"enabled": True, "threshold": 300.0},
            "Kurtosis": {"enabled": False, "threshold": 8.0},
        }
    )

    dialog.preset_bar.restore_button.click()

    expected = {
        method: {"enabled": False, **{p[0]: p[2] for p in details["parameters"]}}
        for method, details in dialog.detection_methods.items()
    }
    assert dialog.get_preset_values() == expected


def test_save_and_reselect_preset_via_bar(qtbot, clean_epochs, monkeypatch):
    dialog = ArtifactDetectionDialog(None, clean_epochs)
    qtbot.addWidget(dialog)
    values = {
        "Extreme Values": {"enabled": True, "threshold": 200.0},
        "Peak-to-Peak": {"enabled": True, "threshold": 300.0},
        "Kurtosis": {"enabled": False, "threshold": 8.0},
    }
    if "AutoReject" in dialog.detection_methods:
        values["AutoReject"] = {"enabled": False}
    dialog.set_preset_values(values)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("My Preset", True))
    dialog.preset_bar.save_button.click()

    dialog.preset_bar.restore_button.click()

    index = dialog.preset_bar.combo.findText("My Preset")
    dialog.preset_bar.combo.setCurrentIndex(index)
    dialog.preset_bar.combo.activated.emit(index)

    assert dialog.get_preset_values() == values
