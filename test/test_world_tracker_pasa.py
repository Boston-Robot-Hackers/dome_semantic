#!/usr/bin/env python3
# test_world_tracker_pasa — F38 acceptance criteria tests (pure Python, no ROS)
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import pytest
from dome_semantic.world_tracker import WorldTracker, WorldTrackerConfig
from dome_semantic.size_estimate import SizeEstimate, estimate_size_m


def pasa_cfg(**kwargs):
    defaults = dict(
        use_class_profiles=True,
        class_profile_path="examples/configs/class_profiles.yaml",
        min_frames=3, min_time_s=0.5,
        lost_timeout_s=2.0, remove_timeout_s=30.0,
        assoc_cost_distance_weight=1.0,
        assoc_cost_size_weight=0.5,
        assoc_cost_track_hint_weight=0.3,
        enable_false_split_recovery=True,
        false_split_lookback_s=5.0,
    )
    defaults.update(kwargs)
    return WorldTrackerConfig(**defaults)


def obs(xyz, label, frame=0, track_id=None, size_est=None):
    return (xyz, label, frame, track_id, size_est)


def feed(tracker, xyz, label, n_frames, start_t=0.0, dt=0.3, size_est=None):
    for i in range(n_frames):
        tracker.update([obs(xyz, label, i, None, size_est)], start_t + i * dt)


# --- AC1: Repeated passes over the same scene converge to true count ---

# Repeated re-observation of the same static scene must not inflate the confirmed count.
def test_repeated_passes_count_converges():
    """Two passes over 2 cups at known positions; confirmed count stays at 2."""
    tracker = WorldTracker(pasa_cfg())
    cup_size = estimate_size_m((35, 65), 1.0, 493.86, 493.87)

    # pass 1: see both cups
    for i in range(5):
        tracker.update([
            obs((1.0, 0.0, 0.5), "cup", i, None, cup_size),
            obs((2.0, 0.0, 0.5), "cup", i, None, cup_size),
        ], float(i) * 0.3)

    assert len(tracker.confirmed_targets) == 2

    # pass 2: same cups again (simulates robot returning)
    for i in range(5):
        tracker.update([
            obs((1.0, 0.0, 0.5), "cup", i + 10, None, cup_size),
            obs((2.0, 0.0, 0.5), "cup", i + 10, None, cup_size),
        ], 5.0 + float(i) * 0.3)

    confirmed = [t for t in tracker.confirmed_targets if not t.is_lost]
    assert len(confirmed) == 2


# --- AC2: Re-entry after occlusion reuses prior target ID ---

# Brief occlusion followed by re-observation should recover the original target ID, not create a new one.
def test_reentry_after_occlusion_reuses_id():
    """Target goes out of view briefly; on return the same ID is recovered."""
    tracker = WorldTracker(pasa_cfg(
        enable_false_split_recovery=True,
        false_split_lookback_s=5.0,
        lost_timeout_s=1.0,
        remove_timeout_s=30.0,
    ))
    cup_size = estimate_size_m((35, 65), 1.0, 493.86, 493.87)
    feed(tracker, (1.0, 0.0, 0.5), "cup", n_frames=5, dt=0.3, size_est=cup_size)
    original_id = tracker.confirmed_targets[0].target_id

    # brief absence (within lookback)
    tracker.update([], 3.0)
    assert tracker.confirmed_targets[0].is_lost is True

    # reappears with same class+size
    tracker.update([obs((1.0, 0.0, 0.5), "cup", 99, None, cup_size)], 3.5)
    recovered = [t for t in tracker.confirmed_targets if not t.is_lost]
    assert len(recovered) == 1
    assert recovered[0].target_id == original_id


# --- AC3: Nearby different subclasses do not merge ---

# Class gating must prevent a cup and a can at the same location from merging into one target.
def test_nearby_different_subclasses_not_merged():
    """A cup and a can at the same position stay separate targets."""
    tracker = WorldTracker(pasa_cfg())
    cup_size = estimate_size_m((35, 65), 1.0, 493.86, 493.87)
    can_size = estimate_size_m((30, 55), 1.0, 493.86, 493.87)

    for i in range(5):
        tracker.update([
            obs((1.0, 0.0, 0.5), "cup", i, None, cup_size),
            obs((1.0, 0.0, 0.5), "can", i, None, can_size),
        ], float(i) * 0.3)

    confirmed = tracker.confirmed_targets
    cup_targets = [t for t in confirmed if t.canonical_class == "coffee cup"]
    can_targets = [t for t in confirmed if t.canonical_class == "soda can"]
    assert len(cup_targets) >= 1
    assert len(can_targets) >= 1
    assert all(c.target_id != a.target_id for c in cup_targets for a in can_targets)


# --- AC4: Degradation to baseline when size signal is weak ---

# When depth is unavailable (quality=0), size term must be zeroed so behavior matches the baseline.
def test_degrades_gracefully_with_poor_depth():
    """When depth_quality=0, size term is zeroed and association uses distance only."""
    tracker_pasa = WorldTracker(pasa_cfg(assoc_cost_size_weight=1.0))
    tracker_base = WorldTracker(WorldTrackerConfig(
        min_frames=3, min_time_s=0.5,
        lost_timeout_s=2.0, remove_timeout_s=30.0,
    ))

    poor_size = SizeEstimate(width_m=99.0, height_m=99.0, aspect_ratio=1.0, depth_quality=0.0)

    for i in range(5):
        tracker_pasa.update([obs((1.0, 0.0, 0.5), "cup", i, None, poor_size)], float(i) * 0.3)
        tracker_base.update([(((1.0, 0.0, 0.5), "cup", i, None))], float(i) * 0.3)

    pasa_confirmed = [t for t in tracker_pasa.confirmed_targets if not t.is_lost]
    base_confirmed = [t for t in tracker_base.confirmed_targets if not t.is_lost]
    # poor depth → size term zeroed → same result as baseline
    assert len(pasa_confirmed) == len(base_confirmed)


# --- AC5: use_class_profiles=False is identical to pre-F38 behavior ---

# use_class_profiles=False must produce identical association results to pre-F38 WorldTracker.
def test_profiles_disabled_identical_to_baseline():
    """Disabling PASA gives exactly the same association result as the old path."""
    xyz = (1.0, 0.0, 0.5)
    label = "cup"

    tracker_new = WorldTracker(WorldTrackerConfig(
        use_class_profiles=False, min_frames=3, min_time_s=0.5,
        lost_timeout_s=2.0, remove_timeout_s=30.0,
    ))
    tracker_old = WorldTracker(WorldTrackerConfig(
        min_frames=3, min_time_s=0.5,
        lost_timeout_s=2.0, remove_timeout_s=30.0,
    ))

    for i in range(5):
        t = float(i) * 0.3
        tracker_new.update([obs(xyz, label, i)], t)
        tracker_old.update([(xyz, label, i, None)], t)

    assert len(tracker_new.confirmed_targets) == len(tracker_old.confirmed_targets)
    assert tracker_new.confirmed_targets[0].label == tracker_old.confirmed_targets[0].label
