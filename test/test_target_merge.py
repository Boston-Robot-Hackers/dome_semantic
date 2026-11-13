#!/usr/bin/env python3
# test_target_merge — pure tests for the same-class confirmed-target merge pass
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import pytest

from dome_semantic.target_merge import merge_close_targets
from dome_semantic.targets import ConfirmedTarget

RADII_M = {"can": 0.4}


def target(target_id, xyz, label="can", obs=10, last_seen_s=1.0, is_lost=False):
    return ConfirmedTarget(
        target_id=target_id,
        label=label,
        canonical_class=label,
        xyz_world=xyz,
        observation_count=obs,
        confirmed_at_s=float(target_id),
        last_seen_s=last_seen_s,
        is_lost=is_lost,
        track_ids={target_id},
    )


def test_close_same_label_targets_merge_to_older_id():
    confirmed = [target(7, (1.3, 0.0, 0.0), obs=30), target(3, (1.0, 0.0, 0.0))]

    merges = merge_close_targets(confirmed, RADII_M)

    assert merges == [(3, 7)]
    assert [t.target_id for t in confirmed] == [3]
    kept = confirmed[0]
    assert kept.observation_count == 40
    assert kept.xyz_world == pytest.approx((1.225, 0.0, 0.0))
    assert kept.track_ids == {3, 7}
    assert kept.confirmed_at_s == 3.0


def test_different_labels_at_same_point_do_not_merge():
    confirmed = [target(1, (1.0, 0.0, 0.0)), target(2, (1.0, 0.0, 0.0), label="cup")]

    assert merge_close_targets(confirmed, {"can": 0.4, "cup": 0.4}) == []
    assert len(confirmed) == 2


def test_targets_beyond_radius_do_not_merge():
    confirmed = [target(1, (0.0, 0.0, 0.0)), target(2, (0.41, 0.0, 0.0))]

    assert merge_close_targets(confirmed, RADII_M) == []


def test_class_without_radius_never_merges():
    confirmed = [
        target(1, (0.0, 0.0, 0.0), label="cup"),
        target(2, (0.0, 0.0, 0.0), label="cup"),
    ]

    assert merge_close_targets(confirmed, RADII_M) == []


# A new ID formed beside a lost target folds back into it, and is no longer lost.
def test_lost_target_absorbs_visible_newcomer():
    confirmed = [
        target(1, (0.0, 0.0, 0.0), last_seen_s=1.0, is_lost=True),
        target(5, (0.2, 0.0, 0.0), last_seen_s=60.0),
    ]

    merge_close_targets(confirmed, RADII_M)

    assert [t.target_id for t in confirmed] == [1]
    assert confirmed[0].is_lost is False
    assert confirmed[0].last_seen_s == 60.0


# The merged mean can move into range of a third target; merging repeats.
def test_merge_chains_until_no_pair_in_range():
    confirmed = [
        target(1, (0.0, 0.0, 0.0), obs=1),
        target(2, (0.35, 0.0, 0.0), obs=10),
        target(3, (0.70, 0.0, 0.0), obs=10),
    ]

    merges = merge_close_targets(confirmed, RADII_M)

    assert merges == [(1, 2), (1, 3)]
    assert [t.target_id for t in confirmed] == [1]
