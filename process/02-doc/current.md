# Current status

**2026-11-13**. See `process/02-doc/history.md` for the completed-work log.

## Where I got to

- **Paused 2026-11-13 mid TF36.7 re-run** to charge the battery; resume
  from "Next steps", step 1.
- **TF36.0 done 2026-11-13**: drive bag recorded and replayed through the
  current node. **The can's new ID came from the remove timeout, not
  drift.** See "TF36.0 bag replay, 2026-11-13".
- **TF33.0's SLAM re-basing run failed on 2026-11-12, and the cause is the
  re-basing design.** The same unmoved can comes back 0.36 m off after a
  loop, so it gets a new ID each time. See "TF33.0 run, 2026-11-12".
- **F36 (approved 2026-11-12) is the fix**: drop global re-basing, widen
  can re-association, add a same-label merge pass, and keep out-of-view
  targets. TF33.0 stays open until a re-run passes with F36.
- **URDF fixed 2026-11-12**; see `history.md`.

## TF36.7 robot run, 2026-11-13

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

## TF36.0 bag replay, 2026-11-13

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

## TF36.2 replay without re-basing, 2026-11-13

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

## Replay with TF36.3 + TF36.4 (0.4 m radius, merge pass), 2026-11-13

`~/bags/f36replay_merge`: **23 IDs** (25 without them). In the cluster,
can IDs drop from 6 to 4 and settle into **two cans ~0.45 m apart**, near
(0.65, −0.95) and (0.9, −0.45), so 0.4 m keeps them separate.

- **Every remaining can duplicate is a deleted-then-re-seen case**:
  T38 is 0.12 m from T17 and T33 is 0.11 m from T18, but T17/T18 were
  removed 30 s after going lost, before the newcomer confirmed. Same for
  the taped can (T1 → T21). **TF36.5 should collapse all of these.**
- Merges inside a visibility window work: e.g. old T21 folded into T17.

## Replay with all of TF36.1–TF36.5, 2026-11-13

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

## TF33.0 run, 2026-11-12

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

## TF33.0 run, 2026-11-10 (still open)

- **One can was detected as both `can` and `cup`** at the same point, making
  two targets and blinking markers. Not seen on 11-12. The fix belongs in
  `dome_vision` (cross-class box suppression); quick test:
  `ros2 param set /dome_vision confidence 0.7`.
- Depth read 1.43–1.45 m against a taped 1.50 m: within stereo error.

## Open

- **RESUME HERE (paused 2026-11-13 to charge the battery)**: TF36.7
  re-run. Check `~/bags/f36run3` first (recorded mid-session, may be
  partial), then follow "TF36.7 re-run procedure" with map name
  `f36run4`. See "Next steps", step 1.
- **Repo state**: F36 TF36.0–TF36.6 committed 2026-11-13, literate docs
  refreshed (chapter 09 is now `target_merge`). 153 tests pass and ruff is
  clean. ruff isn't installed on the robot; use
  `~/ros2_ws/src/dome_vision/.ruff-venv/bin/ruff`.
- **Bags on the robot**: `~/bags/f36drive` (drive, TF36.0) and the replays
  `f36replay_before`, `_after`, `_merge`, `_keep`.
- **Robot hardware state**:
  - The external USB hub is gone; the OAK-D plugs straight into the Pi.
  - **The OAK-D connects at USB 3 only in the bus 2/3 blue port.** The
    other blue port (bus 4/5) falls back to USB 2. Keep it in bus 2/3.
  - Check the speed only after firmware loads (`03e7:f63b`). The unbooted
    bootloader (`03e7:2485`) always shows 480M.
  - The UPS's I2C isn't connected yet, so `/telemetry/battery` doesn't
    publish and the power test records no pack voltage.
  - Wi-Fi is on 5 GHz, to avoid USB 3 interference.
  - The 5 V rail reads 5.1–5.2 V at idle, up from ~5.0 V in October.
- **Two `semantic_map` nodes run together**: `dome2`'s vision launch still
  starts `dome_vision`'s old one beside ours. `dome_vision` F71 (drafted,
  not approved) retires it; its gate is TF33.0's SLAM run.
- **RViz markers** were seen on 2026-11-12: they work but are nearly
  invisible at map zoom (proposed chore).
- **`dome2` issues found on 2026-11-12**: odometry drifts a lot (SLAM
  corrected 1 m and 25° in one session), and the EKF once stalled for
  10.65 s. Raise both in `dome2`.
- **`/cmd_vel` type mismatch** found 2026-11-13: `collision_monitor`
  publishes `TwistStamped`, `gendrv` subscribes `Twist`. **Cause**:
  `dome_nav`'s `nav2_params_real.yaml` (loaded by `robot_map.launch.py`)
  lacks `enable_stamped_cmd_vel: false`, which the explore params files
  already set for Kilted. Also missing in `nav2_params_localization_real.yaml`
  and `nav2_params_explore_real_mini.yaml`. Fix in `dome_nav`.
- **Nav2 `bt_navigator` dies at startup** (2026-11-13, Kilted): params
  still set `error_code_names`, which must be replaced by
  `error_code_name_prefixes`. Nav2 navigation is down until `dome_nav`'s
  params are fixed; teleop is unaffected. Raise in `dome_nav`.
- **Semantic node stopped publishing once** on 2026-11-12, not reproduced.
  If it recurs, keep it running and take a stack dump (`py-spy` isn't
  installed yet).

