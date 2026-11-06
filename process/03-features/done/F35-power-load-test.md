# Feature description for feature F35

Feature file name must be `FNN-<slug>.md` where `NN` matches the feature number.

# F35 — Power load test: one script, one doc

**Priority**: High

**Done:** yes

**Tasks File Created:** yes

**Tests Written:** yes

**Test Passing:** yes

**Description**: The robot browns out when the OAK-D starts. Brownouts block
TF33.0. The current tooling to diagnose this has errors:

- `power_stress_test.py` (in `dome_vision`) logs the SoC core voltage, not the
  5 V input, and ignores USB events.
- `power_system_testing.md` and `power_load_test.md` overlap and disagree.

This feature replaces all three with **one script and one doc**.

### The script: `tools/power_load_test.sh`

- **Run from `~/ros2_ws`, in one terminal window.** It sources the
  workspace, checks its preconditions, and fails loudly when one is missing.
- **Adds load one stage at a time**, holding each stage for a set time:
  1. idle
  2. base robot (`dome2`, drivers + battery)
  3. CPU stress (`stress-ng`)
  4. OAK stack (`dome_vision_ros`, depth on)
  5. a detections subscriber, so inference actually runs
  6. the semantic node (static map→odom)
  7. CPU stress again, with everything running
- **Watches throughout**, in the background:
  - the Pi 5 V rail (`EXT5V_V`) and `get_throttled`, every 0.2 s
  - kernel undervoltage and USB events, shown live
  - Wi-Fi latency to the gateway
  - pack voltage and power from `/telemetry/battery`
  - the OAK-D's USB speed and detection rate once it is up
- **Prints a summary at the end of each stage**: lowest and mean 5 V,
  samples below 4.8 V, throttle changes, kernel events, worst ping.
- **Logs survive a crash.** Each run writes to `~/power_tests/<timestamp>/`,
  one line at a time. `--report <dir>` re-prints the summary after a reboot.
- **Ctrl-C stops everything cleanly**, newest stage first. The semantic node
  gets SIGINT, so it saves its map.

### The doc: `process/02-doc/power_testing.md`

- How to run the script and read its output.
- The manual checks a script can't do: multimeter readings and the wiggle
  test.
- Known problems (`bl` without a TTY, USB 3 interfering with Wi-Fi).
- **The results log from `power_system_testing.md`, carried over**, plus the
  2026-11-05 run.

### Then delete

- `process/02-doc/power_load_test.md` and `process/02-doc/power_system_testing.md`.
- `dome_vision/dome_vision/examples/power_stress_test.py`. It is in another
  repo, so it needs its own commit there.

### Out of scope

- Fixing the power supply itself.
- SLAM in the load sequence. The static map→odom keeps the test simple.

## How to Demo

**Setup**: robot on the stand, charger unplugged, fresh boot, OAK-D plugged
in.

**Steps**:
1. `cd ~/ros2_ws`
2. `src/dome_semantic/tools/power_load_test.sh`
3. Watch the stage banners, live kernel events, and per-stage summaries.
4. Press Ctrl-C partway through one run, to check the cleanup.
5. `src/dome_semantic/tools/power_load_test.sh --report ~/power_tests/<latest>`

**Expected output**:
- All seven stages run in one window, each with a summary.
- After Ctrl-C, no launch or `stress-ng` process is left running.
- `--report` prints the same summaries from the log files.

## Process Gate

After creating this feature file and the corresponding task file, **stop and present the plan to the user**. Do not write any code or content until the user gives explicit approval to proceed.
