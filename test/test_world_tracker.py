#!/usr/bin/env python3
# test_world_tracker — unit tests for WorldTracker, PotentialTarget, ConfirmedTarget
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import numpy as np
import pytest
from dome_semantic.world_tracker import (
    WorldTracker,
    WorldTrackerConfig,
    PotentialTarget,
    ConfirmedTarget,
)
from dome_semantic.targets import Observation
from dome_semantic.size_estimate import SizeEstimate, estimate_size_m
from dome_semantic.class_profiles import build_label_map, load_class_profiles


# --- helpers ---

def cfg(**kwargs):
    return WorldTrackerConfig(**kwargs)


def fast_cfg(**kwargs):
    """Config that confirms immediately after 2 frames over 0.1s."""
    defaults = dict(min_frames=2, min_time_s=0.1, lost_timeout_s=2.0, remove_timeout_s=5.0)
    defaults.update(kwargs)
    return WorldTrackerConfig(**defaults)


def obs(xyz, label, frame=0, track_id=None):
    return (xyz, label, frame, track_id)


def feed(tracker, xyz, label, n_frames, start_t=0.0, dt=0.5, track_id=None):
    """Feed n_frames identical observations; return last update() result."""
    result = []
    for i in range(n_frames):
        result = tracker.update([obs(xyz, label, i, track_id)], start_t + i * dt)
    return result


# --- T01: dataclass instantiation ---

def test_config_defaults():
    c = WorldTrackerConfig()
    assert c.max_assoc_dist_m == 0.3
    assert c.min_frames == 5
    assert c.min_time_s == 1.0
    assert c.lost_timeout_s == 5.0
    assert c.remove_timeout_s == 30.0
    assert c.require_anchor is False


def test_potential_target_fields():
    p = PotentialTarget(
        target_id=1, label="cup", canonical_class="cup", xyz_world=(1.0, 0.5, 0.0),
        observation_count=1, first_seen_s=0.0, last_seen_s=0.0,
    )
    assert p.target_id == 1
    assert p.label == "cup"
    assert p.canonical_class == "cup"
    assert p.track_ids == set()


def test_confirmed_target_fields():
    t = ConfirmedTarget(
        target_id=2, label="can", canonical_class="can", xyz_world=(2.0, 0.0, 0.0),
        observation_count=5, confirmed_at_s=1.0, last_seen_s=1.5,
    )
    assert t.is_lost is False


# --- T02: association logic ---

def test_single_observation_creates_potential():
    tracker = WorldTracker(fast_cfg())
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    assert len(tracker.potential_targets) == 1
    assert tracker.potential_targets[0].label == "cup"
    assert tracker.potential_targets[0].observation_count == 1


def test_nearby_same_label_merges():
    tracker = WorldTracker(fast_cfg())
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    tracker.update([obs((1.01, 0.0, 0.0), "cup")], 0.1)
    potentials = tracker.potential_targets
    confirmed = tracker.confirmed_targets
    assert len(potentials) + len(confirmed) == 1


def test_far_same_label_creates_separate():
    tracker = WorldTracker(fast_cfg())
    tracker.update([obs((1.0, 0.0, 0.0), "cup"), obs((5.0, 0.0, 0.0), "cup")], 0.0)
    assert len(tracker.potential_targets) == 2


def test_different_label_same_location_not_merged():
    tracker = WorldTracker(fast_cfg())
    tracker.update([obs((1.0, 0.0, 0.0), "cup"), obs((1.0, 0.0, 0.0), "can")], 0.0)
    assert len(tracker.potential_targets) == 2


def test_track_id_hint_associates_at_loose_distance():
    tracker = WorldTracker(fast_cfg(max_assoc_dist_m=0.1))
    tracker.update([obs((1.0, 0.0, 0.0), "cup", track_id=42)], 0.0)
    # 0.15m > strict (0.1) but < loose (0.2) — should still associate via track_id
    tracker.update([obs((1.15, 0.0, 0.0), "cup", track_id=42)], 0.2)
    all_targets = tracker.potential_targets + tracker.confirmed_targets
    assert len(all_targets) == 1


# --- T03: state transitions ---

def test_promotion_after_min_frames_and_time():
    tracker = WorldTracker(fast_cfg())
    result = feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    assert len(result) == 1
    assert result[0].label == "cup"


def test_no_promotion_too_fast():
    tracker = WorldTracker(fast_cfg(min_frames=2, min_time_s=1.0))
    result = feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.1)
    assert len(result) == 0
    assert len(tracker.potential_targets) == 1


def test_confirmed_goes_lost():
    tracker = WorldTracker(fast_cfg(lost_timeout_s=1.0, remove_timeout_s=100.0))
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    # advance past lost_timeout but well before remove_timeout
    result = tracker.update([], 3.0)
    assert len(result) == 0
    assert tracker.confirmed_targets[0].is_lost is True


def test_lost_target_removed():
    tracker = WorldTracker(fast_cfg(lost_timeout_s=1.0, remove_timeout_s=2.0))
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    tracker.update([], 20.0)
    assert len(tracker.confirmed_targets) == 0


