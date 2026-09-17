# © MNELAB developers
#
# License: BSD (3-clause)

import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox

from mnelab import presets
from mnelab.widgets import PresetBar


@pytest.fixture(autouse=True)
def temp_presets(tmp_path, monkeypatch):
    """Redirect presets to a temporary file for tests."""
    monkeypatch.setattr(presets, "PRESETS_PATH", str(tmp_path / "mnelab_presets.json"))


DEFAULTS = {"value": 0}


def _make_bar(qtbot):
    """Create a `PresetBar` backed by a simple mutable dict "dialog state"."""
    state = {"value": 1}

    def get_values():
        return dict(state)

    def set_values(values):
        state.clear()
        state.update(values)

    bar = PresetBar(None, "test_category", get_values, set_values, DEFAULTS)
    qtbot.addWidget(bar)
    return bar, state


def test_save_creates_and_selects_preset(qtbot, monkeypatch):
    bar, state = _make_bar(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Preset A", True))

    bar.save_button.click()

    assert presets.list_presets("test_category") == ["Preset A"]
    assert presets.load_preset("test_category", "Preset A") == state
    assert bar.combo.currentText() == "Preset A"


def test_selecting_preset_applies_values(qtbot):
    presets.save_preset("test_category", "Preset A", {"value": 5})
    bar, state = _make_bar(qtbot)

    index = bar.combo.findText("Preset A")
    bar.combo.setCurrentIndex(index)
    bar.combo.activated.emit(index)

    assert state == {"value": 5}


def test_delete_removes_preset_and_clears_selection(qtbot, monkeypatch):
    presets.save_preset("test_category", "Preset A", {"value": 5})
    bar, _ = _make_bar(qtbot)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    bar.combo.setCurrentIndex(bar.combo.findText("Preset A"))
    bar.delete_button.click()

    assert presets.list_presets("test_category") == []
    assert bar.combo.currentText() == ""
    assert not bar.delete_button.isEnabled()


def test_restore_defaults_applies_defaults_without_touching_storage(qtbot):
    presets.save_preset("test_category", "Preset A", {"value": 5})
    bar, state = _make_bar(qtbot)

    bar.restore_button.click()

    assert state == DEFAULTS
    assert bar.combo.currentText() == ""
    assert presets.list_presets("test_category") == ["Preset A"]
