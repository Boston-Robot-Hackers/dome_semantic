# F37 — Forget weak lost targets

**Priority**: High

**Date Created:** 2026-11-16

**Done:** yes

**Tasks File Created:** yes

**Tests Written:** yes

**Test Passing:** yes

**Description**: When a confirmed target goes lost, delete it if it had
fewer than `min_keep_obs` observations. Keep it indefinitely otherwise, as
F36 does today. This clears the short bursts of false detection that F36's
"never delete lost targets" made permanent, without giving back F36's fix
for real objects that go out of view.

## Why

On `f36run6` (2026-11-13) the map ended with one real can (1496 obs) and
11 false cups, several with only 5–15 obs. A target only has to be seen in
`min_frames` (5) frames over `min_time_s` (1 s) to confirm. Before F36 a
lost target was deleted 30 s later, so these cleaned themselves up; since
F36 they stay, and "go to cup" could send the robot to one.

## Scope

- **One global threshold**, `min_keep_obs`, a new `WorldTrackerConfig`
  field. It becomes a ROS param automatically through
  `declare_tracker_config`. The starting value is **30**, to be checked by
  replaying `f36run6`.
- **Forget at the moment of going lost**, in `WorldTracker.expire`. No
  extra timer.
- **A target that is only lost, never deleted, is unchanged**: one with
  `min_keep_obs` or more stays forever, publishes, is drawn dimmed and is
  saved, as F36 built it.
- **Saved maps need no migration.** Restored targets come back with their
  saved `last_seen_s`, so the first `expire` marks them lost, and the weak
  ones are forgotten then.

## Not in scope

- **Steady false detections** and the **can/cup double label**: these
  have as many observations as real targets, so a count threshold can't
  tell them apart. They belong to `dome_vision` I05.
- Per-class thresholds, or raising `min_frames`/`min_time_s`.

## Trade-off accepted

A **real object seen only briefly** (under ~3 s at 10 Hz) and then lost is
forgotten too. If it is seen again, it confirms again under a new ID.

## How to Demo

**Setup**: the robot's `~/bags/f36run6` bag; the live stack stopped.

**Steps**:

1. Replay `f36run6` through the F37 node with a fresh `map_name`, per
   `process/02-doc/notes.md`, "Bag replay of a drive".
2. Read the saved `~/.dome/semantic_maps/<map_name>.json`.

**Expected output**: the can keeps one ID, as on the original run, and
the short-burst cup IDs (under `min_keep_obs` obs) are gone. The steady
false cup (~1000 obs) remains, as expected.

## Process Gate

After creating this feature file and the corresponding task file, **stop and present the plan to the user**. Do not write any code or content until the user gives explicit approval to proceed.
