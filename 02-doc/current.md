# Current status

**2026-10-22** — see `02-doc/history.md` for the completed-work log.

## Open

- **Repo state**: `tf2_geometry_msgs` fix committed and pushed 2026-10-22.
  The TF-wait fix (below) and TF33.0 doc fixes are committed, not pushed;
  all 130 tests pass.
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
- **TF33.8–TF33.10** — sub-stack launch integration, Pi CPU measurement,
  docs: not started. TF33.5 superseded by F35 (consumer is `dome_mission`,
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
