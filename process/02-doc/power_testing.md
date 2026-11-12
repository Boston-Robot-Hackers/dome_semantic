# Power testing

The robot (Pi 5 + OAK-D) browns out under load: the Pi's 5 V input sags
below ~4.8 V and the kernel logs `Undervoltage detected!`. Two crashes on
2026-10-22 ended that way. This doc is the procedure for testing it, and the
log of what each test found.

The chain to suspect: **battery → 5 V converter → wiring/connectors → Pi →
OAK-D**.

## Before you start

- **Robot on the stand**, not driving.
- **Charger unplugged**, or it hides how the battery behaves.
- **Fresh boot**, so `vcgencmd get_throttled` starts at `0x0`. The script
  warns if it doesn't.
- **OAK-D plugged into a blue (USB 3) port.** `lsusb | grep 03e7` must show
  it. Before a pipeline starts it can show as `03e7:2485` at 480M; *that is
  normal*, it switches to USB 3 when its firmware loads.
- **Nothing from the stack already running.** The script refuses to start
  if it finds one.

## Running the load test

One terminal window, from the workspace root:

```
cd ~/ros2_ws
src/dome_semantic/tools/power_load_test.sh            # 30 s per stage
src/dome_semantic/tools/power_load_test.sh --hold 60  # longer stages
```

**Stages**, each adding load to the one before:

| Stage | What runs |
|---|---|
| `idle` | nothing: the baseline |
| `base` | `bl dome2 robot.launch.py --options "d b"` (drivers + battery) |
| `cpu` | `stress-ng --cpu 4`, stopped when the stage ends |
| `oak` | `bl dome_vision_ros dome_vision_ros.launch.py --config "$DOME_VISION_CONFIG" --depth true` |
| `subscriber` | `ros2 topic hz /oak/detections_3d`; without a subscriber the node never runs inference |
| `semantic` | `bl dome_semantic semantic.launch.py --map_name power_test --static_map_odom true` |
| `worst_case` | `stress-ng --cpu 4` again, with everything running |

**What you see**: a banner per stage, kernel voltage and USB events as they
happen (`[kernel] ...`), and a summary when each stage ends. A warning
appears if the OAK-D isn't at USB 3 speed.

**Ctrl-C** stops everything at any point, newest stage first, and prints the
full summary. The semantic node saves `~/.dome/semantic_maps/power_test.json`
as it stops.

## Where the logs go

Each run gets `~/power_tests/<date>_<time>/`. Every line is written as it
happens, so a crash keeps everything up to the moment of the crash.

| File | Contents |
|---|---|
| `rail.log` | 5 V rail (`EXT5V_V`) and `get_throttled`, every 0.2 s |
| `kernel.log` | kernel lines matching voltage or USB |
| `wifi.log` | one ping to the gateway each second |
| `stage_info.log` | per stage: pack voltage and power, OAK-D USB speed, detection rate |
| `procs/<stage>.log` | each launch's own output |
| `summary.txt` | the final summary (missing if the robot crashed) |

## After a crash

Once the robot reboots:

```
src/dome_semantic/tools/power_load_test.sh --report ~/power_tests/<run>
journalctl -k -b -1 | grep -iE "voltage|usb"
tail -20 ~/power_tests/<run>/rail.log
```

The last lines of `rail.log` show the voltage just before the crash.

## Reading the numbers

- **Above ~4.9 V and steady**: the supply is fine.
- **Below ~4.8 V**: brownout territory.
- **Dip right as the OAK-D switches to USB 3** (in the `oak` stage): the
  startup current spike, which is what crashed the robot on 2026-10-22.
- **USB disconnect, then undervoltage**: a marginal cable or contact, or a
  dip on the 5 V rail.
- **Voltage slides down over minutes**: the battery is sagging.
- **Fine on a full pack, bad on a low one**: the converter is running near
  its limit. Note the pack voltage (`pack_v`) of every run.
- **Detection rate**: about 10 Hz on USB 3; 7–8 Hz usually means USB 2.
- **`throttled`**: `0x0` is clean. `0x50000` means undervoltage and
  throttling happened earlier in the boot; `0x50005` means it is happening
  now.

## Manual checks

These need hands, so the script can't do them.

