# © MNELAB developers
#
# License: BSD (3-clause)

import json
import os
import shutil
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import mne
import numpy as np
from mnextend import write_epochs, write_raw
from PySide6.QtCore import QStandardPaths

from mnelab.utils import Montage

PROJECT_FORMAT_VERSION = 1

RECOVERY_PATH = str(
    Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    / "recovery.mnelabproj"
)


class ProjectFormatError(Exception):
    """Raised when a file is not a valid/supported MNELAB project file."""


@dataclass
class LoadedProject:
    """Datasets and bookkeeping parsed from a `.mnelabproj` file."""

    datasets: list
    index: int
    next_id: int
    history: list


def _dataset_suffix(dtype):
    return "_raw.fif" if dtype == "raw" else "_epo.fif"


def save_project(model, fname):
    """Save the entire session held by `model` to a `.mnelabproj` file.

    Parameters
    ----------
    model : mnelab.model.Model
        The model whose `data`/`index`/`history` should be persisted.
    fname : str | Path
        Destination path. Written atomically (a temp file is renamed over the
        destination only after the archive is fully built).
    """
    dest = Path(fname).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=dest.parent, prefix=f".{dest.stem}.", suffix=".tmp"
    )
    os.close(tmp_fd)
    try:
        with (
            tempfile.TemporaryDirectory(prefix="mnelab_proj_build_") as scratch,
            zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf,
        ):
            datasets_meta = [
                _save_dataset(zf, scratch, dataset) for dataset in model.data
            ]
            project_json = {
                "format_version": PROJECT_FORMAT_VERSION,
                "index": model.index,
                "next_id": model._next_id,
                "history": list(model.history),
                "datasets": datasets_meta,
            }
            zf.writestr("project.json", json.dumps(project_json, indent=2))
        os.replace(tmp_path, dest)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _save_dataset(zf, scratch, dataset):
    """Write one dataset's data (and ICA, if present) into `zf`, return its metadata."""
    suffix = _dataset_suffix(dataset["dtype"])
    arcname = f"data/{dataset['id']}{suffix}"

    # reuse an existing eviction-cache fif if one is still valid, regardless of
    # whether the dataset is currently evicted -- cheaper than re-encoding
    if dataset["_cache_path"] is not None:
        zf.write(dataset["_cache_path"], arcname)
    elif dataset["data"] is not None:
        scratch_path = str(Path(scratch) / f"{dataset['id']}{suffix}")
        if dataset["dtype"] == "epochs":
            write_epochs(scratch_path, dataset["data"])
        else:
            write_raw(scratch_path, dataset["data"])
        zf.write(scratch_path, arcname)
    else:
        raise RuntimeError(
            f"Dataset {dataset['id']} has no in-memory data and no cache file; "
            "this indicates a Model bug."
        )

    ica_arcname = None
    if dataset["ica"] is not None:
        ica_scratch_path = str(Path(scratch) / f"{dataset['id']}_ica.fif")
        dataset["ica"].save(ica_scratch_path, overwrite=True)
        ica_arcname = f"data/{dataset['id']}_ica.fif"
        zf.write(ica_scratch_path, ica_arcname)

    montage = dataset["montage"]
    montage_meta = (
        {
            "name": montage.name,
            "path": str(montage.path) if montage.path else None,
            "embedded": montage.embedded,
        }
        if montage is not None
        else None
    )
    events = dataset["events"]
    events_meta = events.tolist() if events is not None else []
    event_mapping = dataset["event_mapping"]
    event_mapping_meta = (
        {str(k): v for k, v in event_mapping.items()} if event_mapping else {}
    )
    iclabel = dataset["iclabel"]
    iclabel_meta = iclabel.tolist() if iclabel is not None else None

    return {
        "id": dataset["id"],
        "parent_id": dataset["parent_id"],
        "name": dataset["name"],
        "fname": dataset["fname"],
        "ftype": dataset["ftype"],
        "fsize": dataset["fsize"],
        "dtype": dataset["dtype"],
        "data_path": arcname,
        "montage": montage_meta,
        "events": events_meta,
        "event_mapping": event_mapping_meta,
        "reference": dataset["reference"],
        "ica_path": ica_arcname,
        "iclabel": iclabel_meta,
    }


