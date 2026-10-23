# Current status

**2026-10-23** — see `process/02-doc/history.md` for the completed-work log.

## Open

- **Repo state**: committed and pushed 2026-10-23 at checkpoint; 135 tests
  pass, ruff clean. **Pack on the charger** (10.6 V, 181 dips this boot —
  see 2026-10-23 power notes below); no hardware runs until it's full.
- **Run the semantic node with** `bl dome_semantic semantic.launch.py
  --map_name <name> [--static_map_odom true]` (TF33.8 Part A, see
  `history.md`).
- **Next actual step: TF33.0, real-hardware verification** (see task file for
  the full bottom-up procedure and per-component launch/diagnostic commands).
  TF33.1-TF33.6 are done (msgs, tracker port, map-frame TF + re-basing, typed
  publishing, persistence) but have never been run against real OAK-D
  hardware — only unit-tested. No combined launch file exists yet (that's
  TF33.8, not started). **Now running on the robot** (confirmed 2026-08-27:
  OAK-D present via `lsusb`) — TF33.0 is in progress.
- **TF33.7 (fake detection producer) — designed, deferred.** Full design
  exists (a pure `fake_scenario.py` scenario model — object list + Gaussian
  noise + seeded dropout — plus a `tools/fake_detections.py` live publisher
  mirroring `dome_mission/tools/nav_intent_check.py`, plus a smoke test),
  verified against `WorldTrackerConfig`'s actual confirmation thresholds.
  Deferred because it's "too much" until TF33.0 shows whether it's actually
  needed — the design lived in a local plan file on the prior VM session and
  was not committed; re-derive or ask if it turns out to be needed after all.
- **Options while the pack charges**: TF33.7 (fake producer — recommended,
  bench-tests detections→tracker→publish→persist with Part A's launch and
  no OAK-D) or wait. Not yet chosen.
- **TF33.8 Parts B/C, TF33.9–TF33.10** — sub-stack launch integration,
  ingestion-gating decision, Pi CPU measurement, docs: not started. TF33.5 superseded by F35 (consumer is `dome_mission`,
  not this package).

## TF33.0 progress — 2026-10-21

### Power: brownouts on the robot

- **The robot crashed during the previous TF33.0 attempt** (boot ended
  11:24:29). The kernel log shows repeated `Undervoltage detected!` starting
  ~40 s after the OAK-D enumerated, ending on an undervoltage line with no
  shutdown — a brownout, not a software crash.
- **Still dipping this boot**: 6 undervoltage events 11:30–11:43, and
  `vcgencmd get_throttled` = `0x50000`. Pi 5V input reads 4.93 V at rest, so it
  sags under load spikes.
- **Battery was low**: 10.65 V under load. The two battery topics disagree on
  percent (`/battery` from the ESP32 firmware says 22%, `/telemetry/battery`
  says 51.8%) because they use different SoC formulas — trust voltage.
- **Plan**: one more semantic-node attempt now, then recharge. If dips continue
  on a full pack, suspect the 5V converter/wiring or power the OAK-D separately.
  Watch live with `journalctl -kf | grep -i voltage`.

### Power: two more brownouts — 2026-10-22 evening

- **Two boots today ended on an `Undervoltage detected!` line** with no
  shutdown, panic, or OOM: one ~17:20, one at 19:57:26.
- **19:57 crash sequence**: 7 dips 19:38–19:40 (each recovered in 2–4 s),
  17 quiet minutes, then at 19:57:25 the OAK-D dropped off USB and
  re-enumerated as SuperSpeed (USB 3) — then the undervoltage, and the log
  ends.
- **Not a manual power-cycle**: the robot rebooted on its own (confirmed).
  The SSH "lost communication" feel was a separate Wi-Fi issue — power save
  was on; now off via `/etc/udev/rules.d/70-wifi-powersave.rules`.
- **Likely trigger**: a pipeline (re)start. The OAK's firmware boot plus the
  switch to USB 3 is a current spike that pulls the Pi's 5 V below brownout.
- **Not related**: the kernel `WARNING ... get_throttled_show` at 19:56:36 is
  `battery_telemetry` reading a deprecated sysfs file — noise, not a fault.
- **Open question**: low battery (pack drained since the 11.27 V morning run)
  vs. a 5 V converter/wiring limit. The voltage at crash time isn't in the
  journal.
- **Next**:
  - Check the pack voltage; recharge if it's around 11 V or lower.
  - If dips continue on a full pack, power the OAK-D separately (powered hub
    or its own power input), or check the converter's rating — Pi 5 plus the
    OAK-D at startup needs about 5 A.
  - Start the OAK-D last while watching `journalctl -kf | grep -i voltage`.
