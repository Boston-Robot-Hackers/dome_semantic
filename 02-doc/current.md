# Current status

**2026-08-03** — see `02-doc/history.md` for the completed-work log.

## Open

- **Repo state**: `dome_semantic`, `dome_nav`, and `~/j3` are all committed
  and pushed to `origin/main` as of today. Nothing pending, nothing staged.
- **Next actual step: real-hardware verification, not T07/T08.** T01-T06 are
  done (msgs, tracker port, map-frame TF + re-basing, typed publishing,
  persistence) but have never been run against real OAK-D hardware — only
  unit-tested. No combined launch file exists yet (that's T08, not started),
  so verification is component-by-component on the real robot: OAK-D
  detections (`/oak/detections_3d`) -> `tf_adapter.py`'s `camera_link`->`map`
  transform -> `SemanticMapNode.on_detections` -> `WorldTracker` -> confirmed
  targets -> `/semantic/targets` + `/targets/markers`. The user launches each
  piece themselves; verification is interactive (checking topics/TF/markers
  as each piece comes up), not a scripted procedure — don't build tooling for
  this, just check it live. **This VM cannot do this verification itself**:
  no OAK-D hardware present (confirmed via `lsusb`) and no SSH path to the
  robot Pi is documented anywhere in the workspace — this only works run
  directly on the robot, which is the whole reason for the restart.

  **Per-component launch (real robot, no combined launch exists)**:
  - Drivers (odom, static TF chain incl. `camera_link`): `bl dome2
    robot.launch.py --options "drivers"`
  - OAK-D detection *only* — do **not** use `--options vision` here, that
    also starts `dome_vision_ros`'s own legacy `semantic_map_node` (the one
    F33 replaces) alongside the camera:
    `bl dome_vision_ros dome_vision_ros.launch.py --config
    dome_vision/dome_vision_ros/config/roboflow_oak.yaml --depth true`
    (no default `--config`, must be passed explicitly). Gotcha: the node only
    publishes `/oak/detections_3d` once something has subscribed to it
    (`get_subscription_count() > 0` gate) — a bare `ros2 topic hz
    /oak/detections_3d` counts and will "unstick" it.
  - SLAM (`map`->`odom`): `bl dome_nav robot_map.launch.py --map_name <name>`
    (SLAM only, no Nav2/explorer — use this over `robot_explore.launch.py`
    for isolated testing)
  - `dome_semantic`'s node — no launch file exists for it, `ros2 run` only:
    `ros2 run dome_semantic semantic_map_node --ros-args -p
    map_name:=<name> -p publish_every_n:=5`

  **Diagnostic checks at each step** (existing repo conventions, not new
  tooling):
  - TF chain the node actually needs: `ros2 run tf2_ros tf2_echo map
    camera_link` (note: `ros2diag`'s `r2tfcheck` predefined pairs do *not*
    include `camera_link`, so this one has to be manual)
  - `ros2 topic hz /oak/detections_3d`, `/semantic/targets`,
    `/targets/markers`
  - `ros2 topic echo /semantic/targets` for content, `/targets/assoc_diag`
    if `use_class_profiles` is on
  - On node shutdown, check the persisted file matches what was seen live:
    `~/.dome/semantic_maps/<map_name>.json`
- **T07 (fake detection producer) — designed, deferred.** Full design exists
  (a pure `fake_scenario.py` scenario model — object list + Gaussian noise +
  seeded dropout — plus a `tools/fake_detections.py` live publisher mirroring
  `dome_mission/tools/nav_intent_check.py`, plus a smoke test), verified
  against `WorldTrackerConfig`'s actual confirmation thresholds. Deferred
  because it's "too much" until real-hardware verification shows whether it's
  actually needed — the design lived in a local plan file on the prior VM
  session and was not committed; re-derive or ask if it turns out to be
  needed after all.
- **T08–T10** — sub-stack launch integration, Pi CPU measurement, docs: not
  started. T05 superseded by F35 (consumer is `dome_mission`, not this
  package).

## Session note

Picking this up on the robot: ask what the real-hardware verification found
before planning any new code — the answer determines whether T07/T08 are
still the right next tasks or need rethinking.
