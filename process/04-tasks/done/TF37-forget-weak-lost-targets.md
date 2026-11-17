# TF37 Forget weak lost targets for Feature F37

**Date Created:** 2026-11-16

TF37.0 measures the observation counts first, so TF37.1's threshold is
set from data.

## TF37.0 — Measure observation counts on recorded runs

**Status**: done 2026-11-16 — `min_keep_obs` 40; table in `current.md`

**Description**: From the saved maps of `f36run6` and `f36replay_keep`
(`~/.dome/semantic_maps/*.json`), list each confirmed target's label,
`observation_count` and whether it is a known real object. Pick
`min_keep_obs` with margin between the largest short-burst false target
and the smallest real one. 30 is the starting guess. Record the table and
the choice in `process/02-doc/current.md`.

**Test**: manual — a data measurement, nothing to unit-test.

## TF37.1 — Add `min_keep_obs` to the config

**Status**: done 2026-11-16

**Description**: Add `min_keep_obs: int` to `WorldTrackerConfig`, with
TF37.0's value as the default and a one-line "why" comment. Set it
explicitly in `config/semantic_map.yaml` too, so the robot's value is
visible beside the other tuning.

**Test**: unit — `declare_tracker_config` exposes `min_keep_obs` as a ROS
param; the shipped config loads it (`test_tracker_params.py`,
`test_shipped_config.py`).

## TF37.2 — Forget weak targets in `expire`

**Status**: done 2026-11-16

**Description**: In `WorldTracker.expire`, delete a confirmed target that
is lost and has fewer than `min_keep_obs` observations. Replace the
"never deleted (F36)" comment. Update the class and module docstrings in
`world_tracker.py` and `semantic_map_node.py` that say lost targets are
never deleted.

**Test**: unit — see TF37.3.

## TF37.3 — Tests

**Status**: done 2026-11-16 — 160 pass, ruff clean

**Description**: Add to `test/test_world_tracker.py`:

- A target with `min_keep_obs − 1` obs is gone once lost; one with
  exactly `min_keep_obs` is kept, marked lost.
- A weak target that is **not** lost (still being seen) is kept.
- A strong lost target that is seen again is un-lost, same ID (F36's
  behavior, still holds).
- A snapshot restored with `from_json` drops its weak targets on the
  first `update`, and keeps its strong ones.
- A weak target that was forgotten and is seen again confirms under a
  **new** ID (the accepted trade-off).

Run the full suite and ruff.

**Test**: this step is the tests.

## TF37.4 — Replay `f36run6` through the F37 node

**Status**: done 2026-11-16 — pass; 4 targets, can keeps one ID; see `current.md`

**Description**: Replay `~/bags/f36run6` per `notes.md`, "Bag replay of a
drive", with a fresh `map_name`. Compare the saved targets with the
original run: the can keeps one ID; short-burst cups are gone; the steady
false cup T2 remains. Record the result in `current.md`.

**Test**: manual — bag replay on the robot.
