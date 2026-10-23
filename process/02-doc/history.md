# History

Completed-work log, moved out of `current.md` to keep session handoff lean.
Append new entries here when marking work done in `current.md`.

**2026-08-02** — package created and bootstrapped.

## Done

- **TF33 T01** (`dome_semantic_msgs`) — done previously, lives in the sibling
  `dome_semantic_msgs` repo (matches spec: `schema_version`, `target_id`,
  `label`, `pose`, `observation_count`, `last_seen`, `track_ids`).
- **TF33 T02** — pure tracker core ported from `dome_vision`:
  `world_tracker.py` + `association.py`, `class_profiles.py`,
  `size_estimate.py`, `targets.py`, `tracker_config.py`, `geometry.py`, plus a
  new `embedding_similarity.py` (cosine_sim only, split out of
  `dome_vision`'s `embedding.py` to avoid pulling `torch`/`torchvision`/`cv2`
  into this package). Behavior-preserving — same thresholds/tolerances.
  83 tests pass (`/usr/bin/python3 -m pytest test/`); `colcon build` clean.
  Two of the original 21 test failures on first port were dropped as
  out-of-scope (`test_appconfig_world_tracker_section`,
  `test_appconfig_world_tracker_defaults_when_absent` — they test
  `dome_vision`'s own `AppConfig`, not `WorldTracker`); the rest were fixed by
  porting `tests/conftest.py`'s cwd-fixture and the
  `examples/configs/class_profiles.yaml` fixture file alongside the code.
  `dome_vision`'s originals were **not** deleted — cleanup is deferred until
  the ROS shell (T03/T04) is proven, same pattern F35/TF35 T06 used.
- **TF33 T03** — `map`-frame recording + re-basing on `map→odom` jumps. Not a
  port this time — nothing like it existed anywhere; `dome_vision`'s current
  node only transforms camera→`odom` and has no re-basing at all. New:
  `tf_adapter.py` (ported `TFAdapter`, retargeted to `map`, now uses the
  detection's real stamp instead of the original's ignored one),
  `map_rebasing.py` (pure SE(2) transform composition + `rebase_tracker`),
  and this package's first ROS node, `semantic_map_node.py` (subscribes
  `/oak/detections_3d`, TF-transforms + re-bases; no publishing yet — that's
  T04). 110 tests pass total; `colcon build` clean.
