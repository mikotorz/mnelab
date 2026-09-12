# © MNELAB developers
#
# License: BSD (3-clause)

import zipfile

import mne
import numpy as np
import pytest
import zstandard as zstd
from mne.preprocessing import ICA
from PySide6.QtWidgets import QMessageBox

from mnelab import project
from mnelab.mainwindow import MainWindow
from mnelab.model import Model
from mnelab.project import ProjectFormatError
from mnelab.utils import Montage

CH_NAMES = ["Fp1", "Fp2", "Fz", "Cz", "Pz", "Oz", "F7", "F8"]
SFREQ = 100.0


def _make_raw(duration_sec=5.0, seed=0):
    rng = np.random.default_rng(seed)
    n_times = int(duration_sec * SFREQ)
    data = rng.standard_normal((len(CH_NAMES), n_times)) * 1e-6
    info = mne.create_info(CH_NAMES, SFREQ, ch_types="eeg")
    return mne.io.RawArray(data, info, verbose=False)


def _make_raw_fif(tmp_path, name, duration_sec=5.0, seed=0):
    """Create a small synthetic raw fif file and return its path."""
    raw = _make_raw(duration_sec=duration_sec, seed=seed)
    path = tmp_path / f"{name}_raw.fif"
    raw.save(path, overwrite=True, verbose=False)
    return path


@pytest.fixture
def model_with_data(tmp_path):
    """A `Model` with one loaded dataset (montage/events/reference set)."""
    model = Model()
    path = _make_raw_fif(tmp_path, "sample")
    model.load(path)

    montage = mne.channels.make_standard_montage("standard_1020")
    model.set_montage(Montage(montage, "standard_1020"))

    model.current["events"] = np.array([[10, 0, 1], [50, 0, 2]])
    model.current["event_mapping"][1] = "stimulus"
    model.current["event_mapping"][2] = "response"
    model.current["data"].events = model.current["events"]
    model.current["reference"] = "average"

    return model


def test_round_trip_replace(tmp_path, model_with_data):
    """Saving and loading a project preserves data, metadata, and history."""
    model = model_with_data
    proj_path = tmp_path / "project.mnelabproj"
    model.save_project(proj_path)

    assert model.project_path == str(proj_path)
    assert model.dirty is False

    original_data = model.current["data"].get_data()
    original_history = list(model.history)
    # compare against the montage as attached to the data (post `set_montage`
    # coordinate-frame alignment), not the pristine standalone montage object,
    # since `set_montage` can transform positions into the head coordinate frame
    original_montage_positions = model.current["data"].get_montage().get_positions()

    loaded_model = Model()
    loaded_model.load_project(proj_path)

    assert len(loaded_model.data) == len(model.data)
    assert loaded_model.index == model.index
    assert loaded_model.project_path == str(proj_path)
    assert loaded_model.dirty is False

    loaded = loaded_model.current
    np.testing.assert_allclose(loaded["data"].get_data(), original_data, atol=1e-9)
    assert loaded["id"] == model.current["id"]
    assert loaded["parent_id"] == model.current["parent_id"]
    assert loaded["name"] == model.current["name"]
    assert loaded["reference"] == "average"
    np.testing.assert_array_equal(loaded["events"], model.current["events"])
    assert dict(loaded["event_mapping"]) == dict(model.current["event_mapping"])

    assert loaded["montage"].name == "standard_1020"
    assert loaded["montage"].embedded is False
    loaded_positions = loaded["montage"].montage.get_positions()
    np.testing.assert_allclose(
        loaded_positions["ch_pos"][CH_NAMES[0]],
        original_montage_positions["ch_pos"][CH_NAMES[0]],
        atol=1e-6,
    )

    assert loaded_model.history == original_history

    # a post-load mutation continues (does not reset) the restored history
    loaded_model.resample(50)
    assert loaded_model.history[: len(original_history)] == original_history
    assert len(loaded_model.history) > len(original_history)


def test_ica_and_iclabel_round_trip(tmp_path, model_with_data):
    """ICA solutions and ICLabel probabilities survive a save/load round-trip."""
    model = model_with_data
    model.current["data"].filter(1.0, None, verbose=False)
    ica = ICA(n_components=4, method="infomax", random_state=42, max_iter=100)
    ica.fit(model.current["data"], verbose=False)
    ica.exclude = [0]
    model.current["ica"] = ica
    model.current["iclabel"] = np.random.default_rng(0).random((4, 7))

    proj_path = tmp_path / "project.mnelabproj"
    model.save_project(proj_path)

    loaded_model = Model()
    loaded_model.load_project(proj_path)
    loaded_ica = loaded_model.current["ica"]

    assert loaded_ica is not None
    assert loaded_ica.n_components_ == ica.n_components_
    assert loaded_ica.method == ica.method
    assert loaded_ica.exclude == ica.exclude
    np.testing.assert_allclose(
        loaded_model.current["iclabel"], model.current["iclabel"]
    )


