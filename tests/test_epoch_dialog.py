# © MNELAB developers
#
# License: BSD (3-clause)

import pytest
from PySide6.QtWidgets import QInputDialog

from mnelab import presets
from mnelab.dialogs.epoch import EpochDialog

EVENT_TYPES = ["1", "2"]


@pytest.fixture(autouse=True)
def temp_presets(tmp_path, monkeypatch):
    """Redirect presets to a temporary file for tests."""
    monkeypatch.setattr(presets, "PRESETS_PATH", str(tmp_path / "mnelab_presets.json"))


def test_initial_values_match_hardcoded_defaults(qtbot):
    dialog = EpochDialog(None, EVENT_TYPES)
    qtbot.addWidget(dialog)

    assert dialog.get_preset_values() == {
        "tmin": -0.2,
        "tmax": 0.5,
        "baseline_enabled": True,
        "baseline_start": -0.2,
        "baseline_end": 0.0,
    }


def test_set_preset_values_round_trips(qtbot):
    dialog = EpochDialog(None, EVENT_TYPES)
    qtbot.addWidget(dialog)

    values = {
        "tmin": -1.0,
        "tmax": 2.0,
        "baseline_enabled": False,
        "baseline_start": -0.5,
        "baseline_end": 0.1,
    }
    dialog.set_preset_values(values)

    assert dialog.get_preset_values() == values
    assert not dialog.a.isEnabled()
    assert not dialog.b.isEnabled()


def test_restore_defaults_resets_fields(qtbot):
    dialog = EpochDialog(None, EVENT_TYPES)
    qtbot.addWidget(dialog)
    dialog.set_preset_values(
        {
            "tmin": -1.0,
            "tmax": 2.0,
            "baseline_enabled": False,
            "baseline_start": -0.5,
            "baseline_end": 0.1,
        }
    )

    dialog.preset_bar.restore_button.click()

    assert dialog.get_preset_values() == {
        "tmin": -0.2,
        "tmax": 0.5,
        "baseline_enabled": True,
        "baseline_start": -0.2,
        "baseline_end": 0.0,
    }
    assert dialog.a.isEnabled()
    assert dialog.b.isEnabled()


def test_save_and_reselect_preset_via_bar(qtbot, monkeypatch):
    dialog = EpochDialog(None, EVENT_TYPES)
    qtbot.addWidget(dialog)
    dialog.set_preset_values(
        {
            "tmin": -1.0,
            "tmax": 2.0,
            "baseline_enabled": False,
            "baseline_start": -0.5,
            "baseline_end": 0.1,
        }
    )
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("My Preset", True))
    dialog.preset_bar.save_button.click()

    dialog.preset_bar.restore_button.click()

    index = dialog.preset_bar.combo.findText("My Preset")
    dialog.preset_bar.combo.setCurrentIndex(index)
    dialog.preset_bar.combo.activated.emit(index)

    assert dialog.get_preset_values() == {
        "tmin": -1.0,
        "tmax": 2.0,
        "baseline_enabled": False,
        "baseline_start": -0.5,
        "baseline_end": 0.1,
    }