## Next steps, in order

1. **Resume here: TF36.7 re-run (= TF33.0 re-run).** TF36.0–TF36.6 are
   done and committed (`453ad90`). The first robot run (`f36run`) passed
   for the tracker but the taped can also became T27 from depth error at
   ~2.6 m (see "TF36.7 robot run"). **Before re-running, check
   `~/bags/f36run3`** (recording started 11:29 on 11-13, session ended
   mid-run): if it holds three full loops, analyze it instead of
   re-running. **Use the next unused name, `f36run4`**: `f36run2`/`f36run3`
   already have SLAM pose graphs and bags, and reusing a name restores them.
   See "TF36.7 re-run procedure" below.
2. **Then**: write the result up, close TF36.7 (and TF33.0 if it passes),
   close F36 with `/close-feature 36`. Raise in `dome_vision`: depth error
   on small objects past ~2 m, and the can/cup double label.
3. **Build the rest of F36, then rerun TF33.0's SLAM run** with it. Pass:
   the same can keeps its ID, or lands within the new radius, across loops.
   Drive 2–3 real passes past the can this time.
3. **Then** TF33.8 Parts B/C, TF33.9 (Pi CPU), TF33.10 (docs). Raise the
   can/cup double label and the 10 s EKF stall in their own packages.
4. **Approve or revise `dome_vision` F70/F71** once TF33.0 passes.

**Planned: move the power testing to `dome2`.** It covers the whole robot,
not the semantic map. Move `tools/power_load_test.sh`,
`tools/power_summary.awk`, `test/test_power_load_test.py` and
`process/02-doc/power_testing.md`. Then drop the "Support tooling" section
from `spec.md`, and update the paths in `dome_vision`'s `current.md`,
`load-reduction.md` and TF69.1. Check `dome2`'s process rules first, to see
whether this needs a feature there.

**TF33.7 (fake detection producer)** is designed but deferred. Build it
only if hardware stays unavailable. The design was never committed, so
re-derive it.

## TF36.7 re-run procedure

**Setup**: one can only, no others nearby. Stop everything, then place the
robot **1.0 m from the can, facing it** (wheel axle midpoint to can
centre). Start fresh so the robot is at map (0, 0); tape point is then map
(1.0, 0.0) — confirm the start yaw from the bag.

**Terminals**, each from `~/ros2_ws`, in order:

```
bl dome2 robot.launch.py --options "d b"
bl dome_nav robot_map.launch.py --map_name f36run4
bl dome_vision_ros dome_vision_ros.launch.py --config "$DOME_VISION_CONFIG" --depth true
bl dome_semantic semantic.launch.py --map_name f36run4
ros2 bag record -o ~/bags/f36run4 /tf /tf_static /oak/detections_3d /odom /scan /semantic/targets
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

**Drive**: hold 10 s facing the can. Three loops, each with the can out of
view for over 30 s, then face it again **from within ~1.5 m** (depth went
bad at ~2.6 m) and hold 10 s. Finish facing it at ~1 m, hold 10 s.

**Stop in this order**: semantic launch first (it saves the map), then the
bag, then the rest. Claude reads `~/.dome/semantic_maps/f36run4.json` and
the bag directly.

**Pass**: one can ID through all loops, no second can ID, position within
0.4 m of first recorded.

**Startup noise that is harmless**: `RTPS_TRANSPORT_SHM ... port7006`,
early `Message Filter dropping message: frame 'laser'`, and
`Legacy map export failed` from `slam_manager`'s one-off `map_saver`.

**Teleop stutters** (moves ½ s, pauses, goes): firmware stops the motors
after 200 ms with no command (`~/linorobot2_hardware/firmware/src/firmware.cpp:202`),
and the VMware text console's key repeat is slow and uneven (measured
~500 ms first gap, gaps up to ~940 ms). GNOME settings don't apply on a
`tty`. **Not fixing it** (a relay was rejected as too hairy); a gamepad
with `joy_teleop`, or SSH from a real desktop terminal, avoids it. It
doesn't affect the test.

## Commands

From `~/ros2_ws`:

```
src/dome_semantic/tools/power_load_test.sh [--hold 60]
src/dome_semantic/tools/power_load_test.sh --report ~/power_tests/<run>
bl dome2 robot.launch.py --options "d b"          # drivers + battery
bl dome_vision_ros dome_vision_ros.launch.py --config "$DOME_VISION_CONFIG" --depth true
bl dome_semantic semantic.launch.py --map_name <name> [--static_map_odom true]
```

## Gotchas from the robot runs

- **Run `ros2 run` from `~/ros2_ws`.** From the package directory it says
  "Package not found".
- **`bl` with no TTY prints `Aborted!`**, but the launch still runs.
- **Stop launches, not nodes.** Killing only the semantic node leaves its
  static TF publisher running.
- **`/oak/detections_3d` needs a subscriber**, or the vision node never runs
  inference.
- A transient "Dropped N detection(s): no TF" at startup is harmless. The
  node is just ahead of its own static TF.
- The node logs nothing when it restores targets; it logs only on save.
- The two battery topics disagree on percent. Trust the voltage.
- RViz can't plot scalars. Use Foxglove (nothing needed on the laptop) or
  PlotJuggler (needs `dome_telemetry_msgs` built on the laptop).
- Wi-Fi power save is off, via `/etc/udev/rules.d/70-wifi-powersave.rules`.
