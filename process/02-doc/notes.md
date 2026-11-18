# Notes

Semi-permanent project notes — durable architecture decisions that don't
belong in a feature/task file and would get lost in `current.md`'s churn.

## Dependency discipline

`WorldTracker`'s pure closure needs `pydantic`, `pyyaml`, `numpy` — all
already present in the workspace Python environment, no new system deps.
It deliberately does **not** need `torch`/`torchvision`/`cv2`: those belong to
`dome_vision`'s `EmbeddingExtractor` (image embedding inference), which never
moved here. This package only ever *compares* embedding vectors
(`embedding_similarity.cosine_sim`), never *extracts* them.

## Watch list: dome_vision features targeting the ported code (resolved)

**Resolved 2026-11-13 by `dome_vision` F71**, which deleted that repo's copy of
the tracker (`world_tracker.py`, `semantic_map_node.py`, `tf_adapter`, class
profiles). **This package is now the only semantic map.**

- `dome_vision` F39, F40, F56 and F57 (merge pass, `/odom_raw` stopped
  detection, `WorldTracker` split, target data model) never landed there and
  are moot. Re-author them here if still wanted; **F39's merge idea is
  already done** by F36's `target_merge.py`.
- `dome_control`'s `behavior_manager` and `dome_vision`'s image node now read
  this package's `config/class_profiles.yaml` and `/semantic/targets`, so
  changes to either reach them.

## Bag replay of a drive (TF36)

Used to compare tracker changes on identical TF and detections, so SLAM's
run-to-run variance drops out.

**Record** on the robot, with drivers, OAK-D detection only and real SLAM
running (the recorder subscribes to `/oak/detections_3d`, so the vision node
runs inference even without the semantic node):

```
ros2 bag record -o ~/bags/<name> /tf /tf_static /oak/detections_3d /odom /scan
```

**Replay** with the live stack stopped (no drivers, SLAM or vision — the bag
supplies their TF). Use a fresh `map_name` each time, so nothing is restored
from an earlier save. Three terminals, from `~/ros2_ws`:

```
ros2 run dome_semantic semantic_map_node --ros-args -r __node:=semantic_map \
  -p use_sim_time:=true -p map_name:=<replay_name> \
  -p class_profile_path:=$(ros2 pkg prefix dome_semantic)/share/dome_semantic/config/class_profiles.yaml \
  --params-file $(ros2 pkg prefix dome_semantic)/share/dome_semantic/config/semantic_map.yaml
ros2 bag record -o ~/bags/<replay_name> /semantic/targets
ros2 bag play ~/bags/<name> --clock
```

Stop the recorder and the node once play ends.

## Tracker facts worth knowing

- **Persistence is keyed only by `--map_name`.** Reusing a name with a fresh
  SLAM map silently restores targets in a dead frame. Use a fresh name per
  run; the node logs nothing on restore, only on save.
- **IDs count potentials, not targets** (`world_tracker.py`), so a high
  number like `CN51` after a few minutes is noise candidates, not 51
  confirmed targets.
- **Depth goes bad on a can at ~2.6 m** (~0.6 m error; `dome_vision` I04),
  so robot runs face targets from within ~1.5 m.
- A map that is mostly −1 is normal: unseen cells inside SLAM's bounding box.

## Robot hardware state

- The OAK-D plugs straight into the Pi (no hub). **It reaches USB 3 only in
  the bus 2/3 blue port**; the bus 4/5 blue port falls back to USB 2.
- Check the speed only after firmware loads (`03e7:f63b`). The unbooted
  bootloader (`03e7:2485`) always shows 480M.
- The UPS's I2C isn't connected yet, so `/telemetry/battery` doesn't publish
  and the power test records no pack voltage.
- Wi-Fi is on 5 GHz, to avoid USB 3 interference. Wi-Fi power save is off,
  via `/etc/udev/rules.d/70-wifi-powersave.rules`.
- The 5 V rail reads 5.1–5.2 V at idle, up from ~5.0 V in October.
- **ruff and uv aren't installed on the robot.** Use
  `~/ros2_ws/src/dome_vision/.ruff-venv/bin/ruff`.

## Robot run procedure (TF36.7 shape)

**Setup**: one can only, no others nearby. Stop everything, then place the
robot **1.0 m from the can, facing it** (wheel axle midpoint to can
centre). Start fresh so the robot is at map (0, 0); the tape point is then
map (1.0, 0.0). Confirm the start yaw from the bag.

**Terminals**, each from `~/ros2_ws`, in order (`<name>` is a fresh map
name; bags already on the robot are `f36drive`, `f36replay_*`, `f36run`,
`f36run3`, `f36run5`, `f36run6`):

```
bl dome2 robot.launch.py --options "d b"
bl dome_nav robot_map.launch.py --map_name <name>
bl dome_vision_ros dome_vision_ros.launch.py --config "$DOME_VISION_CONFIG" --depth true
bl dome_semantic robot.launch.py --map_name <name>
ros2 bag record -o ~/bags/<name> /tf /tf_static /oak/detections_3d /odom /scan /semantic/targets
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

**Drive**: hold 10 s facing the can. Three loops, each with the can out of
view for over 30 s, then face it again **from within ~1.5 m** and hold 10 s.
Finish facing it at ~1 m, hold 10 s.

**Stop in this order**: semantic launch first (it saves the map), then the
bag, then the rest. Claude reads `~/.dome/semantic_maps/<name>.json` and
the bag directly.

**Harmless startup noise**: `RTPS_TRANSPORT_SHM ... port7006`, early
`Message Filter dropping message: frame 'laser'`, and `Legacy map export
failed` from `slam_manager`'s one-off `map_saver`.

**Teleop stutters** (moves ½ s, pauses, goes): firmware stops the motors
after 200 ms with no command
(`~/linorobot2_hardware/firmware/src/firmware.cpp:202`), and the VMware text
console's key repeat is slow and uneven. **Not fixing it** (a relay was
rejected as too hairy); a gamepad with `joy_teleop`, or SSH from a real
desktop terminal, avoids it. It doesn't affect the test.

## Commands

From `~/ros2_ws`:

```
src/dome_semantic/tools/power_load_test.sh [--hold 60]
src/dome_semantic/tools/power_load_test.sh --report ~/power_tests/<run>
bl dome2 robot.launch.py --options "d b"          # drivers + battery
bl dome_vision_ros dome_vision_ros.launch.py --config "$DOME_VISION_CONFIG" --depth true
bl dome_semantic robot.launch.py --map_name <name> [--static_map_odom true]
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
- The two battery topics disagree on percent. Trust the voltage.
- RViz can't plot scalars. Use Foxglove (nothing needed on the laptop) or
  PlotJuggler (needs `dome_telemetry_msgs` built on the laptop).
- **If the semantic node stops publishing** (seen once, 2026-11-12: input at
  8 Hz, no output, threads on futexes), don't kill it; take a stack dump
  (`py-spy` isn't installed yet).
