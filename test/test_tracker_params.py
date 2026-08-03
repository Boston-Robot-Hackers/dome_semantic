#!/usr/bin/env python3
# test_tracker_params — F33 T04: ROS-declared WorldTrackerConfig round-trip
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from types import SimpleNamespace

from dome_semantic.tracker_config import WorldTrackerConfig
from dome_semantic.tracker_params import EXCLUDED_TRACKER_FIELDS, declare_tracker_config


class FakeNode:
    """Minimal declare/get node. Mirrors real rclpy semantics: an override supplied
    at construction (e.g. from a launch file) wins over declare_parameter's default.
    """

    def __init__(self, overrides: dict | None = None):
        self.overrides = overrides or {}
        self.declared = {}

    def declare_parameter(self, name, default):
        self.declared[name] = self.overrides.get(name, default)

    def get_parameter(self, name):
        return SimpleNamespace(value=self.declared[name])


def test_declare_round_trips_default_config():
    node = FakeNode()

    config = declare_tracker_config(node)

    assert config == WorldTrackerConfig()


def test_declares_every_field_except_excluded():
    node = FakeNode()

    declare_tracker_config(node)

    expected = set(WorldTrackerConfig.model_fields) - EXCLUDED_TRACKER_FIELDS
    assert set(node.declared) == expected


def test_declared_defaults_are_launch_overridable():
    node = FakeNode(overrides={"min_frames": 3, "min_time_s": 0.5})

    config = declare_tracker_config(node)

    assert config.min_frames == 3
    assert config.min_time_s == 0.5


def test_none_default_field_round_trips_via_empty_string():
    node = FakeNode()

    config = declare_tracker_config(node)

    assert node.declared["class_profile_path"] == ""
    assert config.class_profile_path is None