def test_stale_potential_removed():
    tracker = WorldTracker(fast_cfg(lost_timeout_s=1.0))
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    tracker.update([], 5.0)
    assert len(tracker.potential_targets) == 0


def test_require_anchor_first_object_exempt():
    tracker = WorldTracker(fast_cfg(require_anchor=True))
    result = feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    assert len(result) == 1


def test_require_anchor_second_needs_coobservation():
    tracker = WorldTracker(fast_cfg(require_anchor=True))
    # confirm first object
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    # observe second object alone — should NOT confirm
    tracker2 = WorldTracker(fast_cfg(require_anchor=True))
    feed(tracker2, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    # now feed second object without co-observation
    t = 1.0
    for i in range(3):
        tracker2.update([obs((5.0, 0.0, 0.0), "can", track_id=99)], t + i * 0.2)
    assert all(t.label != "can" for t in tracker2.confirmed_targets)


def test_require_anchor_second_confirms_with_coobservation():
    tracker = WorldTracker(fast_cfg(require_anchor=True))
    # confirm first object (cup)
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    assert len(tracker.confirmed_targets) == 1
    # now observe can alongside confirmed cup
    t = 1.0
    for i in range(3):
        tracker.update([
            obs((1.0, 0.0, 0.0), "cup"),
            obs((5.0, 0.0, 0.0), "can"),
        ], t + i * 0.2)
    assert any(t.label == "can" for t in tracker.confirmed_targets)


# --- T04: query() and properties ---

def test_query_returns_first_confirmed():
    tracker = WorldTracker(fast_cfg())
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    result = tracker.query("cup")
    assert result is not None
    assert result.label == "cup"


def test_query_returns_nth():
    tracker = WorldTracker(fast_cfg())
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    feed(tracker, (3.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2, start_t=1.0)
    assert tracker.query("cup", 0) is not None
    assert tracker.query("cup", 1) is not None


def test_query_missing_label_returns_none():
    tracker = WorldTracker(fast_cfg())
    assert tracker.query("cup") is None


def test_query_n_exceeds_count_returns_none():
    tracker = WorldTracker(fast_cfg())
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    assert tracker.query("cup", 1) is None


def test_potential_targets_property():
    tracker = WorldTracker(fast_cfg())
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    assert len(tracker.potential_targets) == 1


# --- T06: edge-case tests ---

def test_empty_observations_no_crash():
    tracker = WorldTracker(fast_cfg())
    result = tracker.update([], 0.0)
    assert result == []


def test_all_objects_removed_empty_list():
    tracker = WorldTracker(fast_cfg(lost_timeout_s=1.0, remove_timeout_s=2.0))
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    tracker.update([], 20.0)
    assert tracker.confirmed_targets == []
    assert tracker.update([], 20.1) == []


def test_query_on_empty_tracker():
    tracker = WorldTracker(fast_cfg())
    assert tracker.query("cup") is None
    assert tracker.query("can", 2) is None


def test_reobserved_after_lost_clears_flag():
    tracker = WorldTracker(fast_cfg(lost_timeout_s=1.0, remove_timeout_s=100.0))
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    tracker.update([], 3.0)  # goes lost
    assert tracker.confirmed_targets[0].is_lost is True
    count_before = tracker.confirmed_targets[0].observation_count
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 3.1)
    t = tracker.confirmed_targets[0]
    assert t.is_lost is False
    assert t.observation_count == count_before + 1


def test_running_mean_converges():
    # min_frames=10, min_time_s=0.0 — promotes exactly on the 10th frame
    tracker = WorldTracker(WorldTrackerConfig(min_frames=10, min_time_s=0.0))
    true_xyz = (2.0, 3.0, 1.0)
    for i in range(10):
        noisy = (true_xyz[0] + 0.01 * (i % 2), true_xyz[1], true_xyz[2])
        tracker.update([obs(noisy, "cup", i)], float(i))
    # after 10 frames the potential is promoted; check confirmed xyz
    t = tracker.confirmed_targets[0]
    assert abs(t.xyz_world[0] - true_xyz[0]) < 0.02
    assert abs(t.xyz_world[1] - true_xyz[1]) < 1e-9


def test_immediate_confirmation():
    tracker = WorldTracker(WorldTrackerConfig(min_frames=1, min_time_s=0.0))
    result = tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    assert len(result) == 1
    assert result[0].label == "cup"


# --- F38 T01: PASA config fields, TargetClassProfile, load_class_profiles ---

# All new PASA fields must have safe defaults so existing callers need no changes.
def test_world_tracker_config_pasa_defaults():

    c = WorldTrackerConfig()
    assert c.use_class_profiles is False
    assert c.class_profile_path is None
    assert c.assoc_cost_distance_weight == 1.0
    assert c.assoc_cost_size_weight == 0.0
    assert c.assoc_cost_stationary_weight == 0.0
    assert c.assoc_cost_track_hint_weight == 0.3
    assert c.stationary_window_s == 2.0
    assert c.size_confidence_floor == 0.5
    assert c.enable_false_split_recovery is False
    assert c.false_split_lookback_s == 5.0
    assert c.fx == pytest.approx(493.86)
    assert c.fy == pytest.approx(493.87)


# Note: dome_vision's AppConfig-level world_tracker-section tests
# (test_appconfig_world_tracker_section, test_appconfig_world_tracker_defaults_when_absent)
# are not ported here (F33 T02) - AppConfig is dome_vision's whole vision-pipeline
# config (ModelConfig/RoboflowConfig/InferenceConfig/CameraConfig/...), not part of
# WorldTracker's own pure closure. They stay as dome_vision's own coverage.


# class_profiles.yaml must load exactly two canonical classes (can, cup) with no parse errors.
def test_load_class_profiles_two_entries():
    profiles = load_class_profiles("examples/configs/class_profiles.yaml")
    assert len(profiles) == 2
    assert set(profiles.keys()) == {"soda can", "coffee cup"}


# Each profile must expose all required physical dimension fields with plausible values.
def test_class_profile_fields():
    profiles = load_class_profiles("examples/configs/class_profiles.yaml")
    can = profiles["soda can"]
    assert can.canonical_class == "soda can"
    assert "can" in can.detector_labels
    assert len(can.height_range_m) == 2
    assert len(can.diameter_range_m) == 2
    assert can.max_stationary_speed_mps > 0
    cup = profiles["coffee cup"]
    assert "cup" in cup.detector_labels


# drift_tolerance_m must be parsed from YAML and accessible on each profile.
def test_class_profile_drift_tolerance_m_loaded():
    profiles = load_class_profiles("examples/configs/class_profiles.yaml")
    assert profiles["soda can"].drift_tolerance_m == pytest.approx(0.15)
    assert profiles["coffee cup"].drift_tolerance_m == pytest.approx(0.20)


# --- F38 T02: label normalization ---

# build_label_map must map every detector_label to its canonical class.
def test_build_label_map():
    profiles = load_class_profiles("examples/configs/class_profiles.yaml")
    lmap = build_label_map(profiles)
    assert lmap["cup"] == "coffee cup"
    assert lmap["can"] == "soda can"


# Detector labels must resolve to their canonical class when profiles are loaded.
def test_normalize_label_known():
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
    ))
    assert tracker.label_map.get("cup", "cup") == "coffee cup"
    assert tracker.label_map.get("can", "can") == "soda can"


