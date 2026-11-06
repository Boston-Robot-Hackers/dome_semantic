#!/usr/bin/env python3
# test_shipped_config — the robot's config/ files load and actually turn PASA on
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Checks config/semantic_map.yaml and config/class_profiles.yaml, the files
semantic.launch.py hands the node.

Without them the node runs at WorldTrackerConfig defaults (PASA off), which is
the bug F34 fixes, so these tests guard both the files and the behaviour they
buy.
"""

import pathlib

import yaml

from dome_semantic.class_profiles import load_class_profiles
from dome_semantic.tracker_config import WorldTrackerConfig
from dome_semantic.tracker_params import EXCLUDED_TRACKER_FIELDS
from dome_semantic.world_tracker import WorldTracker

CONFIG_DIR = pathlib.Path(__file__).parent.parent / "config"
PARAMS_FILE = CONFIG_DIR / "semantic_map.yaml"
PROFILES_FILE = CONFIG_DIR / "class_profiles.yaml"


def shipped_params() -> dict:
    return yaml.safe_load(PARAMS_FILE.read_text())["/**"]["ros__parameters"]


def shipped_config(**overrides) -> WorldTrackerConfig:
    params = {**shipped_params(), "class_profile_path": str(PROFILES_FILE)}
    return WorldTrackerConfig(**{**params, **overrides})


def test_profiles_load_can_and_cup():
    profiles = load_class_profiles(str(PROFILES_FILE))
    assert set(profiles) == {"can", "cup"}
    for profile in profiles.values():
        assert profile.abbrev
        assert profile.merge_radius_m is not None
        assert profile.drift_tolerance_m is not None


# Labels must stay "can"/"cup": dome_mission resolves "nav go can" by exact match.
def test_canonical_class_matches_detector_label():
    for name, profile in load_class_profiles(str(PROFILES_FILE)).items():
        assert profile.detector_labels == [name]


def test_params_turn_pasa_on():
    assert shipped_config().use_class_profiles is True


# A key the node never declares is silently dropped by ROS, so a typo would hide.
def test_every_param_is_a_declared_tracker_field():
    declared = set(WorldTrackerConfig.model_fields) - EXCLUDED_TRACKER_FIELDS
    assert set(shipped_params()) <= declared


# ROS rejects an int for a param declared with a float default, failing at startup.
def test_param_types_match_declared_defaults():
    for name, value in shipped_params().items():
        default = WorldTrackerConfig.model_fields[name].default
        assert type(value) is type(default), name


def test_shipped_config_builds_a_tracker():
    tracker = WorldTracker(shipped_config())
    assert set(tracker.profiles) == {"can", "cup"}


def second_can_after_first_confirms(config: WorldTrackerConfig) -> int:
    """Confirm one can, then bring a second into view 0.5 m away, as a spin
    survey does. Returns the confirmed count."""
    first_can = ((1.2, -0.25, 0.0), "can", 0, 1, None)
    second_can = ((1.2, 0.25, 0.0), "can", 0, 2, None)
    tracker = WorldTracker(config)
    for frame in range(10):
        tracker.update([first_can], frame * 0.2)
    for frame in range(10, 30):
        tracker.update([first_can, second_can], frame * 0.2)
    return len(tracker.confirmed_targets)


# The behaviour F34 exists for: PASA's tight per-class radius keeps them apart.
def test_shipped_config_keeps_two_close_cans_separate():
    assert second_can_after_first_confirms(shipped_config()) == 2


# Guards the test above: at defaults the 0.6 m confirmed radius absorbs the second can.
def test_defaults_merge_two_close_cans():
    assert second_can_after_first_confirms(WorldTrackerConfig()) == 1
