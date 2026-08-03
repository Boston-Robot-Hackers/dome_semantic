#!/usr/bin/env python3
# test_semantic_persistence — F33 T06: save/restore keyed to SLAM map identity
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import json
from unittest.mock import patch

from dome_semantic.semantic_persistence import (
    load_semantic_map,
    save_semantic_map,
    semantic_map_path,
)
from dome_semantic.targets import ConfirmedTarget
from dome_semantic.tracker_config import WorldTrackerConfig
from dome_semantic.world_tracker import WorldTracker


def isolated(tmp_path):
    return patch(
        "dome_semantic.semantic_persistence.semantic_map_dir",
        return_value=str(tmp_path),
    )


def make_tracker_with_target() -> WorldTracker:
    tracker = WorldTracker(WorldTrackerConfig())
    tracker.confirmed.append(
        ConfirmedTarget(
            target_id=1,
            label="can",
            canonical_class="can",
            xyz_world=(1.0, 2.0, 0.0),
            observation_count=5,
            confirmed_at_s=10.0,
            last_seen_s=10.0,
        )
    )
    return tracker


def test_semantic_map_path_sanitizes_name(tmp_path):
    with isolated(tmp_path):
        path = semantic_map_path("my room/1")
    assert path == str(tmp_path / "my_room_1.json")


def test_save_writes_map_name_envelope(tmp_path):
    tracker = make_tracker_with_target()
    with isolated(tmp_path):
        path = save_semantic_map(tracker, "kitchen")
    envelope = json.loads((tmp_path / "kitchen.json").read_text())
    assert path == str(tmp_path / "kitchen.json")
    assert envelope["map_name"] == "kitchen"
    assert envelope["targets"][0]["label"] == "can"


def test_round_trip_save_then_load_recovers_confirmed_target(tmp_path):
    tracker = make_tracker_with_target()
    with isolated(tmp_path):
        save_semantic_map(tracker, "kitchen")
        loaded = load_semantic_map("kitchen", WorldTrackerConfig())

    assert len(loaded.confirmed) == 1
    assert loaded.confirmed[0].label == "can"
    assert loaded.confirmed[0].xyz_world == (1.0, 2.0, 0.0)
    assert loaded.confirmed[0].observation_count == 5


def test_load_missing_file_returns_fresh_tracker(tmp_path):
    with isolated(tmp_path):
        loaded = load_semantic_map("never-saved", WorldTrackerConfig())

    assert loaded.confirmed == []


def test_load_unrecognized_format_returns_fresh_and_warns(tmp_path):
    # A bare list (e.g. an old dome_vision-era file, or anything that isn't
    # this module's {"map_name": ..., "targets": [...]} envelope) has no
    # map_name to verify against — treated the same as any other mismatch:
    # fresh tracker, warn, never guess at what it might have meant.
    (tmp_path / "living_room.json").write_text(json.dumps([{"target_id": 1}]))
    warnings = []
    with isolated(tmp_path):
        loaded = load_semantic_map(
            "living_room", WorldTrackerConfig(), warn_fn=warnings.append
        )

    assert loaded.confirmed == []
    assert len(warnings) == 1
    assert "living_room" in warnings[0]


def test_load_mismatched_map_name_returns_fresh_and_warns_not_merges(tmp_path):
    tracker = make_tracker_with_target()
    warnings = []
    with isolated(tmp_path):
        # "room a" and "room#a" both sanitize to room_a.json — a real
        # filename collision, not a contrived one, is what the envelope's
        # own map_name check is there to catch.
        save_semantic_map(tracker, "room a")
        loaded = load_semantic_map(
            "room#a", WorldTrackerConfig(), warn_fn=warnings.append
        )

    assert loaded.confirmed == []  # never silently merges mismatched data
    assert len(warnings) == 1
    assert "room a" in warnings[0] and "room#a" in warnings[0]
