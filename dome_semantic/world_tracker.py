#!/usr/bin/env python3
# world_tracker — world-frame object confirmation state machine
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import base64
import json

import numpy as np

from dome_semantic.association import TargetAssociator
from dome_semantic.class_profiles import build_label_map, load_class_profiles, parse_class_profiles
from dome_semantic.embedding_similarity import cosine_sim
from dome_semantic.size_estimate import SizeEstimate
from dome_semantic.targets import ConfirmedTarget, Observation, PotentialTarget
from dome_semantic.tracker_config import WorldTrackerConfig


class WorldTracker:
    """Two-tier state machine: PotentialTarget accumulates evidence, ConfirmedTarget holds
    reliable estimates. Confirmed targets survive visibility gaps and persist across sessions
    via to_json/from_json. Association is label-constrained so cups never absorb cans.
    """

    def __init__(self, config: WorldTrackerConfig):
        self.config = config
        self.potentials: list[PotentialTarget] = []
        self.confirmed: list[ConfirmedTarget] = []
        self.next_id: int = 1
        self.has_confirmed: bool = False
        self.profiles: dict = {}
        self.label_map: dict = {}
        self.assoc_log: list[dict] = []
        self.load_profiles()
        self.assoc = TargetAssociator(config, self.profiles)

    def load_profiles(self) -> None:
        if not self.config.use_class_profiles:
            return
        if self.config.class_profiles_inline is not None:
            self.profiles = parse_class_profiles(self.config.class_profiles_inline)
        elif self.config.class_profile_path:
            self.profiles = load_class_profiles(self.config.class_profile_path)
        self.label_map = build_label_map(self.profiles)

    def update(self, observations: list, timestamp_s: float) -> list[ConfirmedTarget]:
        self.assoc_log = []
        remaining = self.recover_false_splits(observations, timestamp_s)
        self.associate(remaining, timestamp_s)
        self.promote(remaining, timestamp_s)
        self.expire(timestamp_s)
        return [t for t in self.confirmed if not t.is_lost]

    def recover_false_splits(self, observations: list, timestamp_s: float) -> list:
        """Re-attach observations to targets that briefly disappeared and re-entered the frame.

        A false split happens when a confirmed target goes lost (camera pans away, occlusion)
        and then re-appears close to its last known position. Without this step, re-entry
        creates a new potential rather than resuming the original track — producing duplicate
        entries for the same physical object.

        Returns remaining observations not consumed by recovery.
        """
        if not self.config.enable_false_split_recovery:
            return observations
        recovered_ids = set()
        for raw in observations:
            obs = self.to_obs(raw)
            canonical = self.label_map.get(obs.label, obs.label)
            resolved = Observation(obs.xyz, canonical, obs.frame_num, obs.track_id, obs.size_est)
            t = self.assoc.find_false_split(resolved, self.confirmed, timestamp_s)
            if t is None:
                continue
            t.is_lost = False
            t.xyz_world = self.running_mean(t.xyz_world, t.observation_count, obs.xyz)
            t.observation_count += 1
            t.last_seen_s = timestamp_s
            self.welford_update_position(t, obs.xyz)
            t.position_history.append((timestamp_s, obs.xyz))
            self.trim_pos_history(t)
            recovered_ids.add(id(raw))
            if self.config.use_class_profiles:
                self.assoc_log.append({
                    "xyz": list(obs.xyz), "label": obs.label,
                    "outcome": "recovered", "target_id": t.target_id,
                })
        return [o for o in observations if id(o) not in recovered_ids]

    @property
    def confirmed_targets(self) -> list[ConfirmedTarget]:
        return list(self.confirmed)

    @property
    def potential_targets(self) -> list[PotentialTarget]:
        return list(self.potentials)

    def query(self, label: str, n: int = 0) -> "ConfirmedTarget | None":
        matches = sorted(
            [t for t in self.confirmed if t.label == label and not t.is_lost],
            key=lambda t: t.confirmed_at_s,
        )
        return matches[n] if n < len(matches) else None

    def associate(self, observations: list, timestamp_s: float) -> None:
        for raw in observations:
            obs = self.to_obs(raw)
            canonical = self.label_map.get(obs.label, obs.label)
            resolved = Observation(obs.xyz, canonical, obs.frame_num, obs.track_id, obs.size_est)
            target = self.assoc.find_match(resolved, self.confirmed, self.potentials)
            if self.config.use_class_profiles:
                entry: dict = {"xyz": list(obs.xyz), "label": obs.label}
                if target is None:
                    entry["outcome"] = "new"
                else:
                    entry["outcome"] = "matched"
                    entry["target_id"] = target.target_id
                    entry["costs"] = self.assoc.pasa_cost_breakdown(resolved, target)
                self.assoc_log.append(entry)
            if target is None:
                self.create_potential(obs.xyz, obs.label, canonical, timestamp_s, obs.track_id, obs.size_est)
            else:
                self.update_target(target, obs.xyz, timestamp_s, obs.track_id, obs.size_est)

    def to_obs(self, raw) -> Observation:
        if isinstance(raw, Observation):
            return raw
        xyz, label, frame_num, *rest = raw
        track_id = rest[0] if len(rest) > 0 else None
        size_est = rest[1] if len(rest) > 1 else None
        return Observation(xyz, label, frame_num, track_id, size_est)

    def create_potential(self, xyz, label, canonical, timestamp_s, track_id, size_est) -> None:
        t = PotentialTarget(
            target_id=self.next_id,
            label=label,
            canonical_class=canonical,
            xyz_world=xyz,
            observation_count=1,
            first_seen_s=timestamp_s,
            last_seen_s=timestamp_s,
            track_ids={track_id} if track_id is not None else set(),
        )
        if size_est is not None:
            t.size_mean = size_est
            t.size_n = 1
        t.position_history.append((timestamp_s, xyz))
        self.potentials.append(t)
        self.next_id += 1

    def update_target(self, target, xyz, timestamp_s, track_id, size_est) -> None:
        target.xyz_world = self.running_mean(target.xyz_world, target.observation_count, xyz)
        target.observation_count += 1
        target.last_seen_s = timestamp_s
        if track_id is not None:
            target.track_ids.add(track_id)
        if size_est is not None:
            self.welford_update_size(target, size_est)
        if isinstance(target, ConfirmedTarget):
            self.welford_update_position(target, xyz)
        target.position_history.append((timestamp_s, xyz))
        self.trim_pos_history(target)

    def promote(self, observations: list, timestamp_s: float) -> None:
        obs_labels = {self.to_obs(o).label for o in observations}
        confirmed_this_frame = {t.label for t in self.confirmed if t.label in obs_labels and not t.is_lost}
        ready = [
            p for p in self.potentials
            if p.observation_count >= self.config.min_frames
            and (p.last_seen_s - p.first_seen_s) >= self.config.min_time_s
        ]
        for p in ready:
            # skip the anchor gate on first-ever confirmation — no confirmed targets exist yet to co-observe
            if self.config.require_anchor and self.has_confirmed and not confirmed_this_frame:
                continue
            self.potentials.remove(p)
            self.confirmed.append(ConfirmedTarget(
                target_id=p.target_id,
                label=p.label,
                canonical_class=p.canonical_class,
                xyz_world=p.xyz_world,
                observation_count=p.observation_count,
                confirmed_at_s=timestamp_s,
                last_seen_s=p.last_seen_s,
                track_ids=set(p.track_ids),
                position_history=list(p.position_history),
                size_mean=p.size_mean,
                size_m2=p.size_m2,
                size_n=p.size_n,
            ))
            self.has_confirmed = True

    def expire(self, timestamp_s: float) -> None:
        for t in self.confirmed:
            if timestamp_s - t.last_seen_s > self.config.lost_timeout_s:
                t.is_lost = True
            elif t.is_lost:
                t.is_lost = False
        self.confirmed = [
            t for t in self.confirmed
            if not (t.is_lost and timestamp_s - t.last_seen_s > self.config.remove_timeout_s)
        ]
        self.potentials = [
            p for p in self.potentials
            if timestamp_s - p.last_seen_s <= self.config.lost_timeout_s
        ]

    def trim_pos_history(self, target) -> None:
        if not target.position_history:
            return
        cutoff = target.position_history[-1][0] - self.config.stationary_window_s
        target.position_history = [(t, x) for t, x in target.position_history if t >= cutoff]

    def welford_update_position(self, target: ConfirmedTarget, xyz: tuple) -> None:
        target.pos_n += 1
        n = target.pos_n
        old_mean = target.pos_welford_mean
        new_mean = tuple(old_mean[i] + (xyz[i] - old_mean[i]) / n for i in range(3))
        target.pos_welford_mean = new_mean
        target.pos_m2 += sum((xyz[i] - old_mean[i]) * (xyz[i] - new_mean[i]) for i in range(3))
        target.position_variance = target.pos_m2 / (n - 1) if n >= 2 else 0.0
        target.is_converged = (
            n >= self.config.convergence_min_obs
            and target.position_variance < self.config.convergence_variance_m2
        )

    def welford_update_size(self, target, new_est: SizeEstimate) -> None:
        if new_est.depth_quality == 0:
            return
        target.size_n += 1
        n = target.size_n
        if target.size_mean is None:
            target.size_mean = new_est
            return
        prev_mean_w = target.size_mean.width_m
        prev_mean_h = target.size_mean.height_m
        new_mean_w = prev_mean_w + (new_est.width_m - prev_mean_w) / n
        new_mean_h = prev_mean_h + (new_est.height_m - prev_mean_h) / n
        target.size_m2 += (new_est.width_m - prev_mean_w) * (new_est.width_m - new_mean_w)
        target.size_mean = SizeEstimate(
            width_m=new_mean_w,
            height_m=new_mean_h,
            aspect_ratio=new_mean_h / new_mean_w if new_mean_w > 0 else 0.0,
            depth_quality=new_est.depth_quality,
        )

    def size_variance(self, target) -> float:
        if target.size_n < 2:
            return 0.0
        return target.size_m2 / (target.size_n - 1)

    def update_embedding(self, target: ConfirmedTarget, new_emb: np.ndarray) -> None:
        if target.embedding is None:
            target.embedding = new_emb.copy()
            target.embedding_count = 1
        else:
            n = target.embedding_count + 1
            target.embedding = target.embedding + (new_emb - target.embedding) / n
            target.embedding_count = n

    def to_json(self) -> str:
        entries = []
        for t in self.confirmed:
            entry = {
                "target_id": t.target_id,
                "label": t.label,
                "xyz_world": list(t.xyz_world),
                "observation_count": t.observation_count,
                "confirmed_at_s": t.confirmed_at_s,
                "last_seen_s": t.last_seen_s,
                "embedding": base64.b64encode(
                    t.embedding.astype(np.float32).tobytes()
                ).decode() if t.embedding is not None else None,
            }
            entries.append(entry)
        return json.dumps(entries)

    @classmethod
    def from_json(cls, s: str, config: WorldTrackerConfig) -> "WorldTracker":
        """Reconstruct confirmed targets from a snapshot for cross-session re-association.

        Welford state, track_ids, and position_history are not restored — only the
        fields needed for re-association (position + embedding) are loaded.
        """
        tracker = cls(config)
        entries = json.loads(s)
        for e in entries:
            emb = None
            if e.get("embedding") is not None:
                raw = base64.b64decode(e["embedding"])
                emb = np.frombuffer(raw, dtype=np.float32).copy()
            ct = ConfirmedTarget(
                target_id=e["target_id"],
                label=e["label"],
                canonical_class=tracker.label_map.get(e["label"], e["label"]),
                xyz_world=tuple(e["xyz_world"]),
                observation_count=e["observation_count"],
                confirmed_at_s=e["confirmed_at_s"],
                last_seen_s=e["last_seen_s"],
                embedding=emb,
                embedding_count=1 if emb is not None else 0,
            )
            tracker.confirmed.append(ct)
            tracker.has_confirmed = True
        if tracker.confirmed:
            tracker.next_id = max(t.target_id for t in tracker.confirmed) + 1
        return tracker

    def combined_sim(self, entry_a: tuple, entry_b: tuple) -> float:
        """Position + embedding similarity score in [0, 1]. Higher = more similar.

        Each entry is (xyz, embedding) where embedding may be None.
        Falls back to position-only when either embedding is absent.
        """
        xyz_a, emb_a = entry_a
        xyz_b, emb_b = entry_b
        dist = self.assoc.euclidean(xyz_a, xyz_b)
        pos_score = 1.0 - min(dist / max(self.config.max_assoc_dist_m, 1e-6), 1.0)
        if emb_a is None or emb_b is None:
            return pos_score
        return 0.5 * pos_score + 0.5 * cosine_sim(emb_a, emb_b)

    def running_mean(self, current, n, new_val):
        alpha = self.config.position_ema_alpha
        if alpha > 0.0:
            return tuple(alpha * new_val[i] + (1.0 - alpha) * current[i] for i in range(3))
        return tuple((current[i] * n + new_val[i]) / (n + 1) for i in range(3))
