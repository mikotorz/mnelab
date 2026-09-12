# © MNELAB developers
#
# License: BSD (3-clause)

"""Save, load, import, and export multi-stage Pipeline configurations as JSON."""

import json
import os
import tempfile
from pathlib import Path

from mnelab.dialogs.pipeline import (
    STEP_REGISTRY,
    PipelinePresetFormatError,
    PipelineStep,
)

PRESET_FORMAT_VERSION = 1


def save_pipeline_preset(stages, fname):
    """Save a multi-stage pipeline to a `.json` preset file.

    Parameters
    ----------
    stages : list[tuple[str, list[PipelineStep]]]
        Each stage's name and queued steps, in order.
    fname : str | Path
        Destination path. Written atomically (a temp file is renamed over the
        destination only after the file is fully built).

    Raises
    ------
    PipelinePresetFormatError
        If a queued step cannot be represented in a preset (e.g. an Apply Montage
        step using a montage embedded in a specific recording's own digitization).
    """
    stages_meta = []
    for name, steps in stages:
        steps_meta = [
            {
                "kind": step.kind,
                "label": step.label,
                "params": STEP_REGISTRY[step.kind].to_preset(step.params),
            }
            for step in steps
        ]
        stages_meta.append({"name": name, "steps": steps_meta})

    preset_json = {"format_version": PRESET_FORMAT_VERSION, "stages": stages_meta}
    json_bytes = json.dumps(preset_json, indent=2).encode("utf-8")

    dest = Path(fname).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=dest.parent, prefix=f".{dest.stem}.", suffix=".tmp"
    )
    os.close(tmp_fd)
    try:
        Path(tmp_path).write_bytes(json_bytes)
        os.replace(tmp_path, dest)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def load_pipeline_preset(fname):
    """Parse a `.json` pipeline preset file.

    Parameters
    ----------
    fname : str | Path
        Path to the `.json` pipeline preset file to load.

    Returns
    -------
    stages : list[tuple[str, list[PipelineStep]]]
        Each stage's name and steps, in order. Steps are returned as-is; whether
        each one is still applicable to a particular dataset (e.g. a Crop step
        whose bounds exceed a shorter recording) is for the caller to decide.
    skipped : list[str]
        Human-readable descriptions of steps that could not be restored at all --
        an unknown step kind, or one whose stored parameters could not be turned
        back into live ones (e.g. a missing custom montage file).

    Raises
    ------
    PipelinePresetFormatError
        If `fname` is not a valid/supported MNELAB pipeline preset file.
    """
    try:
        meta = json.loads(Path(fname).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise PipelinePresetFormatError(
            f"{fname} is not a valid MNELAB pipeline preset file."
        ) from e

    if meta.get("format_version") != PRESET_FORMAT_VERSION:
        raise PipelinePresetFormatError(
            "Unsupported pipeline preset file format version: "
            f"{meta.get('format_version')!r}."
        )

    try:
        stage_entries = meta["stages"]
    except KeyError as e:
        raise PipelinePresetFormatError(
            f"{fname} is not a valid MNELAB pipeline preset file."
        ) from e

    stages = []
    skipped = []
    for i, stage_meta in enumerate(stage_entries):
        steps = []
        for step_meta in stage_meta["steps"]:
            kind = step_meta["kind"]
            label = step_meta.get("label", kind)
            spec = STEP_REGISTRY.get(kind)
            if spec is None:
                skipped.append(f"{label} (unknown step type '{kind}')")
                continue
            try:
                params = spec.from_preset(step_meta["params"])
            except PipelinePresetFormatError as e:
                skipped.append(f"{label} ({e})")
                continue
            steps.append(PipelineStep(kind, label, params))
        name = stage_meta.get("name") or f"Stage {i + 1}"
        stages.append((name, steps))

    return stages, skipped