# Labels not in any profile must pass through unchanged so unknown classes still track.
def test_normalize_label_unknown_passthrough():
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
    ))
    assert tracker.label_map.get("widget", "widget") == "widget"


# With use_class_profiles=False, label_map is empty so get falls back to label itself.
def test_normalize_label_disabled():
    tracker = WorldTracker(WorldTrackerConfig(use_class_profiles=False))
    assert tracker.label_map.get("cup", "cup") == "cup"


# Two observations of "cup" near the same position must merge into one target.
def test_coarse_labels_associate_to_same_target():
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
        min_frames=2, min_time_s=0.0,
    ))
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    tracker.update([obs((1.01, 0.0, 0.0), "cup")], 0.2)
    all_targets = tracker.potential_targets + tracker.confirmed_targets
    assert len(all_targets) == 1


# Without profiles, "cup" and "can" are distinct labels and must NOT merge.
def test_class_profiles_disabled_no_normalization():
    tracker = WorldTracker(WorldTrackerConfig(use_class_profiles=False, min_frames=2, min_time_s=0.0))
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    tracker.update([obs((1.01, 0.0, 0.0), "can")], 0.2)
    # different labels → two targets
    all_targets = tracker.potential_targets + tracker.confirmed_targets
    assert len(all_targets) == 2


# --- F38 T03: size estimation ---

# Pinhole projection at 1m depth must yield width_m = bbox_px / fx (and analogously for height).
def test_estimate_size_m_basic():

    s = estimate_size_m(bbox_pixels=(50, 100), depth_m=1.0, fx=493.86, fy=493.87)
    assert abs(s.width_m - 50 / 493.86) < 1e-4
    assert abs(s.height_m - 100 / 493.87) < 1e-4
    assert s.depth_quality == 1.0


# Zero depth means no usable signal; depth_quality must be 0 and dimensions zeroed.
def test_estimate_size_m_zero_depth():

    s = estimate_size_m(bbox_pixels=(50, 100), depth_m=0.0, fx=493.86, fy=493.87)
    assert s.depth_quality == 0.0
    assert s.width_m == 0.0


# After 10 noisy observations the running mean must converge within 10% of the true size.
def test_size_running_mean_converges():

    tracker = WorldTracker(WorldTrackerConfig(min_frames=1, min_time_s=0.0))
    true_w, true_h = 0.07, 0.12
    import random
    random.seed(42)
    for i in range(10):
        noisy_w = true_w * (1 + random.uniform(-0.05, 0.05))
        noisy_h = true_h * (1 + random.uniform(-0.05, 0.05))
        fx, fy, depth = 493.86, 493.87, 1.0
        bbox = (noisy_w * fx / depth, noisy_h * fy / depth)
        size_est = estimate_size_m(bbox_pixels=bbox, depth_m=depth, fx=fx, fy=fy)
        tracker.update([(
            (1.0, 0.0, 0.0), "cup", i, None, size_est
        )], float(i) * 0.1)
    t = tracker.confirmed_targets[0]
    assert t.size_mean is not None
    assert abs(t.size_mean.width_m - true_w) < true_w * 0.1


