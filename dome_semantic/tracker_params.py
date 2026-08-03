#!/usr/bin/env python3
# tracker_params — ROS-declared WorldTrackerConfig (F33 T04)
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Declares every WorldTrackerConfig field as a ROS param and builds the config
from the node's current param values, so the config stays the single source of
truth for tuning (F34 precedent from dome_nav) instead of a hand-duplicated
param list drifting out of sync with it.

`class_profiles_inline` (a list, not a ROS-param-compatible scalar) and
`fx`/`fy` (camera intrinsics — unused until size estimation is wired into this
node) are skipped; `class_profile_path` still exposes the YAML-file escape
hatch for class profiles.
"""

from dome_semantic.tracker_config import WorldTrackerConfig

EXCLUDED_TRACKER_FIELDS = {"class_profiles_inline", "fx", "fy"}


def declare_tracker_config(node) -> WorldTrackerConfig:
    """node needs only declare_parameter(name, default) and
    get_parameter(name).value."""
    kwargs = {}
    for name, info in WorldTrackerConfig.model_fields.items():
        if name in EXCLUDED_TRACKER_FIELDS:
            continue
        default = "" if info.default is None else info.default
        node.declare_parameter(name, default)
        value = node.get_parameter(name).value
        kwargs[name] = (value or None) if info.default is None else value
    return WorldTrackerConfig(**kwargs)
