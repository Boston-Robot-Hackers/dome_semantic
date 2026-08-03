#!/usr/bin/env python3
# semantic_persistence — save/restore the semantic map, keyed to SLAM map identity
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Persists a WorldTracker's confirmed targets to
`~/.dome/semantic_maps/<map_name>.json` (F33 T06, G8) so Mode B can reload the
semantic map matching the currently loaded SLAM map, mirroring the
`--map_name` convention `slam_manager`/`explorer_manager_node` already use
(`~/.dome/slam_maps/<name>`, `~/.dome/telemetry/e<name>...`).

The on-disk file is a small envelope, `{"map_name": ..., "targets": [...]}`, wrapping
WorldTracker.to_json()'s existing bare-list format rather than changing it — the
tracking core stays free of any "map identity" concept (that's a persistence/ROS-layer
concern), and the envelope's own map_name is a belt-and-suspenders check: the save path
is already derived from map_name, but the sanitizing regex is lossy (e.g. "room A" and
"room#A" both become "room_A"), so a collision is possible. Anything that isn't a
matching envelope - missing file, wrong map_name, or an unrecognized/pre-map_name-keying
format - falls back to a fresh tracker with a warning, never a silent merge of targets
recorded for a different map (style guide: never guess-and-fix a violated expectation).
"""

import json
import os
import pathlib
import re

from dome_semantic.tracker_config import WorldTrackerConfig
from dome_semantic.world_tracker import WorldTracker


def semantic_map_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".dome", "semantic_maps")


def semantic_map_path(map_name: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", map_name)
    return os.path.join(semantic_map_dir(), f"{safe_name}.json")


def save_semantic_map(tracker: WorldTracker, map_name: str) -> str:
    """Write tracker's confirmed targets to disk, keyed to map_name.

    Returns the path written."""
    os.makedirs(semantic_map_dir(), exist_ok=True)
    path = semantic_map_path(map_name)
    envelope = {"map_name": map_name, "targets": json.loads(tracker.to_json())}
    pathlib.Path(path).write_text(json.dumps(envelope))
    return path


def load_semantic_map(
    map_name: str, config: WorldTrackerConfig, warn_fn=lambda msg: None
) -> WorldTracker:
    """Load the semantic map saved for map_name, or a fresh WorldTracker if none
    exists or the file's own map_name doesn't match the requested one."""
    path = semantic_map_path(map_name)
    if not os.path.exists(path):
        return WorldTracker(config)

    raw = json.loads(pathlib.Path(path).read_text())
    saved_name = raw.get("map_name") if isinstance(raw, dict) else None
    if saved_name != map_name:
        warn_fn(
            f"Semantic map {path} was saved for map_name={saved_name!r}, not "
            f"{map_name!r} — starting a fresh map instead of merging mismatched data."
        )
        return WorldTracker(config)

    return WorldTracker.from_json(json.dumps(raw["targets"]), config)
