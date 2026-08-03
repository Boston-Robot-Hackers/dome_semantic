#!/usr/bin/env python3
# association — PASA and baseline target matching algorithms
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from dome_semantic.size_estimate import SizeEstimate
from dome_semantic.targets import ConfirmedTarget, Observation, PotentialTarget
from dome_semantic.tracker_config import WorldTrackerConfig


class TargetAssociator:
    """Pure matching logic: given an observation, find the best candidate target.

    No state mutations here — all methods return a match or None.
    WorldTracker owns confirmed/potentials lists and calls update methods itself.
    """

    def __init__(self, config: WorldTrackerConfig, profiles: dict):
        self.config = config
        self.profiles = profiles

    def find_match(self, obs: Observation, confirmed: list, potentials: list):
        if self.config.use_class_profiles:
            return self.find_match_pasa(obs, confirmed, potentials)
        return self.find_match_baseline(obs, confirmed, potentials)

    def find_match_baseline(self, obs: Observation, confirmed: list, potentials: list):
        strict = self.config.max_assoc_dist_m
        confirmed_dist = strict * self.config.confirmed_assoc_mult
        best, best_dist = None, float("inf")
        for t in confirmed:
            if t.canonical_class != obs.label:
                continue
            d = self.euclidean(obs.xyz, t.xyz_world)
            if d <= confirmed_dist and d < best_dist:
                best, best_dist = t, d
        if best is not None:
            return best
        best, best_dist = None, float("inf")
        for t in potentials:
            if t.canonical_class != obs.label:
                continue
            d = self.euclidean(obs.xyz, t.xyz_world)
            if obs.track_id is not None and obs.track_id in t.track_ids and d <= strict * 2 and d < best_dist:
                best, best_dist = t, d
            elif d <= strict and d < best_dist:
                best, best_dist = t, d
        return best

    def find_match_pasa(self, obs: Observation, confirmed: list, potentials: list):
        """When a class profile specifies drift_tolerance_m, confirmed radius tightens to that value.
        This prevents two cups 0.5 m apart from merging when odometry drift would make them appear
        within the default confirmed_assoc_mult radius.
        """
        strict = self.config.max_assoc_dist_m
        profile = self.profiles.get(obs.label)
        if profile is not None and profile.drift_tolerance_m is not None:
            # Known-stationary class: tighten confirmed radius to expected sensor noise only.
            confirmed_dist = profile.drift_tolerance_m
        else:
            confirmed_dist = strict * self.config.confirmed_assoc_mult
        best_c, best_c_cost = None, float("inf")
        for t in confirmed:
            if t.canonical_class != obs.label:
                continue
            if self.euclidean(obs.xyz, t.xyz_world) > confirmed_dist:
                continue
            cost = self.pasa_cost(obs, t)
            if cost < best_c_cost:
                best_c_cost, best_c = cost, t
        if best_c is not None:
            return best_c
        best_p, best_p_cost = None, float("inf")
        for t in potentials:
            if t.canonical_class != obs.label:
                continue
            d = self.euclidean(obs.xyz, t.xyz_world)
            if d > strict:
                if not (obs.track_id is not None and obs.track_id in t.track_ids and d <= strict * 2):
                    continue
            cost = self.pasa_cost(obs, t)
            if cost < best_p_cost:
                best_p_cost, best_p = cost, t
        return best_p

    def find_false_split(self, obs: Observation, confirmed: list, timestamp_s: float):
        """Return the lost confirmed target this observation should recover, or None."""
        for t in confirmed:
            if not t.is_lost:
                continue
            if t.canonical_class != obs.label:
                continue
            if timestamp_s - t.last_seen_s > self.config.false_split_lookback_s:
                continue
            if self.euclidean(obs.xyz, t.xyz_world) > self.config.max_assoc_dist_m:
                continue
            if self.size_check_fails(obs.size_est, t):
                continue
            return t
        return None

    def pasa_cost(self, obs: Observation, target) -> float:
        components = self.pasa_cost_components(obs, target)
        cfg = self.config
        return (
            cfg.assoc_cost_distance_weight * components["dist_norm"]
            + cfg.assoc_cost_size_weight * components["size_norm"]
            + cfg.assoc_cost_stationary_weight * components["stat"]
            - cfg.assoc_cost_track_hint_weight * components["hint"]
        )

    def pasa_cost_breakdown(self, obs: Observation, target) -> dict:
        cfg = self.config
        c = self.pasa_cost_components(obs, target)
        return {
            "distance": round(cfg.assoc_cost_distance_weight * c["dist_norm"], 4),
            "size": round(cfg.assoc_cost_size_weight * c["size_norm"], 4),
            "stationary": round(cfg.assoc_cost_stationary_weight * c["stat"], 4),
            "track_hint": round(-cfg.assoc_cost_track_hint_weight * c["hint"], 4),
        }

    def pasa_cost_components(self, obs: Observation, target) -> dict:
        cfg = self.config
        dist = self.euclidean(obs.xyz, target.xyz_world)
        dist_norm = dist / max(cfg.max_assoc_dist_m, 1e-6)

        size_norm = 0.0
        if cfg.assoc_cost_size_weight > 0 and obs.size_est is not None and target.size_mean is not None:
            if obs.size_est.depth_quality >= cfg.size_confidence_floor:
                size_dev = abs(obs.size_est.width_m - target.size_mean.width_m)
                profile = self.profiles.get(target.canonical_class)
                if profile is not None:
                    diam_range = profile.diameter_range_m[1] - profile.diameter_range_m[0]
                    size_norm = size_dev / max(diam_range, 1e-4)
                else:
                    size_norm = size_dev / max(target.size_mean.width_m, 1e-4)

        stat = self.stationarity_cost(target) if cfg.assoc_cost_stationary_weight > 0 else 0.0
        hint = 1.0 if obs.track_id is not None and obs.track_id in getattr(target, "track_ids", set()) else 0.0

        return {"dist_norm": dist_norm, "size_norm": size_norm, "stat": stat, "hint": hint}

    def size_check_fails(self, size_est: "SizeEstimate | None", target: ConfirmedTarget) -> bool:
        if size_est is None or target.size_mean is None:
            return False
        if size_est.depth_quality < self.config.size_confidence_floor:
            return False
        size_dev = abs(size_est.width_m - target.size_mean.width_m)
        return size_dev > target.size_mean.width_m * 0.5

    def stationarity_cost(self, target) -> float:
        if len(target.position_history) < 2:
            return 0.5  # no evidence yet — neutral
        return 0.0 if self.is_stationary(target) else 1.0

    def is_stationary(self, target) -> bool:
        history = target.position_history
        if len(history) < 2:
            return False
        profile = self.profiles.get(target.canonical_class)
        speed_limit = profile.max_stationary_speed_mps if profile else 0.02
        for i in range(1, len(history)):
            t0, xyz0 = history[i - 1]
            t1, xyz1 = history[i]
            dt = t1 - t0
            if dt <= 0:
                continue
            if self.euclidean(xyz0, xyz1) / dt > speed_limit:
                return False
        return True

    def euclidean(self, a, b) -> float:
        return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5
