# TF36 Stable targets for Feature F36

Order matters: TF36.0–TF36.2 measure re-basing's effect on one recorded
drive, before anything else changes, so the radius in TF36.3 is set from
data.

## TF36.0 — Record a bag and replay it through the current node

**Status**: not done

**Description**: On the robot, record one bag (`/tf`, `/tf_static`,
`/oak/detections_3d`, `/odom`, `/scan`). Drive the same loop 2–3 times past
one can at a tape-measured spot. Replay it with `use_sim_time` through the
current node, and record each confirmed target's ID and pose per pass. Note
the number of duplicate IDs, the spread of the can's position across passes,
and the error against the tape. The bag recording and replay commands go in
`process/02-doc/notes.md`.

**Test**: manual — results recorded in `current.md`.

## TF36.1 — Remove global re-basing

**Status**: not done

**Description**: Delete `map_rebasing.py`, `maybe_rebase` and
`last_map_t_odom` from `semantic_map_node.py`, plus their tests. Amend F33's
G1 and `spec.md` to say targets are recorded in `map` at observation time
and not re-based. No parameter to keep the old path: the A/B uses the bag
from TF36.0, replayed against the code before and after this step.

**Test**: unit — a target's stored pose does not change when `map → odom`
changes and nothing new is observed.

## TF36.2 — Replay the same bag without re-basing

**Status**: not done

**Description**: Replay TF36.0's bag through the TF36.1 node and compare
duplicate IDs, spread and tape error with TF36.0's numbers. If the spread is
still ~0.3 m, SLAM and depth error dominate, and TF36.3/TF36.4 are the real
fix.

**Test**: manual — comparison recorded in `current.md`.

## TF36.3 — Widen can re-association

**Status**: not done

**Description**: Set the can's `drift_tolerance_m` in
`config/class_profiles.yaml` from TF36.2's measured spread, with margin.
Starting point ~0.4 m; check it doesn't merge two real cans placed apart.

**Test**: unit — an observation at the new radius minus 1 cm re-associates;
one at plus 1 cm creates a potential.

## TF36.4 — Merge pass for same-label confirmed targets

**Status**: not done

**Description**: After each update, merge same-label confirmed targets
closer than the class's `merge_radius_m` (raised to suit TF36.2's numbers),
keeping the older ID and combining observation counts and means. Check
`dome_vision` F39 (same idea, deferred) for anything worth reusing.

**Test**: unit — two close same-label targets merge to the older ID; two
different labels at the same point don't.

## TF36.5 — Keep confirmed targets when unseen

**Status**: not done

**Description**: Stop deleting confirmed targets on `remove_timeout_s`.
Lost stays a status: lost targets keep publishing on `/semantic/targets`
and are saved. Markers draw them dimmed. Potentials keep the
`lost_timeout_s` expiry. Update `spec.md`'s "Persist across visibility gaps"
behavior. Remove `remove_timeout_s` if nothing else uses it.

**Test**: unit — a confirmed target unseen for longer than the old remove
timeout is still published and saved; a potential still expires.

## TF36.6 — Test suite for F36

**Status**: not done

**Description**: Make sure TF36.1, TF36.3, TF36.4 and TF36.5's tests exist
and pass, plus a whole-tracker test: one object re-observed after a long
gap with a ~0.3 m offset keeps its ID. The full suite and ruff stay clean.

**Test**: this task is the tests.

## TF36.7 — Real-robot check

**Status**: not done

**Description**: Run F36's demo on the robot. This doubles as TF33.0's
re-run; record the result in both.

**Test**: manual — the F36 demo, recorded in `current.md`.
