# Power system testing

How to diagnose brownouts on the robot (Pi 5 + OAK-D). Two crashes on
2026-10-22 each ended with an `Undervoltage detected!` line and no shutdown,
and the 19:57 one came right after the OAK-D re-enumerated on USB.

Work through the steps below, cheapest first. Each one isolates a part of
the chain: **battery → 5 V converter → wiring/connectors → Pi → USB hub →
OAK-D**.

## Quick health check

Run on the Pi:

```
vcgencmd pmic_read_adc EXT5V_V        # Pi 5 V input
vcgencmd get_throttled                # 0x0 = no undervoltage since boot
vcgencmd get_config usb_max_current_enable
lsusb -t                              # is the OAK-D behind a hub?
journalctl -k -b -1 | grep -i voltage # dips in the previous boot
```

**Baseline (2026-10-22, idle, on charger)**:

- `EXT5V_V` = 5.01 V.
- `usb_max_current_enable=1`, so the Pi isn't capping USB at 600 mA. This only
  tells the Pi to *assume* a 5 A supply; it doesn't prove the supply can
  deliver it.
- The OAK-D sits behind an external USB 3 hub, not directly on the Pi.

## 1. Log the 5 V rail to a file that survives a crash

Run in its own tmux pane during every test:

```
while true; do echo "$(date +%T.%N | cut -c1-12) $(vcgencmd pmic_read_adc EXT5V_V | cut -d= -f2) $(vcgencmd get_throttled)"; sleep 0.2; done | tee -a ~/power_log.txt
```

It writes to `~/power_log.txt`, not `/tmp`, so it's still there after a
reboot. Watch kernel events alongside it with `journalctl -kf | grep -i voltage`.

**Reading it**:

- Voltage slides down over minutes → the battery is sagging.
- Steady near 5.0 V, then the log just stops → a fast spike, which points
  at connectors or wiring.

## 2. Load test on battery only

Robot on the stand, no driving. **Unplug the charger**, or it masks the
battery.

Add load in steps and note the lowest `EXT5V_V` at each:

1. Idle.
2. CPU: `stress-ng --cpu 4 --timeout 60` (`sudo apt install stress-ng` if
   missing).
3. OAK-D: `dome_vision_ros.launch.py --depth true`. Its startup (firmware
   load + switch to USB 3) is the current spike that crashed it on
   2026-10-22.
4. CPU stress and the OAK-D together.

**Thresholds**:

- Above ~4.9 V and steady → the supply is fine.
- Below ~4.8 V → brownout territory.
- Fine on a full pack, bad later → the battery's state of charge. Note the
  pack voltage at each run; the first crash happened at 10.65 V.

## 3. Find where the voltage is lost (multimeter)

During step 2.3 or 2.4, measure at three points:

- the battery terminals
- the 5 V converter's output
- the Pi's input: the USB-C plug, or the GPIO 5 V and GND pins

**Reading it**:

- Converter output drops too → the converter is too small or faulty. Check its
  rating against ~5 A (Pi 5 + OAK-D at startup).
- Converter output steady but the Pi's input drops → the loss is in the wire
  or connectors. Look for thin wire, a loose Dupont/GPIO connection, or a
  bad USB-C cable. Even 0.1 Ω loses 0.5 V at 5 A.

## 4. Wiggle test

With the step 1 log running, gently flex each connector:

- the battery plug
- the converter terminals
- the Pi's power input
- the hub and OAK-D cables

If the log or the kernel watch reacts, that connection is bad. The
2026-10-22 sequence (OAK-D dropped off USB *before* the undervoltage) also
fits a marginal OAK-D cable or hub contact.

## 5. Take the hub out of the path

- Plug the OAK-D straight into one of the Pi's blue USB 3 ports, **or**
- give it its own power: a powered hub, or the OAK's own power input if
  the model has one.

If the brownouts stop, the problem is how the OAK-D gets its power, not
the battery.

## Known noise

The kernel `WARNING ... get_throttled_show` stack trace comes from
`battery_telemetry` reading a deprecated sysfs file. It's harmless and not
a fault.

## Still unknown

- How the Pi is powered (USB-C from the converter vs. GPIO 5 V pins) and
  the converter's current rating.
- Whether the USB hub is powered.

## Results log

Record each run here: date, pack voltage, step, lowest `EXT5V_V`,
throttled flags, outcome.

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
rating. For the staged load test, use `dome_vision/examples/power_stress_test.py`.

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
