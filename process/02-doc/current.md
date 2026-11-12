# Current status

**2026-11-12, evening**. See `process/02-doc/history.md` for the
completed-work log.

## Where I got to

- **TF33.0's SLAM re-basing run failed on 2026-11-12, and the cause is the
  re-basing design.** The same unmoved can comes back 0.36 m off after a
  loop, so it gets a new ID each time. See "TF33.0 run, 2026-11-12".
- **F36 (approved 2026-11-12) is the fix**: drop global re-basing, widen
  can re-association, add a same-label merge pass, and keep out-of-view
  targets. TF33.0 stays open until a re-run passes with F36.
- **URDF fixed 2026-11-12**; see `history.md`.

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

- **Repo state**: checkpoint 2026-11-12 (evening). Docs only since the
  last commit: the TF33.0 run write-up, F36/TF36 (approved), two proposed
  chores, bag replay notes. 160 tests pass and ruff is clean. ruff isn't
  installed on the robot; use `~/ros2_ws/src/dome_vision/.ruff-venv/bin/ruff`.
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
- **Semantic node stopped publishing once** on 2026-11-12, not reproduced.
  If it recurs, keep it running and take a stack dump (`py-spy` isn't
  installed yet).

## Next steps, in order

1. **F36 approved 2026-11-12. Next: TF36.0, record the drive bag** on the
   robot (commands in `notes.md`, "Bag replay of a drive"). Restart the whole
   stack first so the robot starts at map (0, 0); tape the distance from the
   wheel axle midpoint to the can's centre, straight ahead. Hold 10 s, then
   2–3 loops with the can out of view for over 30 s. A throwaway
   `/semantic/targets` bag summarizer was written in session scratch; re-create
   it for the replay (one row per ID: pose, obs count, time seen, tape error).
2. **Build F36, then rerun TF33.0's SLAM run** with it. Pass: the same can
   keeps its ID, or lands within the new radius, across loops.
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
