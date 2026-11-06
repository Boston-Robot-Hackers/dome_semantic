# TF35 Power load test for Feature F35

Task file name must be `TFNN-<slug>.md` where `NN` matches the feature number.

Each step is numbered `TFNN.N`, matching this file's own `TFNN` (e.g. `TF03.0`,
`TF03.1`, ...), starting at `.0`.

For each task step, add a test when feasible. If not feasible, note why.

## TF35.0 — Script skeleton: preflight, run dir, monitors, cleanup

**Status**: done (2026-11-05). `shellcheck` isn't installed, so only `bash -n` ran

**Description**: Create `tools/power_load_test.sh` (bash).

- **Preflight**, failing with a clear message:
  - the current directory is a workspace (`install/setup.bash` exists)
  - `vcgencmd`, `bl` and `stress-ng` are on the path
  - `$DOME_VISION_CONFIG` is set
  - the OAK-D shows in `lsusb` (`03e7`)
- **Run dir** `~/power_tests/<YYYY-MM-DD_HHMMSS>/`. A `stage` file holds the
  current stage name, which every monitor stamps on its lines.
- **Monitors** started in the background, one log each:
  - `rail.log`: `EXT5V_V` and `get_throttled`, every 0.2 s
  - `kernel.log`: `journalctl -kf` lines matching voltage or USB, also echoed
    to the terminal
  - `wifi.log`: one ping to the gateway each second
- **Cleanup trap** on exit and Ctrl-C: stop stages newest first (SIGINT, a
  wait, then SIGTERM to the process group), then stop the monitors.

*Test*: `bash -n` passes, and `shellcheck` is clean when installed. The
preflight exits non-zero with a message when run outside a workspace.

## TF35.1 — Stages

**Status**: done (2026-11-05), verified by the TF35.5 run

**Description**: Run the seven stages in F35's order, each held for `--hold`
seconds (default 30). Each launch runs under `setsid`, so it can be stopped
as one process group, and writes its output to `procs/<stage>.log`.

- At the end of each stage, record the pack voltage and power from
  `/telemetry/battery`, using `ros2 topic echo --once --field` with a timeout.
- After the OAK stage, record the OAK-D's line from `lsusb -t`, and warn when
  it shows `480M` (USB 2 fallback).
- After the subscriber stage, record the detection rate from
  `ros2 topic hz /oak/detections_3d`.

*Test*: not feasible off the robot. The stages start real hardware, so
TF35.5 covers them.

## TF35.2 — Per-stage summary and `--report`

**Status**: done (2026-11-05)

**Description**: An awk summary, by stage, over `rail.log`, `kernel.log` and
`wifi.log`:

- lowest and mean `EXT5V_V`
- samples below 4.8 V
- throttle-value changes
- kernel undervoltage and USB event counts
- worst ping

The script prints it after each stage and writes it all to `summary.txt` at
the end. `--report <dir>` runs the same summary on an earlier run's logs.
This works even when that run crashed partway, possibly mid-line.

*Test*: TF35.4's fixture tests.

## TF35.3 — The doc: `process/02-doc/power_testing.md`

**Status**: done (2026-11-05)

**Description**: One doc that replaces both old ones:

- before you start
- running the script, and `--report` after a crash
- reading the numbers
- the manual checks: multimeter at three points, and the wiggle test
- known problems
- **the results log carried over from `power_system_testing.md`**, plus a
  2026-11-05 entry (hub removed, OAK-D not detected, then seen at USB 2,
  Wi-Fi moved to 5 GHz)

*Test*: none. It's prose; reviewing it is the check.

## TF35.4 — Tests

**Status**: done (2026-11-05): 7 tests pass

**Description**: The feature's dedicated test task. Add
`test/test_power_load_test.py`, which runs the script with `subprocess`:

- `--report` on fixture logs prints the correct minimum, mean, count below
  4.8 V, and event counts per stage.
- `--report` on a log cut off mid-line, as a crash leaves it, still
  summarizes.
- `--report` on a directory that doesn't exist exits non-zero.
- The preflight fails outside a workspace.
- `bash -n` passes on the script.

*Test*: this step is the test.

## TF35.5 — Hardware run on the robot

**Status**: done (2026-11-05). The battery reading went untested: the UPS's I2C isn't connected yet, and the script logged `pack=no_reading` as designed

**Description**: Run F35's demo on battery, with the charger unplugged, and
add the results to the doc's results log.

*Test*: manual and hardware-only. The entry records the command, setup,
per-stage readings, and outcome.

## TF35.6 — Delete the old tooling

**Status**: done (2026-11-05). `dome_vision` commit c21ad8d deletes the script and repoints `load-reduction.md`. TF69.1's reference was updated too, but left uncommitted with the rest of TF69

**Description**:

- Delete `process/02-doc/power_load_test.md` and
  `process/02-doc/power_system_testing.md`.
- Point `current.md`'s references at `power_testing.md`.
- In the `dome_vision` repo, delete `dome_vision/examples/power_stress_test.py`
  and fix any references to it, as a separate commit there.

*Test*: `grep` finds no remaining references to the deleted files in either
repo.
