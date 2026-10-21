# TF33 — Semantic Exploration, Phase A (contract + adapter + launch) for F33

Phase A only. Phases B and C get their own task files once Phase A validates
the decisions recorded in the F33 feature file.

**Settled decisions**: frame of record = `map`; contract = a typed
`SemanticTarget` msg in a new msgs package; the semantic map is owned by a new,
neutral package (`dome_semantic`).

## Build order — interleaved with TF35 (F33 G9)

**TF35 (the `dome_mission` mission-sequencing layer) is now fully complete** —
merged to `dome_nav`'s `main` at `894c799` (2026-08-02). `/intent` ownership and
the semantic-target consumer live in `dome_mission`, not here. This task file
is *not* an independent sequence; the real build order across the two features
was:

1. ~~TF35 T01–T04~~ — *done*: `dome_mission` skeleton, `ExploreArea` action,
   mission FSM, `/intent` moved out of dome_nav.
2. ~~TF33.1–TF33.4 (this file)~~ — *done (2026-08-03)*: msgs, tracker port,
   map-frame recording, typed publishing. `SemanticMapNode` now publishes a
   real, live `/semantic/targets` feed.
3. ~~TF35 T05~~ — *done*: `dome_mission` consumes `SemanticTargetArray`. Was
   blocked on TF33.4 publishing something real; now unblocked end-to-end
   (message type since TF33.1, live publisher since TF33.4) — not yet
   live-verified together on one running stack (that's TF33.8).
4. ~~TF35 T06/T07~~ — *done*: dome_nav cleanup, `ExploreArea` action server,
   top-level launch, live sim bring-up verified 2026-08-01.
5. ~~TF33.6~~ — *done (2026-08-03)*: persistence keyed to SLAM map identity.
6. **TF33.0 (real-hardware verification) is the next actual step** — see
   below. TF33.7 (fake detection producer) and TF33.8 (sub-stack launch
   composition) wait behind it: whether they're still the right next tasks
   depends on what verification finds.

**Consumer of everything this task publishes is `dome_mission`, never
dome_nav** — dome_nav must never gain a `dome_semantic_msgs` dependency.

---

## TF33.0 — Real-hardware verification: test the stack bottom-up

**Status**: not started — the actual next step, ahead of TF33.7/TF33.8

TF33.1–TF33.6 are done but only unit-tested — never run against real OAK-D
hardware. No combined launch exists yet (that's TF33.8), so verification is
component-by-component on the real robot, from the bottom of the stack up:
OAK-D detections (`/oak/detections_3d`) → `tf_adapter.py`'s
`camera_link`→`map` transform → `SemanticMapNode.on_detections` →
`WorldTracker` → confirmed targets → `/semantic/targets` + `/targets/markers`.
This is interactive (checking topics/TF/markers as each piece comes up), not
a scripted procedure — don't build tooling for it, just check it live. Must
run directly on the robot (confirmed 2026-08-27: OAK-D present via `lsusb`).

**1. Drivers** (odom, static TF chain incl. `camera_link`):
`bl dome2 robot.launch.py --options "drivers"`

**2. OAK-D detection only** — do **not** use `--options vision` (that also
starts `dome_vision_ros`'s legacy `semantic_map_node`, the one F33 replaces):
`bl dome_vision_ros dome_vision_ros.launch.py --config
"$DOME_VISION_CONFIG" --depth true` (`.bashrc` already exports
`DOME_VISION_CONFIG` to the right path; no default `--config`, and the node
resolves a relative one against the launching shell's cwd, not the workspace
root, so a literal relative path breaks depending on where you run it from).
Also requires `ROBOFLOW_API_KEY` exported in the shell (not persisted
anywhere — the yaml refuses to expand it if unset). Gotcha: the node only
publishes `/oak/detections_3d` once something has subscribed
(`get_subscription_count() > 0` gate) — a bare `ros2 topic hz
/oak/detections_3d` counts and will unstick it.
Check: `ros2 topic hz /oak/detections_3d`.

**3. SLAM** (`map`→`odom`):
`bl dome_nav robot_map.launch.py --map_name <name>` (SLAM only, no
Nav2/explorer — use this over `robot_explore.launch.py` for isolated
testing).
Check: `ros2 run tf2_ros tf2_echo map camera_link` — not in `ros2diag`'s
`r2tfcheck` predefined pairs, so this one is manual.

**4. dome_semantic node** — no launch file exists yet (TF33.8), `ros2 run`
only:
`ros2 run dome_semantic semantic_map_node --ros-args -p map_name:=<name> -p
publish_every_n:=5`
Check: `ros2 topic hz /semantic/targets`, `/targets/markers`; `ros2 topic
echo /semantic/targets` for content; `/targets/assoc_diag` if
`use_class_profiles` is on.

**On shutdown**: check the persisted file matches what was seen live —
`~/.dome/semantic_maps/<map_name>.json`.

**Test**: manual — real-robot run, findings recorded in `02-doc/current.md`.

## TF33.1 — `dome_semantic_msgs` package

**Status**: done

Already exists as a sibling workspace package (`src/dome_semantic_msgs/`,
committed, `ament_cmake`, no node deps) and **matches the original spec
exactly**:

- `SemanticTarget.msg` — `schema_version` (uint8), `target_id` (string),
  `label` (string), `pose` (`geometry_msgs/Pose`, `map` frame, yaw via
  orientation), `observation_count` (uint32), `last_seen`
  (`builtin_interfaces/Time`), `track_ids` (string[]).
- `SemanticTargetArray.msg` — `std_msgs/Header` + `SemanticTarget[]`.

Both message comments already document the ownership split ("Owned/published
by dome_semantic; consumed by the dome_mission go-to-target behavior").

**Test**: `colcon build` clean; `ros2 interface show` matches spec — *verify
this still holds*, but no further authoring work is needed here.

## TF33.2 — `dome_semantic` package: port the tracker core (pure)

**Status**: done (2026-08-02)

New sibling repo `~/ros2_ws/src/dome_semantic` (bootstrapped from `~/j3`:
`.claude/`, `02-doc/`, `03-features/`, `04-tasks/`, `05-issues/`). F33/TF33
records stayed in `dome_nav` at first, per F35's relocate-with-the-code
pattern. **Update (2026-08-03)**: relocated here — now that TF33.1–TF33.4/
TF33.6 are done, this is the file's permanent home.

**Ported, behavior-preserving** (tolerances/thresholds unchanged):
`world_tracker.py` and its pure dependency closure — `association.py`,
`class_profiles.py`, `size_estimate.py`, `targets.py`, `tracker_config.py`,
`geometry.py` (pulled in transitively via `size_estimate.estimate_size_m`'s
use of `geometry.Intrinsics`).

**One deliberate deviation**: `world_tracker.py` needs only `cosine_sim` from
`dome_vision`'s `embedding.py`, but that file also defines
`EmbeddingExtractor`, pulling in `torch`/`torchvision`/`cv2` at module level —
too heavy for a ROS-free tracking core. `cosine_sim` was extracted into a new
15-line `embedding_similarity.py`; `EmbeddingExtractor` stays in `dome_vision`
(image inference, not tracking math — no test imported `embedding.py`).

**Not done**: deleting anything from `dome_vision`. `dome_vision_ros`'s
`semantic_map_node.py` still imports `dome_vision.world_tracker.WorldTracker`
directly and is the live, deployed tracker — cleanup waits until
`dome_semantic`'s own ROS node (TF33.3/TF33.4) is proven, per the same
delete-after-validation pattern F35/TF35 T06 used.

See `dome_semantic/02-doc/notes.md`'s "Watch list": four **not-done**
`dome_vision` features target this same code and stay `dome_vision`'s
concern until that cleanup — after which they'd need re-authoring against
`dome_semantic`, not a silent carry-over.

- **F39** — duplicate-target collapse
- **F40** — odom-stopped tight association radius
- **F56** — `WorldTracker` architecture split
- **F57** — target data-model consolidation

**Test**: dome_vision's pure tracker tests came along and pass under plain
`pytest` — 83 pass (`/usr/bin/python3 -m pytest test/`); `colcon build
--packages-select dome_semantic` clean. Two tests
(`test_appconfig_world_tracker_section`,
`test_appconfig_world_tracker_defaults_when_absent`) were dropped as
out-of-scope — they test `dome_vision`'s own `AppConfig`, not `WorldTracker`.
`tests/conftest.py`'s cwd-fixture and `examples/configs/class_profiles.yaml`
were ported so relative paths still resolve.

## TF33.3 — `map`-frame recording + re-basing on map jumps

**Status**: done (2026-08-02)

**Not a port** — unlike TF33.2, none of this existed before.
`dome_vision_ros`'s `semantic_map_node.py` only transforms camera→**`odom`**
(never `map`) and has no re-basing logic; F33's G1 decision (frame of record
= `map`, re-base on `map→odom` jumps) had never been implemented.

**`dome_semantic/tf_adapter.py`** — ported `TFAdapter` (generic
source/target-frame transform via an injected `tf2_ros.Buffer`), retargeted
to `map`. One behavior change: the lookup now uses the detection's own stamp
instead of time-zero/"latest available" — F33 G1 says "at observation time,"
and the original silently ignored its own `stamp` parameter.

**`dome_semantic/map_rebasing.py`** (new, pure, no ROS imports) —
`PlanarTransform(x, y, yaw)` plus SE(2)
`apply_transform`/`invert_transform`/`compose_transforms`;
`has_jumped(old, new, epsilon_m, epsilon_rad)`; `rebase_delta(old, new)`
composes old→new-map-frame transforms; `rebase_tracker(tracker, delta)`
re-bases each stored target's `xyz_world`, `position_history`, and
`pos_welford_mean` in place (z untouched — SLAM corrections are planar).

**`dome_semantic/semantic_map_node.py`** (new) — subscribes
`/oak/detections_3d`; `maybe_rebase()` looks up `map→odom` each tick, seeds a
baseline on first success (no false jump on frame one), and re-bases on a
detected jump; missing TF warns (throttled) and drops the detection without
crashing.

**Scope boundary vs. TF33.4**: no `SemanticTargetArray` publishing or param
wiring yet — this node only proves the TF integration end-to-end, using a
default `WorldTrackerConfig()`.

**Test**: 25 new tests (`test_tf_adapter.py`, `test_map_rebasing.py`,
`test_semantic_map_node.py`) — known transform → expected map-frame position;
synthetic `map→odom` jump → targets re-based to identical positions (SE(2)
round-trip + identity-delta no-op); missing TF → warned + dropped, no crash.
Node tests follow `dome_nav`'s `tf2_ros.TransformListener`-patching pattern.
110 total tests pass; `colcon build --packages-select dome_semantic` clean.

## TF33.4 — Typed publishing + node wiring

**Status**: done (2026-08-03)

`SemanticMapNode` now publishes `SemanticTargetArray` on `/semantic/targets`
(already subscribed by `dome_mission`'s `label_resolver.py`),
`/targets/markers` in `map` frame (sphere + label + leader-line per confirmed
target, faint dots for potentials), unthrottled `/targets/assoc_diag` (JSON,
only when `use_class_profiles` is on), and a `/describe_scene` Trigger
service. `/semantic/targets` and `/targets/markers` are throttled by a new
`publish_every_n` param (default 5) — cadence stays separate from
`WorldTrackerConfig`, which owns tracking-behavior tuning only.

**Confirmation-threshold params**: new `dome_semantic/tracker_params.py`
(`declare_tracker_config(node)`) walks `WorldTrackerConfig.model_fields` and
declares each as a ROS param (skips `class_profiles_inline`, a non-scalar
type, and unused `fx`/`fy`) — mirrors dome_nav's F34 "dataclass is the single
source of truth" pattern, adapted for pydantic's `model_fields`. It's a pure
`node`-duck-typed helper (`declare_parameter`/`get_parameter` only), so it's
tested with a `FakeNode` — same testability trade as `declare_frontier_params`.

**Considered and deferred**: dome_nav's fuller pattern
(`ParameterDescriptor(description=...)`, `ros_important`/`ros_dynamic`
metadata, strict bool/int/float type gating) — skipped since
`WorldTrackerConfig` is pydantic with a `str` field (`class_profile_path`)
dome_nav's narrow gate doesn't support, and `ros_important`/`ros_dynamic` are
documentation-only no-ops today anyway. Revisit if `tracker_params.py` grows
a real `ros2 param describe` consumer.

**Consumer is `dome_mission` (already built, TF35 T05) — this task only
publishes.** Nothing in dome_nav subscribes to this topic.

**Test**: `test_tracker_params.py` (4 tests — declare/read round-trip, field
coverage minus exclusions, launch-override precedence, `None`-default
handling) + 5 new `test_semantic_map_node.py` tests (confirmed-target publish
fields, potentials excluded, throttle honored, `/describe_scene` with/without
targets). 119 total tests pass; `colcon build --packages-select
dome_semantic_msgs dome_semantic` clean (after clearing a stale, unrelated
`build/dome_semantic_msgs` CMake cache).

**Literate**: full 01-literate/ set generated for dome_semantic
(00-overview.md theory-of-operation plus one chapter per module) — the
package had none before this task. Extended under TF33.6 to cover
persistence.

## TF33.5 — nav_manager consumes the typed msg

**Status**: superseded by F35 (2026-07-31) — consumer moved to `dome_mission`,
not dome_nav (F33 G9)

Label→pose resolution lives in the mission layer; dome_nav never depends on
`dome_semantic_msgs`. **Already done** via `dome_mission`'s
`label_resolver.py` + `mission_node`'s schema-version-gated
`SemanticTargetArray` subscription — the G2 contract fix (typed msg replacing
schemaless JSON) landed there too. This task stays only as a pointer — *no
work remains here*.

## TF33.6 — Persistence keyed to SLAM map identity

**Status**: done (2026-08-03)

New `dome_semantic/semantic_persistence.py`:
`save_semantic_map`/`load_semantic_map` write/read
`~/.dome/semantic_maps/<map_name>.json` (mirrors `explorer_manager_node`'s
`map_name` param and `slam_manager`'s `--map_name` convention, same
`~/.dome/` root as `slam_maps/`/`telemetry/`). The file is a small envelope,
`{"map_name": ..., "targets": [...]}`, wrapping `WorldTracker.to_json()`'s
bare-list format rather than teaching the pure tracker about map identity.

**Matching a save to a load**: primary key is the sanitized `map_name`
filename, but the sanitizing regex is lossy (`"room a"` and `"room#a"` both
become `room_a.json`) — so the envelope's own `map_name` field is a second,
independent check. Missing file → fresh tracker, no warning (normal first
run). Anything else that doesn't match — wrong `map_name`, or an
unrecognized shape — falls into one path: fresh tracker + warning, **never a
silent merge**.

**Decided against migrating the old bare-array format**: no such file has
ever existed at the new keyed path, so a migration branch would be
speculative code for an unreachable case. The style-guide MUST
(persisted-format changes preserve old files or ship defaults) is satisfied
by the safe fresh-map fallback, not a converter.

**Node wiring**: new `map_name` param (default `"unknown"`, matching
`explorer_manager_node`) selects which saved map to restore.
`SemanticMapNode.__init__` builds its tracker via
`load_semantic_map(self.map_name, declare_tracker_config(self), ...)`
instead of a bare `WorldTracker(...)`; a new `node.save()` runs from
`main()`'s `finally` block — this is a plain `Node`, not a `LifecycleNode`,
so that's the shutdown hook, not `on_shutdown`.

**Test**: `test_semantic_persistence.py` (6 tests — round-trip, missing
file, unrecognized-format fallback, filename-collision mismatch, path
sanitization, envelope contents) + 2 new `test_semantic_map_node.py` tests
(construction restores a saved map, `save()` writes tracker state). 127
total tests pass; `colcon build --packages-select dome_semantic` clean.
Literate: new `12-semantic_persistence.md`; `13-semantic_map_node.md`
(renumbered) gained a "Persistence" section; `00-overview.md` updated to
match.

## TF33.7 — Fake detection producer for sim

**Status**: not done

`tools/fake_detections.py` (or a `dome_semantic` test util) publishes
`/oak/detections_3d` from a scripted scenario (object list + noise + dropout),
analogous to `tools/nav_intent_check.py`. This unlocks sim-based regression of
the integrated mode without OAK hardware (G6) and feeds the TF33.8 integration
test.

**Test**: smoke test — node under test confirms a scripted object end-to-end
in sim time.

## TF33.8 — Perception+SLAM+explore+semantic sub-stack

**Status**: not done

**Launch ownership is already settled** (F33 G9 / TF35 T07): the top-level
launch is `dome_mission`'s `mission_explore.launch.py`. *This task owns only
the sub-stack composed into that launch* — not a second top-level launch.

Delivers the OAK-D + `slam_toolbox` + Nav2 + `explorer_manager_node` +
`dome_semantic` group (in `robot_explore_semantic.launch.py` or a dedicated
include), with documented ordering — TF chain before detections flow, reusing
`sim_nav_full`'s proven `map→odom` wait pattern.

No direct `/intent` wiring into the explorer here — that's `dome_mission`'s
(done, TF35 T04). `mission_explore.launch.py` currently `bl.include`s this
sub-stack's *absence* with a "TF33 uncoded" note; landing this task means
updating that include, not writing a fresh launch file.

**Also includes** the Phase A ingestion-gating decision (F33 constraints):
gate semantic ingestion on robot motion, or accept degraded association while
driving — *measure and pick one, record why*. Sim variant uses the TF33.7
fake producer.

**Test**: sim integration test (marked ROS2-runtime per style guide) — explore
with fake detections → semantic map contains the scripted objects in `map`
frame within tolerance. Manual: real-robot run recorded in notes.

## TF33.9 — Pi CPU headroom measurement

**Status**: not done, manual

Run vision + explore + semantic map together on the Pi; record MPPI control
rate (baseline 8.6 Hz vs 20 desired), TF queue drops, load average. Image pubs
off, on-device NN only. Decides whether Phase A ships on-Pi or needs rate
caps/offboard (G7).

**Test**: manual — numbers recorded in `02-doc/notes.md`.

## TF33.10 — Docs, literate, current.md

**Status**: not done

Update `02-doc/current.md` (F33 underway, Phase A status), regenerate literate
for every changed dome_nav Python module, note the new packages in
README/CLAUDE.md if layout docs reference package lists.

**Test**: full suite green (`/usr/bin/python3 -m pytest test/`) + `colcon
build` clean across dome_nav, dome_semantic, dome_semantic_msgs.