# Alternating wide/narrow observations must yield positive variance (Welford accumulates correctly).
def test_size_variance_nonzero_with_spread():

    tracker = WorldTracker(WorldTrackerConfig(min_frames=1, min_time_s=0.0))
    # alternating values ensure variance > 0
    widths = [0.06, 0.08, 0.06, 0.08, 0.06, 0.08]
    for i, w in enumerate(widths):
        size_est = estimate_size_m((w * 493.86, 0.12 * 493.87), 1.0, 493.86, 493.87)
        tracker.update([((1.0, 0.0, 0.0), "cup", i, None, size_est)], float(i) * 0.1)
    t = tracker.confirmed_targets[0]
    assert t.size_n == len(widths)
    assert tracker.size_variance(t) > 0


# A target observed without any depth data must have size_mean=None (no spurious estimate).
def test_target_no_depth_has_no_size():
    tracker = WorldTracker(WorldTrackerConfig(min_frames=1, min_time_s=0.0))
    tracker.update([((1.0, 0.0, 0.0), "cup", 0, None, None)], 0.0)
    t = tracker.confirmed_targets[0]
    assert t.size_mean is None


# --- F38 T04: PASA composite cost ---

def pasa_cfg(**kwargs):
    defaults = dict(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
        min_frames=1, min_time_s=0.0,
        assoc_cost_distance_weight=1.0,
        assoc_cost_size_weight=1.0,
        assoc_cost_track_hint_weight=0.3,
    )
    defaults.update(kwargs)
    return WorldTrackerConfig(**defaults)


# An observation whose size matches the target's running mean must have lower cost than a mismatched one.
def test_pasa_cost_lower_with_matching_size():

    tracker = WorldTracker(pasa_cfg())
    # seed a confirmed target with a known size
    size_match = estimate_size_m((35, 60), 1.0, 493.86, 493.87)
    tracker.update([((1.0, 0.0, 0.0), "cup", 0, None, size_match)], 0.0)
    t = tracker.confirmed_targets[0]
    # cost with matching size
    cost_match = tracker.assoc.pasa_cost(Observation((1.0, 0.0, 0.0), "cup", 0, None, size_match), t)
    # cost with very different size (large can)
    size_mismatch = estimate_size_m((200, 400), 1.0, 493.86, 493.87)
    cost_mismatch = tracker.assoc.pasa_cost(Observation((1.0, 0.0, 0.0), "cup", 0, None, size_mismatch), t)
    assert cost_match < cost_mismatch


# Below size_confidence_floor the size term must be zeroed so bad depth cannot inflate cost.
def test_pasa_cost_size_zeroed_on_poor_depth():

    tracker = WorldTracker(pasa_cfg(size_confidence_floor=0.5))
    # seed confirmed target with a known size
    good_size = SizeEstimate(width_m=0.07, height_m=0.12, aspect_ratio=1.7, depth_quality=1.0)
    tracker.update([((1.0, 0.0, 0.0), "cup", 0, None, good_size)], 0.0)
    t = tracker.confirmed_targets[0]
    # poor depth obs with wildly different size
    poor_size = SizeEstimate(width_m=0.5, height_m=1.0, aspect_ratio=2.0, depth_quality=0.0)
    cost_poor = tracker.assoc.pasa_cost(Observation((1.0, 0.0, 0.0), "cup", 0, None, poor_size), t)
    good_size2 = SizeEstimate(width_m=0.5, height_m=1.0, aspect_ratio=2.0, depth_quality=1.0)
    cost_good = tracker.assoc.pasa_cost(Observation((1.0, 0.0, 0.0), "cup", 0, None, good_size2), t)
    # poor depth should produce lower cost (size term zeroed)
    assert cost_poor < cost_good


# Class gating: a can observation at the same position as a cup target must not associate.
def test_pasa_class_mismatch_no_association():
    tracker = WorldTracker(pasa_cfg())
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    tracker.update([obs((1.0, 0.0, 0.0), "can")], 0.1)
    all_targets = tracker.potential_targets + tracker.confirmed_targets
    assert len(all_targets) == 2


# Disabling PASA must fall back to the existing label+distance path with no regression.
def test_pasa_disabled_baseline_unchanged():
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=False, min_frames=2, min_time_s=0.0,
    ))
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 0.0)
    tracker.update([obs((1.01, 0.0, 0.0), "cup")], 0.2)
    assert len(tracker.confirmed_targets) == 1


# A matching track_id must reduce PASA cost by the configured hint weight.
def test_pasa_track_hint_reduces_cost():

    tracker = WorldTracker(pasa_cfg())
    size = SizeEstimate(width_m=0.07, height_m=0.12, aspect_ratio=1.7, depth_quality=1.0)
    tracker.update([((1.0, 0.0, 0.0), "cup", 0, 42, size)], 0.0)
    t = tracker.confirmed_targets[0]
    cost_with_hint = tracker.assoc.pasa_cost(Observation((1.0, 0.0, 0.0), "cup", 0, 42, size), t)
    cost_without_hint = tracker.assoc.pasa_cost(Observation((1.0, 0.0, 0.0), "cup", 0, None, size), t)
    assert cost_with_hint < cost_without_hint