- **Checkpoint** (2026-08-02) — added `ruff.toml` (was missing since bootstrap;
  matches `dome_mission`/`dome_nav`'s: line-length 88, ignore `EXE001` for the
  mandatory-shebang convention). Fixed everything `ruff check`/`ruff format`
  flagged except two: unsorted imports, an unused `pytest` import, 5×
  `dict()` → `{}` literal rewrites in test config helpers, 2 dead
  (never-referenced) local vars, 2 unused tuple-unpacks renamed to `_`. One
  substantive fix: `tf_adapter.py`'s `except Exception` narrowed to the
  three `tf2_ros` exceptions this codebase catches everywhere else a TF
  lookup can fail (`dome_nav`'s `explorer_manager_node.py`, this package's
  own `semantic_map_node.py`) — a real bug elsewhere in that method should
  surface, not get silently mapped to "transform unavailable"; updated the
  two tests that raised a generic `Exception` to raise
  `tf2_ros.LookupException` instead. **Left deliberately unfixed**: two
  `SIM102` (nested-if) findings in `association.py` — that file is T02's
  behavior-preserving port, and reshaping matching-logic control flow isn't
  a checkpoint-scope change. 110 tests still pass; `colcon build` clean.
  Also converted the 4 T03-authored files' (`tf_adapter.py`,
  `map_rebasing.py`, `semantic_map_node.py`, `embedding_similarity.py`)
  multi-line rationale `#` comment blocks into proper module docstrings —
  ruff doesn't flag this, but style_guide.md's MUST rule against narrative
  comment blocks does; the ported T02 files were left as-is (matches
  `dome_vision`'s own pre-existing convention, not introduced this session).

- **TF33 T04** (2026-08-03) — typed `SemanticTargetArray` publishing +
  node wiring. New `tracker_params.py` (`declare_tracker_config`, pure
  `node`-duck-typed function walking `WorldTrackerConfig.model_fields`,
  mirrors `dome_nav`'s F34 dataclass-single-source-of-truth pattern for
  pydantic). `SemanticMapNode` gained `/semantic/targets`
  (`SemanticTargetArray`, throttled), `/targets/markers` (map frame,
  throttled), `/targets/assoc_diag` (unthrottled), `/describe_scene`
  (Trigger). New `publish_every_n` ROS param (default 5). Target
  orientation always identity — `WorldTracker` has no facing estimate.
  119 tests pass; `colcon build` clean (hit and fixed a stale
  `build/dome_semantic_msgs` CMake cache pointing at a path missing
  `src/` — unrelated to this task's code).
- **TF33 T06** (2026-08-03) — persistence keyed to SLAM map identity. New
  `semantic_persistence.py`: `save_semantic_map`/`load_semantic_map`
  read/write `~/.dome/semantic_maps/<map_name>.json`, envelope
  `{"map_name": ..., "targets": [...]}` wrapping `WorldTracker.to_json()`.
  Primary key is the (sanitized) filename; envelope's own `map_name` is a
  second check catching sanitization collisions (`"room a"`/`"room#a"` both
  become `room_a.json`) — any mismatch or unrecognized format falls back to
  a fresh tracker + warning, never a silent merge. **Decided against**
  migrating old dome_vision-era bare-array files: no such file can exist at
  the new keyed path, so a migration branch would be speculative code for a
  case that can't occur. Node gained a `map_name` param (default
  `"unknown"`) and a `save()` called from `main()`'s `finally`. 127 tests
  pass; `colcon build` clean.
- **Full `process/01-literate/` set** (2026-08-03) — `00-overview.md`
  theory-of-operation plus one dependency-ordered chapter per module (14
  files total: 00 + 13). Package had none before this session.
- **Checkpoint** (2026-08-03) — `ruff check`/`ruff format` clean across the
  repo, including fenced Python blocks inside `process/01-literate/*.md` (a newer
  ruff feature reformats those too). One substantive fix, this time
  **reversing** the 2026-08-02 checkpoint's deliberate call: that session
  left two `SIM102` (nested-if) findings in `association.py` unfixed,
  reasoning "reshaping matching-logic control flow isn't a checkpoint-scope
  change" for a T02 behavior-preserving port. Revisited because the merge
  ruff suggests (`if a: if b: continue` → `if a and b: continue`) is a pure
  boolean identity, not a control-flow reshape — applied both, all 127
  tests still pass unchanged. Also fixed a real (if minor) finding in this
  session's own code: `seconds_to_ros_time`'s redundant `int(round(...))` —
  `round()` on a float with no `ndigits` already returns `int`.
- **TF33.8 reworded** (2026-10-23) — split into Part A (node-only launch
  file), Part B (includable perception+SLAM+explore+semantic sub-stack
  launch file) and Part C (ingestion-while-driving decision), each with its
  own test line.
- **TF33.8 Part A** (2026-10-23) — `launch/semantic.launch.py`
  (better_launch): `semantic_map_node` with required `map_name` (refuses to
  start without it, since the node's `"unknown"` default would share one
  persistence file across maps) and `publish_every_n`; optional
  `--static_map_odom true` adds the identity `map→odom` for no-SLAM bench
  runs. `setup.py` installs `launch/`; `package.xml` gains
  `exec_depend better_launch`. `test/test_semantic_launch.py` (5 tests,
  fake BetterLaunch, no ROS runtime). Live on the robot: params set,
  `map→odom` published, clean shutdown with map saved. New literate chapter
  `14-semantic_launch.md`.
- **Checkpoint** (2026-10-23) — ruff (via `dome_vision/.ruff-venv`, not
  installed system-wide on the robot) fixed one import-order finding and
  reformatted two test files left over from the 10-22 TF fixes. 135 tests
  pass.
