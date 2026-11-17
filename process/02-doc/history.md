# History

Completed-work log, moved out of `current.md` to keep session handoff lean.
New entries go at the top, newest first; older entries below are in date order.

## 2026-11-10 to 2026-11-13 — F36 and TF33.0 robot runs

Moved from `current.md` on 2026-11-16. Newest run first.

### TF36.7 re-run, 2026-11-13: pass

**Setup**: full stack, real SLAM, map and bag `f36run6` (387 s). One can,
taped **1.5 m** straight ahead, so the tape point is map (1.5, 0.0). The
semantic node started ~57 s after the bag.

**Result: pass.** One can ID, T1, from first to last observation (1496
obs), at (1.60, −0.04) → (1.59, −0.05): **moved ≤ 0.01 m**, 0.10 m from
the tape.

| Out of view | Robot pose when re-seen | Range |
|---|---|---|
| 155–188 s (33 s) | (2.54, −1.30), past the can, facing 127° | 1.56 m |
| 203–265 s (62 s) | (−0.11, −0.07), near the start | 1.70 m |
| 282–351 s (70 s) | (−0.25, 0.24), returning from the north | 1.86 m |

- **SLAM corrected a lot, and the can held**: `map → odom` grew to
  (−1.10, 0.16, 6.7°) by the end. With re-basing this would have moved
  the can by up to ~1 m; without it, nothing moved.
- **No second can ID.** The other 11 targets are all cups.

**Still open, outside F36:**

- **11 false cup IDs**, several with 5–15 obs, now permanent since lost
  targets are kept. Cup T13 at (1.22, −0.13), 0.38 m from the can with
  9 obs, may be the can/cup double label.
- **Cup T2 at (3.28, −1.54)**, 1061 obs, was also seen in `f36run3`/`4`
  in that direction. The user says there is no cup, so it's a steady
  false detection of something real there.

