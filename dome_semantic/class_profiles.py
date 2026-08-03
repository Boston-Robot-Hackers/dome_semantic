#!/usr/bin/env python3
# class_profiles — TargetClassProfile dataclass and YAML loader
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from pathlib import Path

import yaml
from pydantic import BaseModel


class TargetClassProfile(BaseModel):
    canonical_class: str
    display_name: str | None = None
    abbrev: str | None = None
    detector_labels: list = []
    height_range_m: tuple
    diameter_range_m: tuple
    aspect_ratio_range: tuple
    max_stationary_speed_mps: float
    size_confidence_floor: float = 0.5
    depth_noise_scale: float = 1.0
    merge_radius_m: float | None = None
    # Tight confirmed-radius for known-stationary classes (sensor noise only, not odometry drift).
    # When set, find_match_pasa uses this instead of confirmed_assoc_mult * max_assoc_dist_m.
    drift_tolerance_m: float | None = None


def build_abbrev_map(profiles: dict, label_map: dict) -> dict:
    """Return {detector_label: abbrev} for all profiles that have abbrev set."""
    result = {}
    for det_label, canonical in label_map.items():
        profile = profiles.get(canonical)
        if profile and profile.abbrev:
            result[det_label] = profile.abbrev
    return result


def build_label_map(profiles: dict) -> dict:
    mapping = {}
    for canonical, profile in profiles.items():
        for lbl in profile.detector_labels:
            mapping[lbl] = canonical
    return mapping


def parse_class_profiles(entries: list) -> dict:
    profiles = {}
    for entry in entries:
        p = TargetClassProfile(**entry)
        profiles[p.canonical_class] = p
    return profiles


def load_class_profiles(path: str) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return parse_class_profiles(raw.get("class_profiles", []))