- **Test procedure**: see `process/02-doc/power_system_testing.md`.

### Power: low pack, rerun postponed — 2026-10-23

- **181 undervoltage events this boot**, the first at 14:10 and a burst of
  8 between 17:37:09 and 17:38:31. `get_throttled` = `0x50000` (dips earlier
  in the boot, none at the moment of reading).
- **The OAK-D kept reconnecting**: it dropped off USB at 17:38:31, the same
  second as the last dip, and its USB ID appeared 39 times this boot (now
  device number 35).
- **Pack low**: 10.54 V on `/battery`, 10.62 V on `/telemetry/battery`
  (whose 50.8% is wrong for this pack again). It was 11.27 V on the clean
  10-22 morning run. At idle the 5 V rail reads 5.00 V and the robot draws
  7.5 W.
- **Conclusion**: a low pack is the most likely cause. The semantic-node
  rerun is postponed and the pack is on the charger.
- **Next**: charge to ~12.6 V, reboot (clears `get_throttled`), rerun with
  the OAK-D started last. If it still dips on a full pack, suspect the 5 V
  converter/wiring.

### Launch changes affecting step 1

- `drivers` **no longer starts battery telemetry**; it is now its own `battery`
  subsystem in `dome2/robot.launch.py`. Yellow Pad joystick is `yellow`.
- Step 1 is now `bl dome2 robot.launch.py --options "d b"`.

### Run results — 2026-10-22 (low-drain setup)

**Setup used** — chosen to minimize battery drain; no Nav2, no SLAM:

- `bl dome2 robot.launch.py --options "d b"` (drivers + battery)
- OAK-D via `dome_vision_ros.launch.py --depth true` (task file step 2)
- **Static identity `map→odom`** instead of SLAM:
  `ros2 run tf2_ros static_transform_publisher --frame-id map --child-frame-id odom`.
  Exercises detections→map→tracker→publish; skips re-basing (map never jumps).
- Semantic node: run from `~/ros2_ws` (from the package dir `ros2 run` said
  "Package not found"), `-p map_name:=tf33test -p publish_every_n:=5`.

**Findings so far**:

- **Power fine this time**: battery 11.27 V, `get_throttled=0x0`, no
  undervoltage events.
- **Load is light**: load avg ~1.05 on 4 cores, 1.2 GiB of 15 GiB RAM,
  58 °C. `dome_vision` ~9% CPU / 300 MB (inference is on the OAK). OAK 9.9 fps.
- `map→camera_link` resolves via `tf2_echo` once the static TF is up.
- **Bug found and fixed**: the node crashed on its first detection with
  `TypeException: PointStamped is not loaded or supported` — `tf_adapter.py`
  never imported `tf2_geometry_msgs`; mocked unit tests hid it. Fixed with a
  real-Buffer regression test (chores.md).
- **Not yet verified**: node running stable after the fix, confirmed targets
  on `/semantic/targets` with an object in view, persisted JSON on shutdown.
  Only empty `/oak/detections_3d` arrays were sampled so far.
- **Second bug found and fixed**: every detection was dropped
  as a TF extrapolation error — odometry TF lags 10-150 ms behind detection
  stamps, and the lookup used zero wait. `tf_adapter.py` now waits up to
  0.2 s, and the node spins in a `MultiThreadedExecutor` (the TF listener's
  own reentrant callback group keeps receiving while a callback waits).
  Regression test added (chores.md). Not yet re-run on the robot.

### Doc errors — fixed in the TF33.0 task file

- Step 1 is now `--options "d b"`; step 3 now uses slam_toolbox's
  `online_async_launch.py` directly (`robot_map.launch.py` also starts Nav2),
  with the static identity `map→odom` as the no-SLAM option; step 4 notes
  running from `~/ros2_ws`.

### Telemetry plotting

- RViz can't plot scalars. PlotJuggler (laptop) only shows `/telemetry/*` if
  the laptop has `dome_telemetry_msgs` built and sourced; Foxglove WebSocket
  needs nothing on the laptop. Either is light on the Pi for scalar topics —
  only image/pointcloud subscriptions load it.

## Session note

Next: rerun the semantic node with an object in view and finish the
"Not yet verified" items above, then try real SLAM (slam_toolbox without
Nav2) to exercise re-basing. TF33.0's findings determine whether TF33.7/TF33.8 are still the right next tasks or
need rethinking.
