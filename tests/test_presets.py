# © MNELAB developers
#
# License: BSD (3-clause)

import pytest

from mnelab import presets
from mnelab.presets import delete_preset, list_presets, load_preset, save_preset


@pytest.fixture(autouse=True)
def temp_presets(tmp_path, monkeypatch):
    """Redirect presets to a temporary file for tests."""
    monkeypatch.setattr(presets, "PRESETS_PATH", str(tmp_path / "mnelab_presets.json"))


def test_list_presets_empty_when_missing():
    assert list_presets("filter") == []


def test_save_load_round_trip():
    values = {"lower_enabled": True, "lower": 2.0}
    save_preset("filter", "My Preset", values)
    assert load_preset("filter", "My Preset") == values
    assert list_presets("filter") == ["My Preset"]


def test_save_overwrites_existing_preset():
    save_preset("filter", "My Preset", {"lower": 1.0})
    save_preset("filter", "My Preset", {"lower": 2.0})
    assert load_preset("filter", "My Preset") == {"lower": 2.0}
    assert list_presets("filter") == ["My Preset"]


def test_list_presets_sorted():
    save_preset("filter", "Zebra", {})
    save_preset("filter", "Alpha", {})
    assert list_presets("filter") == ["Alpha", "Zebra"]


def test_categories_are_independent():
    save_preset("filter", "Shared Name", {"lower": 1.0})
    save_preset("epoch", "Shared Name", {"tmin": -0.2})
    assert load_preset("filter", "Shared Name") == {"lower": 1.0}
    assert load_preset("epoch", "Shared Name") == {"tmin": -0.2}
    assert list_presets("filter") == ["Shared Name"]
    assert list_presets("epoch") == ["Shared Name"]


def test_load_missing_preset_raises_keyerror():
    with pytest.raises(KeyError):
        load_preset("filter", "Does Not Exist")


def test_load_missing_category_raises_keyerror():
    with pytest.raises(KeyError):
        load_preset("does_not_exist", "Anything")


def test_delete_preset_removes_it():
    save_preset("filter", "My Preset", {"lower": 1.0})
    delete_preset("filter", "My Preset")
    assert list_presets("filter") == []


def test_delete_missing_preset_is_noop():
    delete_preset("filter", "Does Not Exist")
    assert list_presets("filter") == []


def test_corrupt_store_treated_as_empty(tmp_path, monkeypatch):
    path = tmp_path / "corrupt.json"
    path.write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(presets, "PRESETS_PATH", str(path))
    assert list_presets("filter") == []
