# Current status

**2026-11-12**. See `process/02-doc/history.md` for the completed-work log.

## Where I got to

- **URDF fixed 2026-11-12, so TF33.0 is unblocked.** `dome2`'s URDF is now
  generated from `dome2/config/dome3.durdf` with `~/durdf` (commit `46a4fe6`).
  Measured: base_link 7 cm above the floor; camera lens at (0.13, 0, 0.075),
  tilted 5° down (horizon-line calibration; the old rpy rolled the image 8°);
  lidar at (−0.08, 0, 0.105), yaw −90° confirmed from `/scan`. Check with a
  can at 1.00 m, raised so its centre was ~20 cm up: camera
  (1.04, 0.05, 0.199), lidar front face at x 1.02, y ≈ 0.03. `dome_nav`'s sim
  URDF, `dome`'s copy and `dome_vision`'s camera config were updated to
  match (all committed).
- **F33: only TF33.0's SLAM re-basing run is left** of the hardware
  verification. Detections → tracker → publish → persist → restore were all
  verified on 2026-10-23.

## TF33.0 run, 2026-11-10

**Setup**: on battery (not external power), OAK-D at USB 3, real SLAM
(`online_async_launch.py`), `semantic.launch.py --map_name f33slam
--publish_every_n 5`. The commands are in TF33.0's "Remaining" subsection.

**What worked**:

- SLAM came up; `map → camera_link` resolved about 2 s after start.
- Rates: `/oak/detections_3d` 10.0 Hz, `/targets/markers` 2.0 Hz steady
  (max gap 0.54 s).
- Battery 11.71 → 11.69 V over a few minutes; `throttled=0x0`; 5 V rail
  5.20 V; 52.7 °C. `/battery` current reads ~−0.04 A, which is not the
  whole-robot draw (a known `dome2` issue).
- Depth: the can read 1.43–1.45 m against a taped 1.50 m. That's within
  stereo error, and the tape may have gone to the can's centre.

**Why it paused**: the camera and lidar had moved, and the old camera rpy
was wrong (an 8° roll about the optical axis). Both fixed 2026-11-12; see
"Where I got to".

**Findings to act on**:

- **One can is detected as both `can` and `cup`** at the same 3D point
  (`can` 0.91; `cup` 0.38–0.8, near `dome_vision`'s 0.35 cutoff). The
  label-constrained tracker makes two targets. The cup detection comes and
  goes, so its target is lost and re-created again and again; that's the
  "markers blink" effect, and why IDs reached T11 with one can in view.
  The fix belongs in `dome_vision`: suppress overlapping boxes across
  classes. Quick test: `ros2 param set /dome_vision confidence 0.7`.
- **The map forgets targets out of view.** Lost targets (5 s unseen) are
  dropped from `/semantic/targets` and the markers; after 30 s
  (`remove_timeout_s`) they're deleted. That doesn't fit go-to-label. A fix
  changes the spec, so it would be a new feature.
- **`f34test.json` is still empty** (`{"targets": []}`, dated Nov 9), even
  though TF34.5 saw two cans on Nov 10. Check the save on a clean shutdown
  of this run (`f33slam.json`).
- **Semantic node CPU 42–48% of a core:** fixed; ~10% on the robot
  (2026-11-11). See `history.md`.

## Open

- **Repo state**: checkpoint 2026-11-12. F34's close-out, the
  `MultiThreadedExecutor` and RViz-marker chores are committed. 160 tests
  pass and ruff is clean. ruff isn't installed on the robot; use
  `~/ros2_ws/src/dome_vision/.ruff-venv/bin/ruff`.
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
- **RViz markers** (`CN4` labels, 8 cm spheres) are built but not yet looked
  at in RViz.

## Next steps, in order

1. **Rerun TF33.0's SLAM re-basing run** on the fixed URDF (TF33.0
   "Remaining" subsection). Confirm `f33slam.json` is written on shutdown.
   Look at the new RViz markers during the run.
2. **Then** TF33.8 Parts B/C, TF33.9 (Pi CPU), TF33.10 (docs). Decide
   whether the "map forgets out-of-view targets" fix becomes a feature, and
   raise the can/cup double label in `dome_vision`.
3. **Approve or revise `dome_vision` F70/F71** once TF33.0 passes.

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
