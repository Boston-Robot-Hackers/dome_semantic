#!/usr/bin/env python3
# map_rebasing — re-base stored targets when the map->odom transform jumps
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Re-base stored WorldTracker targets when map->odom jumps (F33 T03, new).

No prior implementation existed anywhere in this codebase. A target's
xyz_world is recorded in the `map` frame at observation time, per the
current map->odom estimate. When SLAM later corrects that estimate (a loop
closure, say), every previously-recorded position is now stale relative to
the corrected map - it was correct *given the old estimate*, not the new
one. Re-basing recomputes each stored (x, y) through the delta between the
old and new map->odom transforms, so stored targets stay aligned with the
current map. Planar (x, y, yaw) only - SLAM corrections on a ground robot
are planar; z is left untouched.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanarTransform:
    x: float
    y: float
    yaw: float  # radians


def _rotate(xy: tuple, yaw: float) -> tuple:
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, y = xy
    return (cy * x - sy * y, sy * x + cy * y)


def apply_transform(t: PlanarTransform, xy: tuple) -> tuple:
    """Map a point through t: rotate then translate."""
    rx, ry = _rotate(xy, t.yaw)
    return (rx + t.x, ry + t.y)


def invert_transform(t: PlanarTransform) -> PlanarTransform:
    """The transform t2 such that apply_transform(t2, apply_transform(t, p)) == p."""
    inv_yaw = -t.yaw
    ix, iy = _rotate((-t.x, -t.y), inv_yaw)
    return PlanarTransform(ix, iy, inv_yaw)


def compose_transforms(
    second: PlanarTransform, first: PlanarTransform
) -> PlanarTransform:
    """The transform equivalent to applying `first` then `second`."""
    rx, ry = _rotate((first.x, first.y), second.yaw)
    return PlanarTransform(rx + second.x, ry + second.y, first.yaw + second.yaw)


def yaw_from_quaternion(z: float, w: float) -> float:
    """Planar (z-axis only) quaternion -> yaw. Matches the z=sin(yaw/2),
    w=cos(yaw/2) encoding TF publishes for a ground robot's map->odom rotation."""
    return 2.0 * math.atan2(z, w)


def _angle_diff(a: float, b: float) -> float:
    return (b - a + math.pi) % (2.0 * math.pi) - math.pi


def has_jumped(
    old: PlanarTransform,
    new: PlanarTransform,
    epsilon_m: float = 0.05,
    epsilon_rad: float = 0.02,
) -> bool:
    return (
        abs(old.x - new.x) > epsilon_m
        or abs(old.y - new.y) > epsilon_m
        or abs(_angle_diff(old.yaw, new.yaw)) > epsilon_rad
    )


def rebase_delta(
    old_map_t_odom: PlanarTransform, new_map_t_odom: PlanarTransform
) -> PlanarTransform:
    """The transform mapping an old-map-frame point to its new-map-frame position."""
    return compose_transforms(new_map_t_odom, invert_transform(old_map_t_odom))


def rebase_xyz(delta: PlanarTransform, xyz: tuple) -> tuple:
    x, y, z = xyz
    nx, ny = apply_transform(delta, (x, y))
    return (nx, ny, z)


def rebase_tracker(tracker, delta: PlanarTransform) -> None:
    """Re-base every stored target's world-frame position and history through delta."""
    for t in list(tracker.confirmed_targets) + list(tracker.potential_targets):
        t.xyz_world = rebase_xyz(delta, t.xyz_world)
        t.position_history = [
            (ts, rebase_xyz(delta, xyz)) for ts, xyz in t.position_history
        ]
        if hasattr(t, "pos_welford_mean"):
            t.pos_welford_mean = rebase_xyz(delta, t.pos_welford_mean)