### Multimeter: where the voltage is lost

During the `oak` or `worst_case` stage, measure at:

- the battery terminals
- the 5 V converter's output
- the Pi's input: the USB-C plug, or the GPIO 5 V and GND pins

**Reading it**:

- Converter output drops too → the converter is too small or faulty. Check
  its rating against ~5 A (Pi 5 + OAK-D at startup).
- Converter output steady but the Pi's input drops → the loss is in the
  wire or connectors. Even 0.1 Ω loses 0.5 V at 5 A.

### Wiggle test

With the script at `idle` (try `--hold 300`), gently flex each connector
in turn and watch for kernel events and summary dips:

- the battery plug
- the converter terminals
- the Pi's power input
- the OAK-D cable

## Known problems

- **USB 3 interferes with 2.4 GHz Wi-Fi.** With the OAK-D straight on the
  Pi (2026-11-05), the link fell to 2–6.5 Mbit/s and pings ran 7–294 ms.
  **Fix**: Wi-Fi on 5 GHz (`band: 5GHz` under the access point in
  `/etc/netplan/50-cloud-init.yaml`, then `sudo netplan try`). `wifi.log`
  shows whether it's back.
- **`bl` with no TTY prints `Aborted!`**, but the launch still runs.
- **Stop launches, not nodes.** Killing only the semantic node leaves its
  static TF publisher running. The script stops whole process groups.
- **`WARNING ... get_throttled_show`** in the kernel log comes from
  `battery_telemetry` reading a deprecated sysfs file. Harmless.
- **The two battery topics disagree on percent.** Trust the voltage.

## Still unknown

- How the Pi is powered (USB-C from the converter vs. GPIO 5 V pins) and
  the converter's current rating.

## Results log

Record each run here: date, setup (cable, port, Wi-Fi band), pack voltage at
start and end, the script's summary, and the outcome.

### 2026-10-22 — step 4, wiggle test (battery only, idle)

**Setup**: charger unplugged, OAK-D not running, pack voltage not recorded.
Logging was ~8 readings/s, so microsecond spikes can slip between readings;
the kernel undervoltage flag would still catch those.

**First pass (unlabelled, ~70 s)**:

- Steady at 5.03–5.07 V, `throttled=0x0`, no kernel voltage events.
- One noisy ~5 s stretch (20:20:10–20:20:14) ending in a **4.88 V** dip
  that recovered within 0.25 s. The connector being flexed was not recorded.

**Second pass (guided, 15 s per connector)**:

| Connector | Mean V | Min V | < 4.95 V | Std dev |
|---|---|---|---|---|
| Baseline (hands off) | 5.047 | 5.004 | 0 | 0.020 |
| Battery plug | 5.046 | **4.899** | 2 | 0.034 |
| Converter input | 5.031 | 4.947 | 1 | 0.024 |
| Converter output | 5.034 | 4.926 | 1 | 0.030 |
| Pi power input | 5.039 | 4.953 | 0 | **0.038** |
| USB hub cables | 5.031 | 4.959 | 0 | 0.026 |
| OAK-D cable | 5.028 | 4.973 | 0 | 0.023 |
| Rest (between) | 5.043 | 4.962 | 0 | 0.025 |

**Outcome**:

- **No connector failed.** `throttled` stayed `0x0` and the kernel logged
  no undervoltage events.
- **The battery plug is the weak suspect**: it gave the lowest reading,
  matching the first pass's 4.88 V dip. The Pi power input varied the most.
  Neither stands far above background noise (rest periods dipped to 4.96 V).
- **The wiring holds up at idle current.** Brownouts are load-triggered (OAK-D
  startup), where a slightly worn contact costs far more voltage at ~5 A.

**Next**: inspect or reseat the battery plug, then run step 2's load test
with an OAK-D start.

### 2026-10-22 — 17:20 crash, from existing telemetry

**Source**: `~/.dome/telemetry/10-22-telemetry`, written by `dome_telemetry`'s
`battery_telemetry` node once a minute. `ext5v_min_v` is the lowest 5 V
reading in that minute (sampled every 0.5 s).

