#!/usr/bin/env python3
# target_merge — collapse same-class confirmed targets that sit too close together
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Merge pass for confirmed targets (F36).

Two potentials of one object can confirm separately, as two IDs a few
centimetres apart, when SLAM pose and depth error scatter the sightings.
After each tracker update, any two confirmed targets of the same canonical
class closer than that class's `merge_radius_m` become one.

- **The older target survives**: the lower `target_id`, since IDs are
  issued in creation order. Consumers that already hold that ID keep it.
- **Combined**: observation counts add, the position becomes the
  count-weighted mean, `last_seen_s` is the later one, `confirmed_at_s` the
  earlier one, `track_ids` the union. It stays lost only if both were lost.
- **Not combined**: Welford position/size stats, position history and the
  embedding stay the survivor's.
- Merging repeats until no pair is in range, since a merged position can
  move into range of a third target. Lost targets merge too, so a new ID
  formed beside a lost one folds back into it.
"""

import math

from dome_semantic.targets import ConfirmedTarget


def absorb(keep: ConfirmedTarget, drop: ConfirmedTarget) -> None:
    total = keep.observation_count + drop.observation_count
    keep.xyz_world = tuple(
        (k * keep.observation_count + d * drop.observation_count) / total
        for k, d in zip(keep.xyz_world, drop.xyz_world)
    )
    keep.observation_count = total
    keep.last_seen_s = max(keep.last_seen_s, drop.last_seen_s)
    keep.confirmed_at_s = min(keep.confirmed_at_s, drop.confirmed_at_s)
    keep.track_ids |= drop.track_ids
    keep.is_lost = keep.is_lost and drop.is_lost


def find_close_pair(
    confirmed: list, merge_radius_by_class: dict
) -> tuple[ConfirmedTarget, ConfirmedTarget] | None:
    """Return (older, newer) for the first same-class pair in range, or None."""
    by_age = sorted(confirmed, key=lambda t: t.target_id)
    for i, older in enumerate(by_age):
        radius_m = merge_radius_by_class.get(older.canonical_class)
        if radius_m is None:
            continue
        for newer in by_age[i + 1 :]:
            if newer.canonical_class != older.canonical_class:
                continue
            if math.dist(older.xyz_world, newer.xyz_world) <= radius_m:
                return older, newer
    return None


def merge_close_targets(
    confirmed: list, merge_radius_by_class: dict
) -> list[tuple[int, int]]:
    """Merge same-class confirmed targets in range, in place.

    merge_radius_by_class maps canonical class -> radius in metres; classes
    absent from it never merge. Returns (kept_id, dropped_id) per merge.
    """
    merges = []
    pair = find_close_pair(confirmed, merge_radius_by_class)
    while pair is not None:
        keep, drop = pair
        absorb(keep, drop)
        confirmed.remove(drop)
        merges.append((keep.target_id, drop.target_id))
        pair = find_close_pair(confirmed, merge_radius_by_class)
    return merges