# --- F38 T05: stationarity evidence ---

# A target that never moves must be classified stationary across its full history window.
def test_is_stationary_identical_positions():
    tracker = WorldTracker(WorldTrackerConfig(min_frames=1, min_time_s=0.0, stationary_window_s=5.0))
    for i in range(5):
        tracker.update([obs((1.0, 0.0, 0.0), "cup")], float(i) * 0.5)
    t = tracker.confirmed_targets[0]
    assert tracker.assoc.is_stationary(t) is True


# A target moving at 1 m/s must NOT be classified stationary (well above max_stationary_speed).
def test_is_stationary_fast_moving():
    tracker = WorldTracker(WorldTrackerConfig(min_frames=1, min_time_s=0.0, stationary_window_s=5.0))
    for i in range(5):
        tracker.update([obs((float(i) * 0.5, 0.0, 0.0), "cup")], float(i) * 0.5)
    t = tracker.confirmed_targets[0]
    assert tracker.assoc.is_stationary(t) is False


# stationarity_cost must return 0.0 for a confirmed-stationary target (no penalty added to cost).
def test_stationarity_term_zero_when_stationary():
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
        min_frames=1, min_time_s=0.0,
        assoc_cost_stationary_weight=1.0,
        stationary_window_s=5.0,
    ))
    for i in range(5):
        tracker.update([obs((1.0, 0.0, 0.0), "cup")], float(i) * 0.5)
    t = tracker.confirmed_targets[0]
    assert tracker.assoc.stationarity_cost(t) == 0.0


# Setting assoc_cost_stationary_weight=0 must make pasa_cost equal to the distance term alone.
def test_stationarity_weight_zero_no_contribution():
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
        min_frames=1, min_time_s=0.0,
        assoc_cost_stationary_weight=0.0,
    ))
    for i in range(5):
        tracker.update([obs((float(i), 0.0, 0.0), "cup")], float(i) * 0.1)
    t = tracker.confirmed_targets[0]
    cost = tracker.assoc.pasa_cost(Observation((5.0, 0.0, 0.0), "cup", 0, None, None), t)
    # stationarity weight=0 means only distance term contributes
    dist_norm = tracker.assoc.euclidean((5.0, 0.0, 0.0), t.xyz_world) / tracker.config.max_assoc_dist_m
    assert abs(cost - dist_norm) < 1e-6


# --- F38 T06: false-split recovery ---

def fsr_cfg(**kwargs):
    defaults = dict(
        min_frames=2, min_time_s=0.1,
        lost_timeout_s=1.0, remove_timeout_s=100.0,
        enable_false_split_recovery=True,
        false_split_lookback_s=5.0,
    )
    defaults.update(kwargs)
    return WorldTrackerConfig(**defaults)


# A target that went lost and reappears within lookback_s must recover its original ID.
def test_false_split_recovery_reuses_id():
    tracker = WorldTracker(fsr_cfg())
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    original_id = tracker.confirmed_targets[0].target_id
    tracker.update([], 3.0)  # goes lost
    assert tracker.confirmed_targets[0].is_lost is True
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 3.5)
    t = tracker.confirmed_targets[0]
    assert t.is_lost is False
    assert t.target_id == original_id


# After the original target is fully removed (past remove_timeout), reobservation creates a new target.
def test_false_split_expired_creates_new():
    # use remove_timeout_s=2.0 so original target is fully removed before reobservation
    tracker = WorldTracker(fsr_cfg(false_split_lookback_s=1.0, remove_timeout_s=2.0))
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    original_id = tracker.confirmed_targets[0].target_id
    tracker.update([], 20.0)  # past remove_timeout — target gone from confirmed list
    assert len(tracker.confirmed_targets) == 0
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 20.5)
    # no confirmed target to absorb → new potential
    assert len(tracker.potential_targets) == 1
    assert tracker.potential_targets[0].target_id != original_id


# Size incompatibility must block false-split recovery; baseline association handles the reactivation instead.
def test_false_split_incompatible_size_no_recovery():

    tracker = WorldTracker(WorldTrackerConfig(
        min_frames=1, min_time_s=0.0,
        lost_timeout_s=1.0, remove_timeout_s=100.0,
        enable_false_split_recovery=True,
        false_split_lookback_s=5.0,
        size_confidence_floor=0.5,
    ))
    small_size = SizeEstimate(width_m=0.03, height_m=0.05, aspect_ratio=1.7, depth_quality=1.0)
    tracker.update([((1.0, 0.0, 0.0), "cup", 0, None, small_size)], 0.0)
    original_id = tracker.confirmed_targets[0].target_id
    tracker.update([], 3.0)  # goes lost; original stays in confirmed list (not removed yet)
    assert tracker.confirmed_targets[0].is_lost is True
    # reobservation with incompatible size: recovery should skip; baseline association absorbs it
    large_size = SizeEstimate(width_m=0.3, height_m=0.5, aspect_ratio=1.7, depth_quality=1.0)
    tracker.update([((1.0, 0.0, 0.0), "cup", 1, None, large_size)], 3.5)
    # after baseline absorption the original target is reactivated, but with new size
    t = next(ct for ct in tracker.confirmed_targets if ct.target_id == original_id)
    assert t.is_lost is False  # reactivated via baseline (not false-split recovery)


