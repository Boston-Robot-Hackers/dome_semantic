# Current status

See `process/02-doc/history.md` for completed work and
`process/02-doc/notes.md` for hardware state, the robot run procedure,
commands and gotchas.

## Open

### Pick up here (2026-11-16)

- **F37 closed** (forget weak lost targets): a confirmed target that goes
  lost with under `min_keep_obs` (40) observations is deleted. 160 tests
  pass. Details below.
- **`.claude/` synced to the `j3` kit**, committed (`8436ec6`). The kit
  assumes `uv`, which the robot lacks: the ruff hook no-ops and
  `/checkpoint`'s `uv run pytest` fails. Use `/usr/bin/python3 -m pytest
  test/` and `dome_vision`'s `.ruff-venv` ruff.
- **No feature in progress.** Next: "Next", step 1.

#### TF37.0: count at first loss decides

The threshold applies when a target *first* goes lost, so the counts that
matter are those, from each bag's `/semantic/targets`:

| Bag | Smallest real can | Largest short-burst false |
|---|---|---|
| `f36run6` | T1: 987 | T17: 16 |
| `f36run` | T5: **58** | T10/T12: 39 |
| `f36replay_keep` | T18: 64 | T8: 28 |

**Chose 40.** The margin to real cans is thin (58), so watch for a real
object vanishing on the next robot run.

#### TF37.4: `f36run6` replay, pass

`~/bags/f37replay_run6`, map `f37replay_run6`: **4 targets, down from 12.**

- **Can T1**: one ID, (1.59, −0.05), as on the original run.
- **11 short-burst cups** confirmed, then were forgotten when lost.
- **Left**: steady false cup T2 (1618 obs, `dome_vision` I05); T45 at
  (−1.08, 1.36), 61 obs; T65 at (2.80, −0.65), 297 obs. T65 is the
  original T17, forgotten at 16 obs and re-confirmed under a new ID.
- Counts run higher than the live run because the live node started 57 s
  after the bag.

#### Live run `mon09`, 2026-11-16: can pass, cups partial

Real SLAM (`slam_toolbox` alone: `robot_map.launch.py`'s Nav2 drove load
to ~40 and starved the EKF). One can, **no real cups**. The bag stops
at 20:54:54; the node ran to 20:56:53 and saved `mon09.json`.

- **Can T1 kept one ID**: lost 5 times, 276 obs at the first loss.
- **8 false cups forgotten** (5–27 obs). **8 remain** (41–207 obs), 4
  of them lost at only 41–57. A cluster of 4 near (3.1–3.4, 0.5–1.3);
  T25/T26 near (−1.7, −0.55), the same spot as cup T10 in `mon08`; T31
  0.15 m from the can (double label).
- **A count can't separate these**: false cups reach 40–100 obs, and a
  real can had 58 at first loss (`f36run`). The rest is `dome_vision`
  I05's job.

### Next

1. **TF33.8** Parts B and C, **TF33.9** (Pi CPU), **TF33.10** (docs).
2. **Move power testing to `dome2`**: `tools/power_load_test.sh`,
   `tools/power_summary.awk`, `test/test_power_load_test.py`,
   `process/02-doc/power_testing.md`. Then drop "Support tooling" from
   `spec.md` and fix the paths in `dome_vision`'s docs. Check `dome2`'s
   process rules first.
3. **TF33.7** (fake detection producer): deferred; build only if hardware
   stays unavailable. Its design was never committed.

### Decisions pending

- **`dome_vision` F70** (image world IDs from the semantic map): drafted,
  not approved.

### Chores

- Make RViz markers visible at map zoom; rename `/targets/*` topics to
  `/semantic/*`. Both proposed in `process/04-tasks/chores.md`.
- Add `Date Created` to the done F33–F36 / TF33–TF36 files (kit rule:
  header changes apply retroactively), dated from git history.
- Adapt the kit's `uv`-based hook and `/checkpoint` to this repo, or
  install `uv` (not yet decided).

### Open issues

- **I01**: range noise makes duplicate targets along one line of sight
  (2026-11-17, two cans at ~5 m became five targets). Waits on
  `dome_vision` I04.

### Open issues, in other packages

- **`dome_vision`** I04 (depth error on small objects at ~2 m, recurred at
  ~5 m on 2026-11-17), I05
  (can/cup double label, steady false cups).
- **`dome_nav`** I13 (real params not migrated to Kilted: `/cmd_vel` type
  mismatch, `bt_navigator` crash). **Nav2 navigation is down** until fixed;
  teleop works. The issue file is still uncommitted there.
- **`dome2`** I01 (odometry drift), I02 (10 s EKF stall).

### Loose ends elsewhere

- **`dome_vision` F71 code landed** (`717a6d4`, old tracker deleted), but
  its feature file is still in `notdone/` with `Done: no`. Close it there.
