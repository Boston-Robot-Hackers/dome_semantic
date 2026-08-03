#!/usr/bin/env python3
# targets — data classes for world-frame object tracking
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np

from dome_semantic.size_estimate import SizeEstimate


class Observation(NamedTuple):
    xyz: tuple
    label: str
    frame_num: int
    track_id: int | None = None
    size_est: "SizeEstimate | None" = None


@dataclass
class PotentialTarget:
    target_id: int
    label: str
    canonical_class: str
    xyz_world: tuple[float, float, float]
    observation_count: int
    first_seen_s: float
    last_seen_s: float
    track_ids: set = field(default_factory=set)
    position_history: list = field(default_factory=list)  # list of (timestamp_s, xyz)
    size_mean: SizeEstimate | None = None
    size_m2: float = 0.0   # running sum of squares for variance (Welford M2)
    size_n: int = 0        # number of size observations


@dataclass
class ConfirmedTarget:
    target_id: int
    label: str
    canonical_class: str
    xyz_world: tuple[float, float, float]
    observation_count: int
    confirmed_at_s: float
    last_seen_s: float
    is_lost: bool = False
    track_ids: set = field(default_factory=set)
    position_history: list = field(default_factory=list)  # list of (timestamp_s, xyz)
    size_mean: SizeEstimate | None = None
    size_m2: float = 0.0
    size_n: int = 0
    # Welford running variance for position (m²). Updated on every confirmed-target observation.
    pos_m2: float = 0.0
    pos_n: int = 0
    pos_welford_mean: tuple = field(default_factory=lambda: (0.0, 0.0, 0.0))
    position_variance: float = 0.0
    is_converged: bool = False
    embedding: np.ndarray | None = field(default=None, compare=False)
    embedding_count: int = 0