def test_evicted_dataset_save_reuses_cache(tmp_path, model_with_data, monkeypatch):
    """Saving a project reuses an existing eviction cache instead of re-encoding."""
    model = model_with_data
    evicted_id = model.current["id"]
    original_data = model.current["data"].get_data().copy()
    model.evict_dataset(model.index)
    assert model.current["data"] is None  # confirm it's actually evicted

    calls = []
    orig_write_raw = project.write_raw
    monkeypatch.setattr(
        project,
        "write_raw",
        lambda fname, raw: calls.append(fname) or orig_write_raw(fname, raw),
    )

    proj_path = tmp_path / "project.mnelabproj"
    project.save_project(model, proj_path)

    assert calls == []  # the cached fif was copied directly, never re-written

    loaded_model = Model()
    loaded_model.load_project(proj_path)
    restored = loaded_model.data[loaded_model.find_index_by_id(evicted_id)]
    np.testing.assert_allclose(restored["data"].get_data(), original_data, atol=1e-9)


def test_merge_id_renumbering(tmp_path, model_with_data):
    """Merging a project renumbers ids/parent_ids to avoid collisions."""
    source = model_with_data
    # creates a parent/child pair; index now points at the duplicated child
    source.duplicate_data()
    source_project_path = tmp_path / "source.mnelabproj"
    source.save_project(source_project_path)

    target = Model()
    target_path = _make_raw_fif(tmp_path, "target")
    target.load(target_path)
    pre_merge_next_id = target._next_id

    target.load_project(source_project_path, merge=True)

    ids = [d["id"] for d in target.data]
    assert len(set(ids)) == len(ids)  # no collisions
    merged = sorted(
        (d for d in target.data if d["id"] >= pre_merge_next_id),
        key=lambda d: d["id"],
    )
    assert len(merged) == len(source.data) == 2
    merged_parent, merged_child = merged
    assert merged_parent["parent_id"] is None
    assert merged_child["parent_id"] == merged_parent["id"]

    # the dataset active in the source session (the duplicated child) is still
    # the active one after merging
    assert target.data[target.index]["id"] == merged_child["id"]
    assert target.dirty is True
    assert target.project_path is None


def test_dirty_flag_transitions(tmp_path):
    """`Model.dirty` tracks unsaved changes across load/save/mutate/load cycles."""
    model = Model()
    assert model.dirty is False

    path = _make_raw_fif(tmp_path, "sample")
    model.load(path)
    assert model.dirty is True

    proj_path = tmp_path / "project.mnelabproj"
    model.save_project(proj_path)
    assert model.dirty is False
    assert model.project_path == str(proj_path)

    model.duplicate_data()
    assert model.dirty is True
    assert len(model.data) == 2

    model.load_project(proj_path, merge=False)
    assert model.dirty is False
    assert model.project_path == str(proj_path)
    assert len(model.data) == 1  # the later duplicate is discarded, not saved


def test_format_version_guard(tmp_path):
    """Loading a project with an unsupported format version raises."""
    bad_path = tmp_path / "bad.mnelabproj"
    json_bytes = (
        b'{"format_version": 999, "index": -1, "next_id": 1, '
        b'"history": [], "datasets": []}'
    )
    with zipfile.ZipFile(bad_path, "w") as zf:
        zf.writestr("project.json", zstd.ZstdCompressor().compress(json_bytes))
    with pytest.raises(ProjectFormatError, match="format version"):
        project.load_project(bad_path)


def test_corrupt_file_raises_project_format_error(tmp_path):
    """A non-project file raises `ProjectFormatError`, not a raw exception."""
    bad_path = tmp_path / "bad.mnelabproj"
    bad_path.write_text("this is not a zip file")
    with pytest.raises(ProjectFormatError):
        project.load_project(bad_path)

    empty_zip_path = tmp_path / "empty.mnelabproj"
    with zipfile.ZipFile(empty_zip_path, "w"):
        pass  # zip file with no project.json at all
    with pytest.raises(ProjectFormatError):
        project.load_project(empty_zip_path)


def test_empty_session_round_trip(tmp_path):
    """A session with zero datasets saves and reloads cleanly."""
    model = Model()
    proj_path = tmp_path / "empty.mnelabproj"
    model.save_project(proj_path)

    loaded_model = Model()
    loaded_model.load_project(proj_path)
    assert loaded_model.data == []
    assert loaded_model.index == -1


def test_autosave_recovery_restore(qtbot, tmp_path, model_with_data, monkeypatch):
    """A recovery snapshot can be restored (or discarded) on the next launch."""
    recovery_path = tmp_path / "recovery.mnelabproj"
    monkeypatch.setattr(project, "RECOVERY_PATH", str(recovery_path))

    # simulate an autosave tick having written the recovery file
    project.save_project(model_with_data, recovery_path)
    assert recovery_path.is_file()

    # restore path
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    model = Model()
    view = MainWindow(model)
    model.view = view
    qtbot.addWidget(view)

    view.check_crash_recovery()

    assert len(model.data) == len(model_with_data.data)
    assert model.project_path is None
    assert model.dirty is True
    assert not recovery_path.is_file()

    # discard path
    project.save_project(model_with_data, recovery_path)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    model2 = Model()
    view2 = MainWindow(model2)
    model2.view = view2
    qtbot.addWidget(view2)

    view2.check_crash_recovery()

    assert model2.data == []
    assert not recovery_path.is_file()