| Time | Battery | Current | Power | `ext5v_v` | `ext5v_min_v` | throttled |
|---|---|---|---|---|---|---|
| 17:14 | 10.65 V | 0.68 A | 7.0 W | 5.01 | 4.92 | 0x0 |
| 17:16 | 10.64 V | 0.65 A | 7.0 W | 5.02 | 5.00 | 0x0 |
| 17:17 | 10.62 V | 0.75 A | 7.1 W | 4.94 | 4.87 | 0x0 |
| 17:18 | 10.47 V | 1.13 A | 11.8 W | 4.87 | 4.76 | 0x50000 |
| 17:19 | 10.46 V | 1.23 A | 12.9 W | 4.81 | 4.69 | 0x50000 |
| 17:20 | 10.42 V | 1.17 A | 12.2 W | 4.82 | 4.69 | 0x50005 |
| 17:21 | 10.41 V | 1.24 A | 12.9 W | 4.80 | **4.63** | 0x50000 |

**Findings**:

- **The battery was fine**: it fell only 10.65 → 10.41 V, ample for a 5 V
  converter.
- **The 5 V rail sagged steadily, not just in spikes.** When load went from
  ~7 W to ~13 W (OAK-D start), the typical 5 V level fell ~0.2 V and stayed
  down; minima reached 4.63 V, at the brownout limit.
- **The weak link is battery → Pi**: the 5 V converter, or the wire and
  connectors after it. ~0.2 V lost for ~1.2 A extra on the 5 V side is
  ~0.17 Ω — far too much. Consistent with the wiggle test's mild battery-plug
  and Pi-input suspects.
- **Recharging alone probably won't fix it.**
- **The 19:57 crash left no record**: the node started at ~19:56:36 and
  appends once a minute, so it died before its first write.

**Next**: multimeter at converter output vs. Pi input during an OAK-D start
(step 3) to split converter from wiring; find the converter's current
rating. (Superseded: the load test is now `tools/power_load_test.sh`.)

The guided wiggle-test script lives only in the session scratchpad. It
tags each reading with the connector being flexed; recreate it if needed.

### 2026-10-22 20:43 — OAK-D start on a full pack (F03 telemetry)

**Setup**: battery only, 11.97 V (89%). Telemetry node with 10 s records,
then the OAK-D started at ~20:43:45.

| Record | Bus V | Peak discharge | Power | `ext5v_v` | `ext5v_min_v` |
|---|---|---|---|---|---|
| 20:43:40 (before) | 11.96 | 0.68 A | 7.3 W | 5.064 | 5.013 |
| 20:43:50 (start) | 11.86 | 0.98 A | 11.1 W | 4.942 | 4.930 |
| 20:44:10 | 11.86 | 0.98 A | 11.0 W | 4.963 | 4.878 |
| 20:44:20 | 11.84 | 1.14 A | 11.2 W | 4.979 | 4.875 |

**Outcome**: no brownout; `throttled` stayed `0x0`.

- **The 5 V sag is about half the 17:20 crash's** at the same ~11–12 W: the
  typical level fell ~0.1 V (5.06 → 4.96) instead of ~0.2 V, and minima
  stopped at 4.875 V instead of 4.63 V.
- **So battery charge does matter, unlike what the 17:20 data alone
  suggested.** A plain buck converter shouldn't care whether its input is
  10.4 or 12 V. That it does points at the converter or UPS board running
  near its limit.
- **The margin is still thin**: ~0.25 V above the brownout limit on a full
  pack, with the OAK-D running.

### 2026-10-23 evening — TF33.0 run on a good pack (from `current.md`)

**Setup**: OAK-D behind the external USB hub; pack 11.77 V → 11.62 V under
load; static map→odom, semantic node running.

- 5 V rail: 4.97 V idle → 4.84 V with the OAK-D → 4.80 V with the semantic
  node too.
- 13 undervoltage dips this boot. The first came 1 s after the OAK-D
  switched to USB 3; the first two lasted 31 s and 25 s. No crash.
- **Conclusion**: the pack is not the cause. The 5 V converter or wiring has
  too little headroom for a Pi 5 + OAK-D.

### 2026-11-05 — hub removed, OAK-D straight on the Pi

**Setup**: external USB hub removed; OAK-D plugged straight into the Pi.