def load_project(fname):
    """Parse a `.mnelabproj` file into a `LoadedProject`.

    Parameters
    ----------
    fname : str | Path
        Path to the `.mnelabproj` file to load.

    Returns
    -------
    LoadedProject
        Datasets (ready to become `Model.data` entries) plus `index`,
        `next_id`, and `history`.

    Raises
    ------
    ProjectFormatError
        If `fname` is not a valid/supported MNELAB project file.
    """
    try:
        zf = zipfile.ZipFile(fname)
    except (zipfile.BadZipFile, OSError) as e:
        raise ProjectFormatError(f"{fname} is not a valid MNELAB project file.") from e

    with zf:
        try:
            meta = json.loads(zf.read("project.json"))
        except (KeyError, json.JSONDecodeError) as e:
            raise ProjectFormatError(
                f"{fname} is not a valid MNELAB project file."
            ) from e

        if meta.get("format_version") != PROJECT_FORMAT_VERSION:
            raise ProjectFormatError(
                "Unsupported project file format version: "
                f"{meta.get('format_version')!r}."
            )

        try:
            datasets = [_load_dataset(zf, entry) for entry in meta["datasets"]]
        except KeyError as e:
            raise ProjectFormatError(
                f"{fname} is not a valid MNELAB project file."
            ) from e

    return LoadedProject(
        datasets=datasets,
        index=meta["index"],
        next_id=meta["next_id"],
        history=list(meta["history"]),
    )


def _load_dataset(zf, entry):
    """Extract one dataset's data (and ICA, if present) from `zf`, build its dict."""
    dtype = entry["dtype"]
    suffix = _dataset_suffix(dtype)
    fd, cache_path = tempfile.mkstemp(suffix=suffix, prefix="mnelab_")
    os.close(fd)
    with zf.open(entry["data_path"]) as src, open(cache_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    if dtype == "epochs":
        data = mne.read_epochs(cache_path, preload=True)
    else:
        data = mne.io.read_raw_fif(cache_path, preload=True)

    events = entry["events"]
    events = np.array(events, dtype=int) if events else np.empty((0, 3), dtype=int)
    if dtype == "raw":
        data.events = events

    event_mapping = defaultdict(
        str, {int(k): v for k, v in entry["event_mapping"].items()}
    )

    montage_meta = entry.get("montage")
    if montage_meta is not None:
        montage = Montage(
            data.get_montage(),
            name=montage_meta["name"],
            path=Path(montage_meta["path"]) if montage_meta["path"] else None,
            embedded=montage_meta["embedded"],
        )
    else:
        montage = None

    ica = None
    if entry.get("ica_path"):
        ica_fd, ica_tmp_path = tempfile.mkstemp(suffix="_ica.fif", prefix="mnelab_")
        os.close(ica_fd)
        try:
            with zf.open(entry["ica_path"]) as src, open(ica_tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            ica = mne.preprocessing.read_ica(ica_tmp_path)
        finally:
            Path(ica_tmp_path).unlink(missing_ok=True)

    iclabel = entry.get("iclabel")
    iclabel = np.array(iclabel, dtype=float) if iclabel is not None else None

    return defaultdict(
        lambda: None,
        id=entry["id"],
        parent_id=entry["parent_id"],
        name=entry["name"],
        fname=entry["fname"],
        ftype=entry["ftype"],
        fsize=entry["fsize"],
        data=data,
        dtype=dtype,
        montage=montage,
        events=events,
        event_mapping=event_mapping,
        reference=entry.get("reference"),
        ica=ica,
        iclabel=iclabel,
        _cache_path=cache_path,
    )
