# © MNELAB developers
#
# License: BSD (3-clause)

import numpy as np
import pytest

from mnelab.dialogs.crop import CropDialog

SFREQ = 100.0
# event id 1 at t=1.0/5.0 s, event id 2 at t=2.0/8.0 s (samples = seconds * SFREQ)
EVENTS = np.array(
    [
        [100, 0, 1],
        [200, 0, 2],
        [500, 0, 1],
        [800, 0, 2],
    ]
)
MAX_STOP = 10.0


def test_event_radio_disabled_without_events(qtbot):
    """The event-range mode is unavailable when there are no events."""
    dialog = CropDialog(None, 0, MAX_STOP)
    qtbot.addWidget(dialog)

    assert not dialog.event_radio.isEnabled()


def test_event_combo_uses_mapping_labels(qtbot):
    """Combo entries use the event mapping label when available."""
    dialog = CropDialog(
        None, 0, MAX_STOP, events=EVENTS, event_mapping={1: "stim"}, sfreq=SFREQ
    )
    qtbot.addWidget(dialog)

    items = [dialog.event_combo.itemText(i) for i in range(dialog.event_combo.count())]
    assert items == ["All Events", "stim (1)", "Event 2"]


def test_event_range_specific_event(qtbot):
    """Selecting an event type crops to its first/last occurrence plus padding."""
    dialog = CropDialog(None, 0, MAX_STOP, events=EVENTS, sfreq=SFREQ)
    qtbot.addWidget(dialog)

    dialog.event_radio.setChecked(True)
    index = dialog.event_combo.findData(1)
    dialog.event_combo.setCurrentIndex(index)
    dialog.before_spin.setValue(0.1)
    dialog.after_spin.setValue(0.5)

    assert dialog.start == pytest.approx(0.9)
    assert dialog.stop == pytest.approx(5.5)


def test_event_range_all_events(qtbot):
    """'All Events' uses the min/max occurrence across every event type."""
    dialog = CropDialog(None, 0, MAX_STOP, events=EVENTS, sfreq=SFREQ)
    qtbot.addWidget(dialog)

    dialog.event_radio.setChecked(True)
    dialog.before_spin.setValue(0.1)
    dialog.after_spin.setValue(0.5)

    assert dialog.start == pytest.approx(0.9)
    assert dialog.stop == pytest.approx(8.5)


def test_event_range_clamped_to_bounds(qtbot):
    """Padding cannot push the crop range outside [0, max_stop]."""
    dialog = CropDialog(None, 0, MAX_STOP, events=EVENTS, sfreq=SFREQ)
    qtbot.addWidget(dialog)

    dialog.event_radio.setChecked(True)
    index = dialog.event_combo.findData(2)
    dialog.event_combo.setCurrentIndex(index)
    dialog.before_spin.setValue(5.0)
    dialog.after_spin.setValue(5.0)

    assert dialog.start == 0.0
    assert dialog.stop == MAX_STOP


def test_manual_mode_unchanged(qtbot):
    """Manual mode still returns None for an unchecked bound."""
    dialog = CropDialog(None, 0, MAX_STOP, events=EVENTS, sfreq=SFREQ)
    qtbot.addWidget(dialog)

    dialog.stop_checkbox.setChecked(False)

    assert dialog.start == 0.0
    assert dialog.stop is None
