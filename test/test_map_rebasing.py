#!/usr/bin/env python3
# test_map_rebasing — pure tests for map->odom jump re-basing (F33 T03)
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import math

import pytest

from dome_semantic.map_rebasing import (
    PlanarTransform,
    apply_transform,
    compose_transforms,
    has_jumped,
    invert_transform,
    rebase_delta,
    rebase_tracker,
    rebase_xyz,
    yaw_from_quaternion,
)
from dome_semantic.targets import ConfirmedTarget, PotentialTarget

IDENTITY = PlanarTransform(0.0, 0.0, 0.0)


def test_apply_transform_translation_only():
    t = PlanarTransform(1.0, 2.0, 0.0)
    assert apply_transform(t, (0.0, 0.0)) == pytest.approx((1.0, 2.0))


def test_apply_transform_rotation_only():
    t = PlanarTransform(0.0, 0.0, math.pi / 2)
    x, y = apply_transform(t, (1.0, 0.0))
    assert x == pytest.approx(0.0, abs=1e-9)
    assert y == pytest.approx(1.0, abs=1e-9)


def test_invert_transform_round_trip():
    t = PlanarTransform(1.5, -2.5, 0.7)
    p = (3.0, -1.0)
    forward = apply_transform(t, p)
    back = apply_transform(invert_transform(t), forward)
    assert back == pytest.approx(p)


def test_compose_transforms_matches_sequential_application():
    first = PlanarTransform(1.0, 0.0, math.pi / 4)
    second = PlanarTransform(0.0, 2.0, math.pi / 4)
    p = (1.0, 1.0)
    sequential = apply_transform(second, apply_transform(first, p))
    composed = apply_transform(compose_transforms(second, first), p)
    assert composed == pytest.approx(sequential)


def test_has_jumped_false_within_epsilon():
    old = PlanarTransform(0.0, 0.0, 0.0)
    new = PlanarTransform(0.01, 0.01, 0.005)
    assert has_jumped(old, new) is False


def test_has_jumped_true_on_translation():
    old = PlanarTransform(0.0, 0.0, 0.0)
    new = PlanarTransform(0.5, 0.0, 0.0)
    assert has_jumped(old, new) is True


def test_has_jumped_true_on_rotation():
    old = PlanarTransform(0.0, 0.0, 0.0)
    new = PlanarTransform(0.0, 0.0, 0.2)
    assert has_jumped(old, new) is True


def test_rebase_delta_identity_when_transforms_equal():
    t = PlanarTransform(1.0, 2.0, 0.3)
    delta = rebase_delta(t, t)
    assert apply_transform(delta, (5.0, -3.0)) == pytest.approx((5.0, -3.0))


def test_rebase_xyz_preserves_z():
    old = IDENTITY
    new = PlanarTransform(1.0, 0.0, 0.0)
    delta = rebase_delta(old, new)
    result = rebase_xyz(delta, (0.0, 0.0, 2.5))
    assert result[2] == 2.5


def test_rebase_xyz_shifts_x_y_by_delta():
    old = IDENTITY
    new = PlanarTransform(2.0, -1.0, 0.0)
    delta = rebase_delta(old, new)
    result = rebase_xyz(delta, (0.0, 0.0, 0.0))
    assert result == pytest.approx((2.0, -1.0, 0.0))


def make_confirmed(xyz, history):
    return ConfirmedTarget(
        target_id=1,
        label="can",
        canonical_class="can",
        xyz_world=xyz,
        observation_count=3,
        confirmed_at_s=1.0,
        last_seen_s=2.0,
        position_history=list(history),
        pos_welford_mean=xyz,
    )


def make_potential(xyz, history):
    return PotentialTarget(
        target_id=2,
        label="cup",
        canonical_class="cup",
        xyz_world=xyz,
        observation_count=1,
        first_seen_s=1.0,
        last_seen_s=1.0,
        position_history=list(history),
    )


class FakeTracker:
    def __init__(self, confirmed, potentials):
        self._confirmed = confirmed
        self._potentials = potentials

    @property
    def confirmed_targets(self):
        return list(self._confirmed)

    @property
    def potential_targets(self):
        return list(self._potentials)


def test_rebase_tracker_updates_confirmed_and_potential_targets():
    confirmed = make_confirmed((0.0, 0.0, 1.0), [(1.0, (0.0, 0.0, 1.0))])
    potential = make_potential((0.0, 0.0, 0.5), [(1.0, (0.0, 0.0, 0.5))])
    tracker = FakeTracker([confirmed], [potential])

    delta = rebase_delta(IDENTITY, PlanarTransform(3.0, 0.0, 0.0))
    rebase_tracker(tracker, delta)

    assert confirmed.xyz_world == pytest.approx((3.0, 0.0, 1.0))
    assert confirmed.position_history[0][1] == pytest.approx((3.0, 0.0, 1.0))
    assert confirmed.pos_welford_mean == pytest.approx((3.0, 0.0, 1.0))
    assert potential.xyz_world == pytest.approx((3.0, 0.0, 0.5))
    assert potential.position_history[0][1] == pytest.approx((3.0, 0.0, 0.5))


def test_yaw_from_quaternion_identity():
    assert yaw_from_quaternion(0.0, 1.0) == pytest.approx(0.0)


def test_yaw_from_quaternion_ninety_deg():
    assert yaw_from_quaternion(
        math.sin(math.pi / 4), math.cos(math.pi / 4)
    ) == pytest.approx(math.pi / 2)


def test_rebase_tracker_identity_delta_is_noop():
    confirmed = make_confirmed((1.0, 2.0, 0.5), [(1.0, (1.0, 2.0, 0.5))])
    tracker = FakeTracker([confirmed], [])

    delta = rebase_delta(IDENTITY, IDENTITY)
    rebase_tracker(tracker, delta)

    assert confirmed.xyz_world == pytest.approx((1.0, 2.0, 0.5))