# With recovery disabled, normal baseline association still re-activates lost confirmed targets.
def test_false_split_disabled_uses_normal_association():
    # without recovery, baseline association still re-activates the lost target
    tracker = WorldTracker(fsr_cfg(enable_false_split_recovery=False))
    feed(tracker, (1.0, 0.0, 0.0), "cup", n_frames=3, dt=0.2)
    original_id = tracker.confirmed_targets[0].target_id
    tracker.update([], 3.0)  # goes lost
    assert tracker.confirmed_targets[0].is_lost is True
    tracker.update([obs((1.0, 0.0, 0.0), "cup")], 3.5)
    # baseline re-activates via normal association and expire() clears is_lost
    t = tracker.confirmed_targets[0]
    assert t.is_lost is False
    assert t.target_id == original_id
    assert len(tracker.potential_targets) == 0


# --- F40-precursor: drift_tolerance_m structural radius ---

def drift_cfg(**kwargs):
    defaults = dict(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
        min_frames=1, min_time_s=0.0,
        lost_timeout_s=5.0, remove_timeout_s=30.0,
    )
    defaults.update(kwargs)
    return WorldTrackerConfig(**defaults)


# drift_tolerance_m (0.15m for can) must be used as confirmed radius instead of
# confirmed_assoc_mult * max_assoc_dist_m when a class profile defines it.
def test_drift_tolerance_replaces_confirmed_radius():
    # can profile has drift_tolerance_m=0.15; default confirmed_assoc_mult*max=4*0.3=1.2m
    # Two cans 0.3m apart: within 1.2m (old) but outside 0.15m (new) → must stay separate
    tracker = WorldTracker(drift_cfg())
    # confirm first can
    for i in range(3):
        tracker.update([obs((0.0, 0.0, 0.5), "can", i)], float(i) * 0.5)
    assert len(tracker.confirmed_targets) == 1
    # second can 0.3m away should NOT merge with confirmed first (0.3 > drift_tolerance_m=0.15)
    tracker.update([obs((0.3, 0.0, 0.5), "can")], 2.0)
    all_targets = tracker.potential_targets + tracker.confirmed_targets
    assert len(all_targets) == 2


# A re-observation within drift_tolerance_m must still associate with the confirmed target.
def test_drift_tolerance_within_radius_associates():
    tracker = WorldTracker(drift_cfg())
    for i in range(3):
        tracker.update([obs((0.0, 0.0, 0.5), "can", i)], float(i) * 0.5)
    assert len(tracker.confirmed_targets) == 1
    original_id = tracker.confirmed_targets[0].target_id
    # re-observation 0.10m away — within drift_tolerance_m=0.15 for can
    tracker.update([obs((0.10, 0.0, 0.5), "can")], 2.0)
    assert len(tracker.confirmed_targets) == 1
    assert tracker.confirmed_targets[0].target_id == original_id


# Classes without a class profile must fall back to confirmed_assoc_mult * max_assoc_dist_m.
def test_drift_tolerance_absent_falls_back_to_mult():
    # use_class_profiles=False → no drift_tolerance_m lookup → baseline wide radius
    tracker = WorldTracker(WorldTrackerConfig(
        use_class_profiles=False,
        min_frames=1, min_time_s=0.0,
        max_assoc_dist_m=0.3, confirmed_assoc_mult=4.0,
        lost_timeout_s=5.0, remove_timeout_s=30.0,
    ))
    for i in range(3):
        tracker.update([obs((0.0, 0.0, 0.5), "can", i)], float(i) * 0.5)
    assert len(tracker.confirmed_targets) == 1
    # 0.3m < 4.0*0.3=1.2m → should associate (wide radius still applies)
    tracker.update([obs((0.3, 0.0, 0.5), "can")], 2.0)
    assert len(tracker.confirmed_targets) == 1


# --- Bug fixes: two-cups-1.2m-apart scenario ---

def two_cup_tracker():
    """Tracker that confirms after 2 frames; default confirmed_assoc_mult=2.0 (0.6m radius)."""
    return WorldTracker(fast_cfg(max_assoc_dist_m=0.3))


def confirm_cup(tracker, xyz, start_t=0.0):
    """Feed 2 observations to confirm a cup at xyz."""
    for i in range(2):
        tracker.update([obs(xyz, "cup", i)], start_t + i * 0.2)


# Bug 1 regression: two cups 1.2 m apart must remain separate confirmed targets.
def test_two_cups_1_2m_apart_stay_separate():
    tracker = two_cup_tracker()
    cup_a = (0.0, 0.0, 1.0)
    cup_b = (1.2, 0.0, 1.0)
    confirm_cup(tracker, cup_a, start_t=0.0)
    confirm_cup(tracker, cup_b, start_t=1.0)
    assert len(tracker.confirmed_targets) == 2
    ids = {t.target_id for t in tracker.confirmed_targets}
    assert len(ids) == 2


