# Current status

**2026-11-05**. See `process/02-doc/history.md` for the completed-work log.

## Where I got to

- **F35 power load test: done.** `tools/power_load_test.sh` works on the
  robot. The first run was clean (worst 5.01 V, no undervoltage), but **the
  OAK-D was at USB 2**, so it wasn't the worst case. Results are in
  `power_testing.md`.
- **F34 tracker config: code done, robot check (TF34.5) not run.**
- **F33: only TF33.0's SLAM re-basing run is left** of the hardware
  verification. Detections → tracker → publish → persist → restore were all
  verified on 2026-10-23.

## Open

- **Repo state**: checkpoint 2026-11-05. F34 and F35 are committed and
  pushed, along with `dome_vision` and `dome2`. 153 tests pass and ruff is
  clean. ruff isn't installed on the robot; use
  `~/ros2_ws/src/dome_vision/.ruff-venv/bin/ruff`.
- **Robot hardware state**:
  - The external USB hub is gone; the OAK-D plugs straight into the Pi.
  - **The OAK-D only connects at USB 2** (kernel: "new high-speed", bus 4).
    Its last USB 3 connection was through the hub, on 2026-10-24.
  - The UPS's I2C isn't connected yet, so `/telemetry/battery` doesn't
    publish and the power test records no pack voltage.
  - Wi-Fi is on 5 GHz, to avoid USB 3 interference.
  - The 5 V rail reads 5.1–5.2 V at idle, up from ~5.0 V in October.

## Next steps, in order

1. **Get the OAK-D onto USB 3**: the other blue port, the plug fully seated,
   or another cable. Check with `journalctl -k | grep -iE "new .*speed"`;
   you want "SuperSpeed" on `usb 3-` or `usb 5-`.
2. **Rerun the power test** at USB 3 and add the result to `power_testing.md`.
3. **TF34.5**: F34's demo, with two cans 0.5 m apart. Expect two targets and
   `/targets/assoc_diag` publishing.
4. **Commit**: run `/checkpoint` first (tests, ruff, literate docs).
5. **TF33.0's last part**: run real SLAM to exercise re-basing.
   slam_toolbox's `online_async_launch.py` directly, not
   `robot_map.launch.py`, which also starts Nav2.
6. **Then** TF33.8 Parts B/C, TF33.9 (Pi CPU), TF33.10 (docs).

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
