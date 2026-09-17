# © MNELAB developers
#
# License: BSD (3-clause)

import pytest
from PySide6.QtWidgets import QInputDialog

from mnelab import presets
from mnelab.dialogs.iclabel import AutoSelectDialog

LABELS = ["Brain", "Muscle", "Eye", "Heart"]


@pytest.fixture(autouse=True)
def temp_presets(tmp_path, monkeypatch):
    """Redirect presets to a temporary file for tests."""
    monkeypatch.setattr(presets, "PRESETS_PATH", str(tmp_path / "mnelab_presets.json"))


def test_initial_values_match_hardcoded_defaults(qtbot):
    dialog = AutoSelectDialog(None, LABELS)
    qtbot.addWidget(dialog)

    assert dialog.get_preset_values() == {
        "Brain": {"enabled": False, "threshold": 0.90},
        "Muscle": {"enabled": True, "threshold": 0.90},
        "Eye": {"enabled": True, "threshold": 0.90},
        "Heart": {"enabled": False, "threshold": 0.90},
    }


def test_set_preset_values_round_trips(qtbot):
    dialog = AutoSelectDialog(None, LABELS)
    qtbot.addWidget(dialog)

    values = {
        "Brain": {"enabled": True, "threshold": 0.75},
        "Muscle": {"enabled": False, "threshold": 0.50},
        "Eye": {"enabled": False, "threshold": 0.60},
        "Heart": {"enabled": True, "threshold": 0.95},
    }
    dialog.set_preset_values(values)

    assert dialog.get_preset_values() == values


def test_set_preset_values_skips_unknown_labels(qtbot):
    dialog = AutoSelectDialog(None, LABELS)
    qtbot.addWidget(dialog)

    dialog.set_preset_values({"NotALabel": {"enabled": True, "threshold": 0.5}})

    assert dialog.get_preset_values() == {
        "Brain": {"enabled": False, "threshold": 0.90},
        "Muscle": {"enabled": True, "threshold": 0.90},
        "Eye": {"enabled": True, "threshold": 0.90},
        "Heart": {"enabled": False, "threshold": 0.90},
    }


def test_restore_defaults_resets_fields(qtbot):
    dialog = AutoSelectDialog(None, LABELS)
    qtbot.addWidget(dialog)
    dialog.set_preset_values(
        {
            "Brain": {"enabled": True, "threshold": 0.75},
            "Muscle": {"enabled": False, "threshold": 0.50},
            "Eye": {"enabled": False, "threshold": 0.60},
            "Heart": {"enabled": True, "threshold": 0.95},
        }
    )

    dialog.preset_bar.restore_button.click()

    assert dialog.get_preset_values() == {
        "Brain": {"enabled": False, "threshold": 0.90},
        "Muscle": {"enabled": True, "threshold": 0.90},
        "Eye": {"enabled": True, "threshold": 0.90},
        "Heart": {"enabled": False, "threshold": 0.90},
    }


def test_save_and_reselect_preset_via_bar(qtbot, monkeypatch):
    dialog = AutoSelectDialog(None, LABELS)
    qtbot.addWidget(dialog)
    values = {
        "Brain": {"enabled": True, "threshold": 0.75},
        "Muscle": {"enabled": False, "threshold": 0.50},
        "Eye": {"enabled": False, "threshold": 0.60},
        "Heart": {"enabled": True, "threshold": 0.95},
    }
    dialog.set_preset_values(values)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("My Preset", True))
    dialog.preset_bar.save_button.click()

    dialog.preset_bar.restore_button.click()

    index = dialog.preset_bar.combo.findText("My Preset")
    dialog.preset_bar.combo.setCurrentIndex(index)
    dialog.preset_bar.combo.activated.emit(index)

    assert dialog.get_preset_values() == values