# Bug 1 regression: with the old default (mult=4.0) this would have collapsed.
def test_two_cups_just_outside_confirmed_radius_stay_separate():
    # confirmed radius = 2.0 * 0.3 = 0.6 m; cups at 0.7 m apart must be two targets.
    tracker = two_cup_tracker()
    cup_a = (0.0, 0.0, 1.0)
    cup_b = (0.7, 0.0, 1.0)
    confirm_cup(tracker, cup_a, start_t=0.0)
    confirm_cup(tracker, cup_b, start_t=1.0)
    assert len(tracker.confirmed_targets) == 2


# Bug 2 regression: when an observation falls within the confirmed radius of two targets,
# the nearer one must win — not the one that appears first in the confirmed list.
def test_nearest_confirmed_wins_not_first():
    tracker = two_cup_tracker()
    # Place cups 1.0 m apart so each can be confirmed independently (> 0.6 m radius).
    cup_a = (0.0, 0.0, 1.0)
    cup_b = (1.0, 0.0, 1.0)
    confirm_cup(tracker, cup_a, start_t=0.0)
    confirm_cup(tracker, cup_b, start_t=1.0)
    assert len(tracker.confirmed_targets) == 2

    # Observation at x=0.55: dist to cup_a=0.55 m, dist to cup_b=0.45 m — both within 0.6 m.
    # Nearest is cup_b; old first-wins code would assign to cup_a (confirmed first).
    near_b = (0.55, 0.0, 1.0)
    tracker.update([obs(near_b, "cup")], 2.0)
    cup_b_target = min(tracker.confirmed_targets, key=lambda t: tracker.assoc.euclidean(t.xyz_world, cup_b))
    assert cup_b_target.observation_count > 2  # cup_b absorbed the observation


# Sanity: observation within the new tighter radius still re-associates correctly.
def test_observation_within_new_confirmed_radius_associates():
    tracker = two_cup_tracker()
    cup_a = (0.0, 0.0, 1.0)
    confirm_cup(tracker, cup_a, start_t=0.0)
    # 0.5 m < 0.6 m confirmed radius → must re-associate, not spawn new target
    tracker.update([obs((0.5, 0.0, 1.0), "cup")], 2.0)
    assert len(tracker.confirmed_targets) == 1


# --- position_variance and converged (F48 T02) ---

def confirmed_target_at(xyz, n_obs=10, dt=0.5):
    """Return a ConfirmedTarget that has received n_obs identical observations at xyz."""
    tracker = WorldTracker(fast_cfg(convergence_min_obs=5, convergence_variance_m2=0.0025))
    for i in range(n_obs):
        tracker.update([obs(xyz, "cup", i)], i * dt)
    targets = tracker.confirmed_targets
    assert targets, "no confirmed target produced"
    return tracker, targets[0]


def test_position_variance_defaults_zero():
    ct = ConfirmedTarget(
        target_id=1, label="cup", canonical_class="cup",
        xyz_world=(1.0, 0.0, 1.0), observation_count=0,
        confirmed_at_s=0.0, last_seen_s=0.0,
    )
    assert ct.position_variance == 0.0
    assert ct.is_converged is False


def test_position_variance_decreases_with_stable_observations():
    tracker, t = confirmed_target_at((1.0, 0.0, 1.0), n_obs=20)
    # After 20 identical observations variance should be near zero
    assert t.position_variance < 0.0025


def test_converged_true_after_enough_stable_observations():
    tracker, t = confirmed_target_at((1.0, 0.0, 1.0), n_obs=20)
    assert t.is_converged is True


def test_converged_false_with_noisy_observations():
    tracker = WorldTracker(fast_cfg(convergence_min_obs=5, convergence_variance_m2=0.0025))
    import math
    for i in range(30):
        # large position jitter: ±0.5 m
        noise = 0.5 * math.sin(i)
        tracker.update([obs((1.0 + noise, 0.0, 1.0), "cup", i)], i * 0.5)
    targets = tracker.confirmed_targets
    assert targets
    assert targets[0].is_converged is False


def test_converged_false_before_min_obs_even_if_variance_low():
    # convergence_min_obs=20, but we only feed 10 post-promotion observations
    tracker = WorldTracker(fast_cfg(convergence_min_obs=20, convergence_variance_m2=0.0025))
    for i in range(12):
        tracker.update([obs((1.0, 0.0, 1.0), "cup", i)], i * 0.5)
    targets = tracker.confirmed_targets
    assert targets
    t = targets[0]
    # pos_n may be < 20 so converged must be False regardless of low variance
    assert t.is_converged is False


def test_position_variance_nonzero_then_stabilises():
    tracker = WorldTracker(fast_cfg(convergence_min_obs=5, convergence_variance_m2=0.0025))
    # First 10 obs noisy, next 20 stable
    import math
    for i in range(10):
        tracker.update([obs((1.0 + 0.3 * math.sin(i), 0.0, 1.0), "cup", i)], i * 0.5)
    variance_after_noisy = None
    targets = tracker.confirmed_targets
    if targets:
        variance_after_noisy = targets[0].position_variance

    for i in range(10, 60):
        tracker.update([obs((1.0, 0.0, 1.0), "cup", i)], i * 0.5)
    targets = tracker.confirmed_targets
    assert targets
    if variance_after_noisy is not None:
        # variance should have dropped as observations stabilise
        assert targets[0].position_variance <= variance_after_noisy + 1e-6


