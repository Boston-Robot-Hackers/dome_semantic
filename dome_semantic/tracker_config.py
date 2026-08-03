#!/usr/bin/env python3
# tracker_config — configuration for WorldTracker
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from pydantic import BaseModel


class WorldTrackerConfig(BaseModel):
    # How far apart (metres) two observations can be and still associate to the same potential target.
    # Set to roughly the expected odometry drift per observation interval.
    max_assoc_dist_m: float = 0.3

    # Confirmed targets absorb observations at this multiple of max_assoc_dist_m.
    # Higher = more tolerant of drift when re-observing a known object.
    # 2x (0.6 m at default max_assoc_dist_m) tolerates typical odometry drift while
    # keeping two objects 1.2 m apart from collapsing into one target.
    confirmed_assoc_mult: float = 2.0

    # Minimum number of frames before a potential is promoted to confirmed.
    # Higher = fewer false positives from transient detections.
    min_frames: int = 5

    # Minimum elapsed seconds across those frames before promotion.
    # Prevents a burst of detections in a single second from instant confirmation.
    min_time_s: float = 1.0

    # Seconds without observation before a confirmed target is marked lost.
    lost_timeout_s: float = 5.0

    # Seconds after going lost before a confirmed target is removed from memory entirely.
    remove_timeout_s: float = 30.0

    # If True, a new potential is only promoted when at least one confirmed target is
    # co-observed in the same frame (the "anchor" requirement). Prevents spurious
    # confirmations far from known landmarks. Use when odometry drift is a concern.
    require_anchor: bool = False

    # --- PASA params (F38) — all disabled by default ---

    # Master switch for F38 PASA association. False = pre-F38 label+distance behavior.
    use_class_profiles: bool = False

    # Absolute path to a YAML file containing TargetClassProfile entries (one per class).
    # Only used when use_class_profiles=True and class_profiles_inline is None.
    class_profile_path: str | None = None

    # Inline class profiles parsed directly from the main config YAML.
    # When set, takes precedence over class_profile_path.
    class_profiles_inline: list | None = None

    # Weight for the Euclidean distance term in the composite PASA cost.
    # Increase relative to size/stationary to rely more on position alone.
    assoc_cost_distance_weight: float = 1.0

    # Weight for the size-consistency term. Set to 0 to disable (default).
    # Start at 0; tune upward once depth quality is verified on real hardware.
    assoc_cost_size_weight: float = 0.0

    # Weight for the stationarity prior term. Set to 0 to disable (default).
    # When > 0, known-stationary classes (per their class profile) get a cost bonus —
    # rewarding association to targets that a priori shouldn't have moved.
    # This is a CLASS PRIOR, not empirical motion measurement.
    assoc_cost_stationary_weight: float = 0.0

    # Soft bonus subtracted from cost when an observation's track_id matches a known
    # track_id on the candidate target. Keeps camera-frame track continuity as a hint.
    assoc_cost_track_hint_weight: float = 0.3

    # Time window (seconds) over which position history is kept for stationarity checks.
    # Observations older than this are discarded from the per-target history buffer.
    stationary_window_s: float = 2.0

    # Minimum depth quality (0–1) required to use the size term in PASA cost.
    # Below this floor, size_weight is zeroed automatically so noisy depth doesn't skew association.
    size_confidence_floor: float = 0.5

    # Enable false-split recovery: if a confirmed target goes lost then reappears nearby
    # within false_split_lookback_s, recover its original ID instead of creating a new one.
    enable_false_split_recovery: bool = False

    # How far back (seconds) to search for a recently-lost confirmed target on re-entry.
    # Should be longer than lost_timeout_s to be meaningful.
    false_split_lookback_s: float = 5.0

    # Camera intrinsics at the operating resolution (default: 512×512 measured values).
    # Used by estimate_size_m() to project bbox pixels to real-world metres.
    # fx and fy are the focal lengths in pixels along x and y axes.
    fx: float = 493.86
    fy: float = 493.87

    # EMA alpha for position updates. 0.0 = pure running mean (old behavior).
    # 0.1 = 10% weight to each new observation; keeps position responsive as obs count grows.
    # Tune upward for faster tracking, downward for more stability.
    position_ema_alpha: float = 0.0

    # Welford position variance threshold (m²) below which a confirmed target is considered
    # converged. 0.0025 m² = ±5 cm std dev.
    convergence_variance_m2: float = 0.0025

    # Minimum number of post-promotion position updates before converged can be True.
    convergence_min_obs: int = 5
