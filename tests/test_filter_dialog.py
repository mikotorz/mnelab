# © MNELAB developers
#
# License: BSD (3-clause)

import pytest
from PySide6.QtWidgets import QInputDialog

from mnelab import presets
from mnelab.dialogs.filter import FilterDialog


@pytest.fixture(autouse=True)
def temp_presets(tmp_path, monkeypatch):
    """Redirect presets to a temporary file for tests."""
    monkeypatch.setattr(presets, "PRESETS_PATH", str(tmp_path / "mnelab_presets.json"))


def test_initial_values_match_hardcoded_defaults(qtbot):
    dialog = FilterDialog()
    qtbot.addWidget(dialog)

    assert dialog.get_preset_values() == {
        "lower_enabled": False,
        "lower": 1.0,
        "upper_enabled": True,
        "upper": 30.0,
        "notch_enabled": False,
        "notch": 50.0,
    }


def test_set_preset_values_round_trips(qtbot):
    dialog = FilterDialog()
    qtbot.addWidget(dialog)

    values = {
        "lower_enabled": True,
        "lower": 2.5,
        "upper_enabled": False,
        "upper": 40.0,
        "notch_enabled": True,
        "notch": 60.0,
    }
    dialog.set_preset_values(values)

    assert dialog.get_preset_values() == values


def test_restore_defaults_resets_fields(qtbot):
    dialog = FilterDialog()
    qtbot.addWidget(dialog)
    dialog.set_preset_values(
        {
            "lower_enabled": True,
            "lower": 2.5,
            "upper_enabled": False,
            "upper": 40.0,
            "notch_enabled": True,
            "notch": 60.0,
        }
    )

    dialog.preset_bar.restore_button.click()

    assert dialog.get_preset_values() == {
        "lower_enabled": False,
        "lower": 1.0,
        "upper_enabled": True,
        "upper": 30.0,
        "notch_enabled": False,
        "notch": 50.0,
    }


def test_save_and_reselect_preset_via_bar(qtbot, monkeypatch):
    dialog = FilterDialog()
    qtbot.addWidget(dialog)
    dialog.set_preset_values(
        {
            "lower_enabled": True,
            "lower": 3.0,
            "upper_enabled": True,
            "upper": 45.0,
            "notch_enabled": False,
            "notch": 50.0,
        }
    )
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("My Preset", True))
    dialog.preset_bar.save_button.click()

    dialog.set_preset_values(
        {
            "lower_enabled": False,
            "lower": 1.0,
            "upper_enabled": True,
            "upper": 30.0,
            "notch_enabled": False,
            "notch": 50.0,
        }
    )

    index = dialog.preset_bar.combo.findText("My Preset")
    dialog.preset_bar.combo.setCurrentIndex(index)
    dialog.preset_bar.combo.activated.emit(index)

    assert dialog.get_preset_values() == {
        "lower_enabled": True,
        "lower": 3.0,
        "upper_enabled": True,
        "upper": 45.0,
        "notch_enabled": False,
        "notch": 50.0,
    }