# --- F50: update_embedding, to_json, from_json, combined_sim ---

def make_confirmed(target_id=1, label="cup", xyz=(1.0, 0.0, 0.5)):
    return ConfirmedTarget(
        target_id=target_id, label=label, canonical_class=label,
        xyz_world=xyz, observation_count=5,
        confirmed_at_s=0.0, last_seen_s=1.0,
    )


def test_update_embedding_first_call():
    tracker = WorldTracker(cfg())
    t = make_confirmed()
    emb = np.ones(576, dtype=np.float32)
    tracker.update_embedding(t, emb)
    assert t.embedding is not None
    assert t.embedding.shape == (576,)
    assert t.embedding_count == 1


def test_update_embedding_running_average():
    tracker = WorldTracker(cfg())
    t = make_confirmed()
    emb_a = np.zeros(576, dtype=np.float32)
    emb_b = np.ones(576, dtype=np.float32) * 2.0
    tracker.update_embedding(t, emb_a)
    tracker.update_embedding(t, emb_b)
    assert t.embedding_count == 2
    np.testing.assert_allclose(t.embedding, np.ones(576) * 1.0, atol=1e-5)


def test_to_json_round_trip_no_embedding():
    tracker = WorldTracker(fast_cfg())
    for i in range(3):
        tracker.update([obs((1.0, 0.0, 0.5), "cup", i)], float(i) * 0.5)
    assert tracker.confirmed_targets
    s = tracker.to_json()
    t2 = WorldTracker.from_json(s, fast_cfg())
    assert len(t2.confirmed) == 1
    ct = t2.confirmed[0]
    assert ct.label == "cup"
    assert ct.observation_count == 3
    assert ct.embedding is None


def test_to_json_round_trip_with_embedding():
    tracker = WorldTracker(fast_cfg())
    for i in range(3):
        tracker.update([obs((1.0, 0.0, 0.5), "cup", i)], float(i) * 0.5)
    ct = tracker.confirmed[0]
    emb = np.linspace(0, 1, 576, dtype=np.float32)
    tracker.update_embedding(ct, emb)
    s = tracker.to_json()
    t2 = WorldTracker.from_json(s, fast_cfg())
    ct2 = t2.confirmed[0]
    assert ct2.embedding is not None
    np.testing.assert_allclose(ct2.embedding, emb, atol=1e-5)


def test_from_json_next_id_past_max():
    tracker = WorldTracker(fast_cfg())
    for i in range(3):
        tracker.update([obs((1.0, 0.0, 0.5), "cup", i)], float(i) * 0.5)
    assert tracker.confirmed_targets
    s = tracker.to_json()
    t2 = WorldTracker.from_json(s, fast_cfg())
    max_id = max(ct.target_id for ct in t2.confirmed)
    assert t2.next_id > max_id


def test_combined_sim_position_only_no_embedding():
    tracker = WorldTracker(cfg(max_assoc_dist_m=1.0))
    score = tracker.combined_sim(((0.0, 0.0, 0.0), None), ((0.5, 0.0, 0.0), None))
    assert 0.0 < score < 1.0


def test_combined_sim_identical_position_no_embedding():
    tracker = WorldTracker(cfg())
    score = tracker.combined_sim(((1.0, 0.0, 0.0), None), ((1.0, 0.0, 0.0), None))
    assert score == pytest.approx(1.0)


def test_position_ema_alpha_zero_uses_running_mean():
    # Regression: default was accidentally changed to 0.1; 0.0 must use pure running mean.
    tracker = WorldTracker(cfg(position_ema_alpha=0.0))
    obs1 = obs((0.0, 0.0, 1.0), "cup", 1)
    obs2 = obs((0.0, 0.0, 3.0), "cup", 2)
    # Two equal-weight observations → mean z = 2.0
    result = tracker.running_mean((0.0, 0.0, 1.0), 1, (0.0, 0.0, 3.0))
    assert result[2] == pytest.approx(2.0)


def test_position_ema_alpha_nonzero_applies_ema():
    tracker = WorldTracker(cfg(position_ema_alpha=0.5))
    # EMA: 0.5 * 3.0 + 0.5 * 1.0 = 2.0 same here, but check alpha path runs
    result = tracker.running_mean((0.0, 0.0, 1.0), 1, (0.0, 0.0, 3.0))
    assert result[2] == pytest.approx(2.0)
    # Different weights: alpha=0.5, current=0, new=4 → 2.0
    result2 = tracker.running_mean((0.0, 0.0, 0.0), 1, (0.0, 0.0, 4.0))
    assert result2[2] == pytest.approx(2.0)


def test_combined_sim_with_embeddings_same():
    tracker = WorldTracker(cfg(max_assoc_dist_m=1.0))
    emb = np.ones(576, dtype=np.float32)
    score = tracker.combined_sim(((0.0, 0.0, 0.0), emb), ((0.0, 0.0, 0.0), emb))
    assert score > 0.99