**Runs that don't count**: `f36run3` (563 s) never moved: the robot sat at
(0, 0) the whole time. `f36run4` has no bag (the recorder wasn't started);
its saved map also shows a single can ID. `f36run5` was abandoned before
driving.

### TF36.7 robot run, 2026-11-13

**Setup**: full stack, real SLAM, map `f36run`, bag `~/bags/f36run`
(338 s, includes `/semantic/targets`). Two cans: the taped one straight
ahead, a second ~2 m to the left at about the same distance ahead. The
robot drove ~80–170 s, then sat still at map ≈ (0.0, 1.44), facing −44°.

**The tracker passed:**

- **T1** (taped can, (1.10, −0.14), 991 obs) **kept its ID** after
  ~210 s out of view, re-seen from a new viewpoint, and moved 0.02 m.
- **T5** at (1.31, 1.93) is the second can.
- All 12 targets were saved, most of them lost by shutdown.

**But the taped can also became T27** at (1.26, −0.94), 889 obs, 0.82 m
from T1. **The cause is depth, not the tracker**:

- From the stopped robot, detections of one can (one track, id 30) at one
  bearing flicker in range: **~85% at ~2.6 m, a few at ~2.0 m**.
- 2.0 m is the range to T1 from that pose, so the pose is right and the
  2.6 m mode is ~0.6 m of depth error at ~2.6 m. Likely `dome_vision`
  sampling depth from behind a 6.6 cm can at that range.
- No association radius should absorb 0.6 m; the fix belongs in
  `dome_vision` (depth on small, distant objects), or a max-range gate.

**Other**: can T23 + cup T24 at (0.51, 1.36), ~0.5 m in front of the stop
pose, match no real can (ghost / double label); 7 cup IDs, several with
7–15 obs. **No full loops were driven**: one ~90 s drive, then stationary.

### TF36.0 bag replay, 2026-11-13

**Bags**: `~/bags/f36drive` (395 s; `/tf`, `/tf_static`,
`/oak/detections_3d`, `/odom`, `/scan`) and `~/bags/f36replay_before`
(`/semantic/targets` from the current node, re-basing on). Map name
`f36bag`; replay `map_name` `f36replay_before`.

**Setup**: robot started at map (0, 0) facing **−x** (yaw −179.8°), so
the can, taped 1.0 m straight ahead, is at map **(−1.0, 0.0)**. The robot
sat still ~110 s, drove 110–240 s, then sat still to the end.

**Result for the can:**

| ID | Seen (s) | Obs | Pose (map) | Tape error |
|---|---|---|---|---|
| T1 | 1–110 | 1052 | (−1.07, 0.12) | 0.14 m |
| T21 | 154–160 | 18 | (−1.05, 0.24) | 0.25 m |

- **Position held**: T21 is 0.13 m from T1, inside the can's 0.15 m
  `drift_tolerance_m`, though `map → odom` had grown to 0.2–0.5 m and up
  to 14° by then.
- **New ID because T1 was deleted**: lost at ~110 s (`lost_timeout_s` 5),
  removed 30 s later (`remove_timeout_s`); the can was out of view ~50 s.
  This is **TF36.5**'s case.
- **Re-basing barely mattered here**: `map → odom` was exactly zero while
  T1 was observed.
- **Thin evidence**: the drive passed the can only once, not 2–3 times.
  TF36.2 compares on this one revisit.

**Other findings**:

- **Can/cup double label is back**: a second object near map
  (0.6–1.1, −0.3 to −1.0) produced cans T15/T16/T34/T38 and cups
  T17/T35/T39, with can+cup pairs at the same spot (T16/T17, T34/T39).
  Cup clusters near (−0.7, −3.6) and a can at (−1.76, 0.43) are unidentified.
- **`/cmd_vel` type mismatch**: Nav2's `collision_monitor` publishes
  `TwistStamped`, `gendrv` subscribes `Twist`, so Nav2 commands never reach
  the motors (teleop is unaffected). `ros2 bag record` logs an error about
  it; harmless for the recording. A `dome2`/`dome_nav` issue.
- The EKF's `odom` starts at yaw −179.8°, not 0.

### TF36.2 replay without re-basing, 2026-11-13

Same `~/bags/f36drive`, through the TF36.1 node, into
`~/bags/f36replay_after` (`map_name` `f36replay_after`).

**The taped can is unchanged**: T1 (−1.07, 0.12), 0.14 m tape error, then
T24 at (−1.05, 0.24) after the gap, exactly as before. Re-basing wasn't
the cause in this drive; **the 30 s remove timeout is** (TF36.5).

**Elsewhere, re-basing was sliding targets while they were observed:**

| | Before (re-basing) | After (none) |
|---|---|---|
| Target IDs | 20 | 25 |
| Per-ID `moved_m` | up to 0.42 m | ≤ 0.06 m (one 0.11) |

- **Without re-basing, targets stay put, and more IDs split.** In the
  cluster near (0.6–1.0, −0.4 to −1.0), later sightings land beside the
  earlier IDs instead of dragging them, e.g. cans T19 (0.86, −0.43),
  T37 (0.80, −0.37), T40 (0.97, −0.49): **~0.1–0.2 m apart**, just past
  the can's 0.15 m radius.
- **Measured spread for one re-observed object is ~0.13–0.2 m** here, not
  the 0.3 m of TF33.0's run. TF36.3's ~0.4 m starting radius covers it.
- **Can't yet check "doesn't merge two real cans"**: what's actually in
  that cluster is unknown, and it's also full of can/cup double labels.

### Replay with TF36.3 + TF36.4 (0.4 m radius, merge pass), 2026-11-13

`~/bags/f36replay_merge`: **23 IDs** (25 without them). In the cluster,
can IDs drop from 6 to 4 and settle into **two cans ~0.45 m apart**, near
(0.65, −0.95) and (0.9, −0.45), so 0.4 m keeps them separate.

- **Every remaining can duplicate is a deleted-then-re-seen case**:
  T38 is 0.12 m from T17 and T33 is 0.11 m from T18, but T17/T18 were
  removed 30 s after going lost, before the newcomer confirmed. Same for
  the taped can (T1 → T21). **TF36.5 should collapse all of these.**
- Merges inside a visibility window work: e.g. old T21 folded into T17.

### Replay with all of TF36.1–TF36.5, 2026-11-13

`~/bags/f36replay_keep`: **18 IDs** (20 at baseline, 23 with only the
radius + merge). **Pass for the taped can**: T1 keeps its ID across the
~50 s gap, 1074 obs (the re-sighting's 18 folded in), 0.14 m tape error.

- **Cluster**: two cans, T17 (0.68, −0.86) and T18 (0.94, −0.48),
  0.44 m apart; the T38/T33 duplicates folded into them (122 and 254 obs).
- **Can T21** at (−1.72, 0.41), 11 obs, 0.75 m from T1: unidentified.
- **New cost: false confirmations are now permanent.** 13 cup IDs stay on
  the map, several with only 7–17 obs, plus cup T19/T34 on top of cans
  T18/T17 (double label). Cups T22/T25 are 0.17 m apart, past the cup's
  0.12 m merge radius. Candidate follow-ups, outside F36: drop lost
  targets with few obs, widen the cup radii, fix the double label in
  `dome_vision`.

### TF33.0 run, 2026-11-12

**Setup**: battery, OAK-D on USB 3 (bus 2/3), real SLAM, map names
`f33slam` → `f33slam2` → `f33slam4` (restarted twice; see below).

**Result: fail.** In `f33slam4`, baseline T1 `can` at map (1.36, 0.22) with
`map → odom` (0.19, −0.07, −2.4°). After a loop, the same can came back as
T10, T31, then T33 at (1.46, 0.57) with `map → odom` (0.07, −0.01, −6.2°).

- **0.36 m apart**, beyond the can's 0.15 m `drift_tolerance_m`, so each
  return is a new ID. The current view was always self-consistent.
- In `f33slam`, the same can moved 1.9 m, (1.44, −0.08) → (0.49, −1.70),
  with `map → odom` grown to (−0.12, 0.97, −25°). **Odometry drifts a lot.**
- The node logged `map->odom jumped; re-based stored targets.` at 17:26:47
  (twice) and 17:27:39 — inside the baseline window and mid-loop.

**Architect review of re-basing** (`map_rebasing.py`,
`semantic_map_node.py:152-162`):

- **Re-basing is wrong as built.** slam_toolbox steps `map → odom` to absorb
  odometry drift since its last graph node; that says nothing about where a
  target already transformed at its own stamp is. Re-basing adds the
  robot's *later* drift to an *earlier* observation, pinning targets to
  `odom`. It's only right after a loop closure, and then only locally.
- The 5 cm / 0.02 rad gate absorbs small steps and applies big ones, so
  what a target inherits is arbitrary.
- Replaying the logged values: re-basing moved T1 to 0.42 m from T33, so it
  **made this miss worse by ~0.06–0.1 m**. The other ~0.3 m is most likely
  SLAM pose plus OAK-D depth error, so 0.15 m is too tight a radius.

**Other findings**:

- **`f33slam.json` from 11-10 was saved correctly** (T9, 8021 obs) and was
  restored on start. Persistence is keyed only by `--map_name`, so reusing
  a name with a fresh SLAM map silently restores targets in a dead frame.
- **IDs count potentials, not targets** (`world_tracker.py:162,176`), so
  CN51 after a few minutes is noise candidates, not 50 confirmed targets.
- **EKF stalled for 10.65 s** at 17:06:45 ("Failed to meet update rate").
  Load, temperature, memory and throttling were all fine. Unexplained; a
  DDS publish blocking on the laptop's RViz over Wi-Fi is one suspect. A
  `dome2` issue.
- **The semantic node stopped publishing once** (`f33slam3`): detections in
  at 8 Hz, nothing out on `/semantic/targets` or `/targets/markers`, all
  threads waiting on futexes, ~8% CPU. Gone after restarting everything;
  not reproduced. If it recurs, don't kill it — take a `py-spy dump`.
- **No can/cup double label this run.**
- **Markers are too small at map zoom** (8 cm sphere, true size), and
  marker topics are `/targets/*` while targets are `/semantic/*`. Both
  are proposed chores.
- The map being mostly −1 is normal: unseen cells inside SLAM's bounding
  box.

### TF33.0 run, 2026-11-10 (still open)

- **One can was detected as both `can` and `cup`** at the same point, making
  two targets and blinking markers. Not seen on 11-12. The fix belongs in
  `dome_vision` (cross-class box suppression); quick test:
  `ros2 param set /dome_vision confidence 0.7`.
- Depth read 1.43–1.45 m against a taped 1.50 m: within stereo error.

**2026-08-02** — package created and bootstrapped.

## Done

- **TF33 T01** (`dome_semantic_msgs`) — done previously, lives in the sibling
  `dome_semantic_msgs` repo (matches spec: `schema_version`, `target_id`,
  `label`, `pose`, `observation_count`, `last_seen`, `track_ids`).
- **TF33 T02** — pure tracker core ported from `dome_vision`:
  `world_tracker.py` + `association.py`, `class_profiles.py`,
  `size_estimate.py`, `targets.py`, `tracker_config.py`, `geometry.py`, plus a
  new `embedding_similarity.py` (cosine_sim only, split out of
  `dome_vision`'s `embedding.py` to avoid pulling `torch`/`torchvision`/`cv2`
  into this package). Behavior-preserving — same thresholds/tolerances.
  83 tests pass (`/usr/bin/python3 -m pytest test/`); `colcon build` clean.
  Two of the original 21 test failures on first port were dropped as
  out-of-scope (`test_appconfig_world_tracker_section`,
  `test_appconfig_world_tracker_defaults_when_absent` — they test
  `dome_vision`'s own `AppConfig`, not `WorldTracker`); the rest were fixed by
  porting `tests/conftest.py`'s cwd-fixture and the
  `examples/configs/class_profiles.yaml` fixture file alongside the code.
  `dome_vision`'s originals were **not** deleted — cleanup is deferred until
  the ROS shell (T03/T04) is proven, same pattern F35/TF35 T06 used.
- **TF33 T03** — `map`-frame recording + re-basing on `map→odom` jumps. Not a
  port this time — nothing like it existed anywhere; `dome_vision`'s current
  node only transforms camera→`odom` and has no re-basing at all. New:
  `tf_adapter.py` (ported `TFAdapter`, retargeted to `map`, now uses the
  detection's real stamp instead of the original's ignored one),
  `map_rebasing.py` (pure SE(2) transform composition + `rebase_tracker`),
  and this package's first ROS node, `semantic_map_node.py` (subscribes
  `/oak/detections_3d`, TF-transforms + re-bases; no publishing yet — that's
  T04). 110 tests pass total; `colcon build` clean.
- **Checkpoint** (2026-08-02) — added `ruff.toml` (was missing since bootstrap;
  matches `dome_mission`/`dome_nav`'s: line-length 88, ignore `EXE001` for the
  mandatory-shebang convention). Fixed everything `ruff check`/`ruff format`
  flagged except two: unsorted imports, an unused `pytest` import, 5×
  `dict()` → `{}` literal rewrites in test config helpers, 2 dead
  (never-referenced) local vars, 2 unused tuple-unpacks renamed to `_`. One
  substantive fix: `tf_adapter.py`'s `except Exception` narrowed to the
  three `tf2_ros` exceptions this codebase catches everywhere else a TF
  lookup can fail (`dome_nav`'s `explorer_manager_node.py`, this package's
  own `semantic_map_node.py`) — a real bug elsewhere in that method should
  surface, not get silently mapped to "transform unavailable"; updated the
  two tests that raised a generic `Exception` to raise
  `tf2_ros.LookupException` instead. **Left deliberately unfixed**: two
  `SIM102` (nested-if) findings in `association.py` — that file is T02's
  behavior-preserving port, and reshaping matching-logic control flow isn't
  a checkpoint-scope change. 110 tests still pass; `colcon build` clean.
  Also converted the 4 T03-authored files' (`tf_adapter.py`,
  `map_rebasing.py`, `semantic_map_node.py`, `embedding_similarity.py`)
  multi-line rationale `#` comment blocks into proper module docstrings —
  ruff doesn't flag this, but style_guide.md's MUST rule against narrative
  comment blocks does; the ported T02 files were left as-is (matches
  `dome_vision`'s own pre-existing convention, not introduced this session).

- **TF33 T04** (2026-08-03) — typed `SemanticTargetArray` publishing +
  node wiring. New `tracker_params.py` (`declare_tracker_config`, pure
  `node`-duck-typed function walking `WorldTrackerConfig.model_fields`,
  mirrors `dome_nav`'s F34 dataclass-single-source-of-truth pattern for
  pydantic). `SemanticMapNode` gained `/semantic/targets`
  (`SemanticTargetArray`, throttled), `/targets/markers` (map frame,
  throttled), `/targets/assoc_diag` (unthrottled), `/describe_scene`
  (Trigger). New `publish_every_n` ROS param (default 5). Target
  orientation always identity — `WorldTracker` has no facing estimate.
  119 tests pass; `colcon build` clean (hit and fixed a stale
  `build/dome_semantic_msgs` CMake cache pointing at a path missing
  `src/` — unrelated to this task's code).
- **TF33 T06** (2026-08-03) — persistence keyed to SLAM map identity. New
  `semantic_persistence.py`: `save_semantic_map`/`load_semantic_map`
  read/write `~/.dome/semantic_maps/<map_name>.json`, envelope
  `{"map_name": ..., "targets": [...]}` wrapping `WorldTracker.to_json()`.
  Primary key is the (sanitized) filename; envelope's own `map_name` is a
  second check catching sanitization collisions (`"room a"`/`"room#a"` both
  become `room_a.json`) — any mismatch or unrecognized format falls back to
  a fresh tracker + warning, never a silent merge. **Decided against**
  migrating old dome_vision-era bare-array files: no such file can exist at
  the new keyed path, so a migration branch would be speculative code for a
  case that can't occur. Node gained a `map_name` param (default
  `"unknown"`) and a `save()` called from `main()`'s `finally`. 127 tests
  pass; `colcon build` clean.
- **Full `process/01-literate/` set** (2026-08-03) — `00-overview.md`
  theory-of-operation plus one dependency-ordered chapter per module (14
  files total: 00 + 13). Package had none before this session.
- **Checkpoint** (2026-08-03) — `ruff check`/`ruff format` clean across the
  repo, including fenced Python blocks inside `process/01-literate/*.md` (a newer
  ruff feature reformats those too). One substantive fix, this time
  **reversing** the 2026-08-02 checkpoint's deliberate call: that session
  left two `SIM102` (nested-if) findings in `association.py` unfixed,
  reasoning "reshaping matching-logic control flow isn't a checkpoint-scope
  change" for a T02 behavior-preserving port. Revisited because the merge
  ruff suggests (`if a: if b: continue` → `if a and b: continue`) is a pure
  boolean identity, not a control-flow reshape — applied both, all 127
  tests still pass unchanged. Also fixed a real (if minor) finding in this
  session's own code: `seconds_to_ros_time`'s redundant `int(round(...))` —
  `round()` on a float with no `ndigits` already returns `int`.
- **TF33.8 reworded** (2026-10-23) — split into Part A (node-only launch
  file), Part B (includable perception+SLAM+explore+semantic sub-stack
  launch file) and Part C (ingestion-while-driving decision), each with its
  own test line.
- **TF33.8 Part A** (2026-10-23) — `launch/semantic.launch.py`
  (better_launch): `semantic_map_node` with required `map_name` (refuses to
  start without it, since the node's `"unknown"` default would share one
  persistence file across maps) and `publish_every_n`; optional
  `--static_map_odom true` adds the identity `map→odom` for no-SLAM bench
  runs. `setup.py` installs `launch/`; `package.xml` gains
  `exec_depend better_launch`. `test/test_semantic_launch.py` (5 tests,
  fake BetterLaunch, no ROS runtime). Live on the robot: params set,
  `map→odom` published, clean shutdown with map saved. New literate chapter
  `14-semantic_launch.md`.
- **Checkpoint** (2026-10-23) — ruff (via `dome_vision/.ruff-venv`, not
  installed system-wide on the robot) fixed one import-order finding and
  reformatted two test files left over from the 10-22 TF fixes. 135 tests
  pass.
- **TF33.0 hardware runs** (2026-10-21 to 10-23) — first runs on the robot,
  with a static identity `map→odom` instead of SLAM. **Detections → tracker
  → `/semantic/targets` → persisted JSON → restored on relaunch, all
  verified** (two `can` targets at ~(1.32, ∓0.3) in `map`, ~2 Hz with
  `publish_every_n 5`). Two bugs found and fixed, each with a regression
  test (see `chores.md`): `tf_adapter.py` never imported
  `tf2_geometry_msgs`, and the zero-wait TF lookup dropped every detection
  (odometry TF lags 10–150 ms; now waits up to 0.2 s under a
  `MultiThreadedExecutor`). Load was light: load avg ~1.05, 1.2 GiB RAM,
  `dome_vision` ~9% CPU. **Power was the blocker**: repeated undervoltage
  and two brownout crashes on 10-22; details in `power_testing.md`'s results
  log. Only the SLAM re-basing run remains.
- **F34 code** (2026-10-24) — ships `config/semantic_map.yaml` and
  `config/class_profiles.yaml`; the launch always passes them, so PASA runs
  on; `WorldTracker` raises when PASA is on with no profiles. TF34.0–TF34.4
  done; the TF34.5 hardware check is still open.
- **F35 power load test** (2026-11-05, closed) — `tools/power_load_test.sh`
  plus `tools/power_summary.awk` and `power_testing.md` replace
  `power_load_test.md`, `power_system_testing.md` and `dome_vision`'s
  `examples/power_stress_test.py`, which logged the SoC core voltage
  instead of the 5 V input (removed in `dome_vision` c21ad8d). First run:
  all seven stages clean, worst 5.01 V, but with the OAK-D at USB 2. 7 new
  tests; 153 pass.
- **F34 close-out** (2026-11-10) — TF34.5's robot check passed: two `can`
  targets 0.38 m apart at 0.85 m stayed separate with PASA on; rates
  `/oak/detections_3d` 10.0 Hz, `/semantic/targets` 2.0 Hz; `throttled=0x0`.
  Moved to `done/`.
- **F35 USB 3 rerun** (2026-11-09) — OAK-D at USB 3 (10 Hz detection):
  worst 5.14 V, no undervoltage, `throttled=0x0`.
- **`MultiThreadedExecutor` chore** (2026-11-11) — TF on its own node and
  thread; semantic node CPU ~10% of a core, down from 42–48%.
- **RViz marker chore** (2026-11-11) — `CN4`-style labels matching
  `dome_vision`'s image, 8 cm target spheres, no leader line.
- **URDF fix in `dome2`** (2026-11-12) — unblocked TF33.0; see
  `current.md` "Where I got to".

**2026-11-12** — URDF fixed in `dome2` (commit `46a4fe6`, generated from
`dome2/config/dome3.durdf`): camera lens at (0.13, 0, 0.075) tilted 5° down,
lidar at (−0.08, 0, 0.105) yaw −90°. Verified live: `map → camera_link` at
rest (0.130, 0, 0.145), RPY (−95°, 0, −90°). `dome_nav`, `dome` and
`dome_vision` copies updated to match.
