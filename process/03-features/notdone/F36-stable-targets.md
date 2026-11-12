# F36 — Stable targets: no global re-basing, wider re-association, keep unseen targets

**Priority**: High

**Done:** no

**Tasks File Created:** yes

**Tests Written:** no

**Test Passing:** no

**Description**: Make a confirmed target stay put in the `map` frame, so the
same unmoved object keeps one ID and one pose across loops and while out of
view. That is what `dome_mission`'s go-to-label needs. TF33.0's 2026-11-12
run failed this: the same can came back 0.36 m off after a loop and got a new
ID each time (`process/02-doc/current.md`, "TF33.0 run, 2026-11-12").

## Why

- **Global re-basing is wrong** (architect review, 2026-11-12). slam_toolbox
  steps `map → odom` to absorb odometry drift, not to revise the map. A
  target already transformed at its own stamp is SLAM's best estimate, so
  re-basing it adds the robot's later drift. It made the 11-12 miss worse.
- **0.15 m re-association is too tight.** SLAM pose plus OAK-D depth error
  is ~0.2–0.4 m, so a correct re-sighting can fall outside it.
- **Unseen targets vanish.** Lost after 5 s, deleted after 30 s, so the map
  forgets everything out of view, and a deleted target is never saved.

## Scope

- **Remove global re-basing** (`map_rebasing.py`, `maybe_rebase`). This
  **amends F33 G1**: targets are recorded in `map` at observation time and
  then left alone.
- **Widen can re-association** to a value set from measured spread (starting
  point ~0.4 m).
- **Merge pass**: combine same-label confirmed targets closer than a merge
  radius, keeping the older ID.
- **Keep confirmed targets when unseen.** Lost becomes a status, not a
  removal; they keep publishing (consumers use `last_seen`), are saved, and
  are drawn dimmed. Potentials keep their short timeout.

**Out of scope**: loop-closure-aware local correction (per-graph-node
anchoring); removing a target on negative evidence (in view but not
detected); renaming `/targets/*` topics; marker size. No message change.

## How to Demo

**Setup**: robot stack as in TF33.0 (drivers, OAK-D detection only, real
SLAM, `semantic.launch.py`), RViz on `/targets/markers`, one can on the floor.

**Steps**:
1. Face the can until it's confirmed; note its ID and map pose.
2. Drive a loop of over 30 s with the can out of view, then face it again.
3. Ctrl-C the semantic launch; read `~/.dome/semantic_maps/<name>.json`.

**Expected output**: the can keeps its ID (or merges back into it) and its
map pose stays within the new radius. While out of view it stays in
`/semantic/targets` and shows dimmed in RViz. The saved file holds it.

## Process Gate

After creating this feature file and the corresponding task file, **stop and
present the plan to the user**. Do not write any code or content until the
user gives explicit approval to proceed.
