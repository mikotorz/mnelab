# © MNELAB developers
#
# License: BSD (3-clause)

"""Save, load, list, and delete named dialog-setting presets as JSON.

Presets are grouped by category (one per dialog, e.g. `"filter"`, `"epoch"`), each
holding any number of named presets. Unlike `pipeline_preset.py`, these files are never
exported, imported, or handed to another user, so a missing or corrupt store is
silently treated as empty rather than raising.
"""

import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths

PRESETS_PATH = str(
    Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
    )
    / "mnelab_presets.json"
)


def _read_all():
    try:
        return json.loads(Path(PRESETS_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_all(data):
    dest = Path(PRESETS_PATH).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(data, indent=2).encode("utf-8")
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


def list_presets(category):
    """Return the sorted names of every preset saved under `category`."""
    return sorted(_read_all().get(category, {}))


def save_preset(category, name, values):
    """Save (or overwrite) a named preset's values under `category`."""
    data = _read_all()
    data.setdefault(category, {})[name] = values
    _write_all(data)


def load_preset(category, name):
    """Return the values of the preset `name` saved under `category`.

    Raises
    ------
    KeyError
        If `category` or `name` does not exist.
    """
    return _read_all()[category][name]


def delete_preset(category, name):
    """Delete the preset `name` under `category`, if it exists."""
    data = _read_all()
    if name in data.get(category, {}):
        del data[category][name]
        _write_all(data)
