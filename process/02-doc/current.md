# Current status

See `process/02-doc/history.md` for completed work and
`process/02-doc/notes.md` for hardware state, the robot run procedure,
commands and gotchas.

## Open

### Pick up here (2026-11-16)

- **`.claude/` synced to the `j3` kit** (exact copy, minus
  `settings.local.json`); current.md restructured to the kit's new shape.
  The run write-ups moved to `history.md`, durable facts to `notes.md`.
- **The kit assumes `uv`**, which the robot lacks: the ruff hook silently
  no-ops, and `/checkpoint`'s `uv run pytest` will fail. Run tests with
  `/usr/bin/python3 -m pytest test/` and ruff from `dome_vision`'s venv.
- **No feature is in progress.** F36 closed 2026-11-13 (TF36.7 and TF33.0
  passed on `f36run6`). Next is "Decisions pending", first item.

### Next

1. **TF33.8** Parts B and C, **TF33.9** (Pi CPU), **TF33.10** (docs), once
   false confirmations are decided.
2. **Move power testing to `dome2`**: `tools/power_load_test.sh`,
   `tools/power_summary.awk`, `test/test_power_load_test.py`,
   `process/02-doc/power_testing.md`. Then drop "Support tooling" from
   `spec.md` and fix the paths in `dome_vision`'s docs. Check `dome2`'s
   process rules first.
3. **TF33.7** (fake detection producer): deferred; build only if hardware
   stays unavailable. Its design was never committed.

### Decisions pending

- **False confirmations are now permanent** (11 false cup IDs on
  `f36run6`). Drop lost targets with few observations, or widen the cup
  radii? Needs its own feature.
- **`dome_vision` F70** (image world IDs from the semantic map): drafted,
  not approved.

### Chores

- Make RViz markers visible at map zoom; rename `/targets/*` topics to
  `/semantic/*`. Both proposed in `process/04-tasks/chores.md`.
- Adapt the kit's `uv`-based hook and `/checkpoint` to this repo, or
  install `uv` (not yet decided).

### Open issues, in other packages

- **`dome_vision`** I04 (depth error on small objects at ~2 m), I05
  (can/cup double label, steady false cups).
- **`dome_nav`** I13 (real params not migrated to Kilted: `/cmd_vel` type
  mismatch, `bt_navigator` crash). **Nav2 navigation is down** until fixed;
  teleop works. The issue file is still uncommitted there.
- **`dome2`** I01 (odometry drift), I02 (10 s EKF stall).

### Loose ends elsewhere

- **`dome_vision` F71 code landed** (`717a6d4`, old tracker deleted), but
  its feature file is still in `notdone/` with `Done: no`. Close it there.