- **At first the Pi didn't see the OAK-D**: no `03e7` in `lsusb`, no kernel
  USB events, even during a 3-minute replug watch.
- **Power at rest looked healthy**: `EXT5V_V` 5.18–5.19 V (about 5.0 V in
  earlier runs), `throttled=0x0`.
- **Wi-Fi went sluggish** with the OAK-D on the Pi's USB 3 (see *Known
  problems*). Wi-Fi was then moved to 5 GHz (channel 153).
- **Later the OAK-D enumerated** as `03e7:f63b` (firmware loaded) but at
  **480M**: a USB 2 fallback. Port, plug seating, or cable still to check.
- No load test was run yet.

### 2026-11-05 20:00 — first `power_load_test.sh` run

**Setup**: OAK-D straight on the Pi, but at **USB 2** (`480M`; the kernel
logged "new high-speed", never "SuperSpeed"). Wi-Fi on 5 GHz. 30 s stages.
Pack voltage not recorded: the UPS's I2C isn't connected yet, so
`/telemetry/battery` doesn't publish. Run dir: `~/power_tests/2026-11-05_200014/`.

| Stage | Min 5 V | Mean 5 V | Det. rate | Worst ping |
|---|---|---|---|---|
| idle | 5.11 | 5.19 | — | 8.7 ms |
| base | 5.07 | 5.17 | — | 9.9 ms |
| cpu | 5.04 | 5.07 | — | 20.7 ms |
| oak | 5.06 | 5.15 | — | 11.8 ms |
| subscriber | 5.08 | 5.15 | 7.8 Hz | 8.0 ms |
| semantic | 5.06 | 5.12 | 7.8 Hz | 11.0 ms |
| worst_case | **5.01** | 5.05 | 7.7 Hz | 6.0 ms |

**Outcome**: no dips, no undervoltage events, `throttled=0x0` throughout,
no lost pings. Cleanup left nothing running; the semantic map was saved.

- **The rail sits ~0.15–0.2 V higher than in October** (5.19 V idle against
  ~5.0 V), which leaves far more headroom.
- **This isn't the worst case yet**: at USB 2 the OAK-D draws less and runs
  at 7.7 Hz instead of ~10 Hz. Rerun once it connects at USB 3.

### 2026-11-09 16:45 — first run at USB 3

**Setup**: OAK-D straight on the Pi, now at **USB 3** (`5000M`, kernel
"new SuperSpeed" on `usb 3-1`). Wi-Fi on 5 GHz. Stages ran ~30 s each
(stage spacing ~40 s), although `--hold 60` was intended. Pack voltage not
recorded (UPS I2C still unconnected). Run dir: `~/power_tests/2026-11-09_164519/`.

| Stage | Min 5 V | Mean 5 V | Det. rate | Worst ping |
|---|---|---|---|---|
| idle | 5.19 | 5.24 | — | 16.9 ms |
| base | 5.18 | 5.23 | — | 19.9 ms |
| cpu | 5.14 | 5.18 | — | 15.1 ms |
| oak | 5.16 | 5.21 | — | 12.3 ms |
| subscriber | 5.17 | 5.21 | 10.0 Hz | 19.3 ms |
| semantic | 5.15 | 5.21 | 10.0 Hz | 16.4 ms |
| worst_case | **5.14** | 5.16 | 10.0 Hz | 18.5 ms |

**Outcome**: no dips below 4.80 V, no undervoltage events, `throttled=0x0`
throughout, no lost pings. The two USB disconnects are expected: the
bootloader-to-firmware re-enumeration in `oak` and the shutdown at the end.

- **Finding the USB 3 fault**: the OAK-D connects at USB 3 only in the
  blue port on bus 2/3. In the other blue port (bus 4/5) it fell back to
  USB 2 with two cables and repeated reseats, and bus 5 logged no events.
  **Keep the OAK-D in the bus 2/3 port.**
- **Check speed only after firmware loads.** The unbooted bootloader
  (`03e7:2485`) always enumerates at 480M. Look for `03e7:f63b`.
- **The worst case has plenty of margin**: 5.14 V min against the 4.80 V
  threshold, better than the USB 2 run's 5.01 V, at full 10 Hz detection.
