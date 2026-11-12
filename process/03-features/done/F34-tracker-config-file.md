# Feature description for feature F34

Feature file name must be `FNN-<slug>.md` where `NN` matches the feature number.

# F34 — Ship the tracker config so PASA actually runs

**Priority**: High

**Done:** yes

**Tasks File Created:** yes

**Tests Written:** yes

**Test Passing:** yes

**Description**: `semantic_map_node` declares every `WorldTrackerConfig` field as
a ROS parameter (`tracker_params.py`), but nothing ever sets them. So the node
always runs at dataclass defaults: **PASA off** and a flat 0.6 m confirmed
radius. Two cans 0.5 m apart can merge into one target.

This is the same bug `dome_vision` fixed in its F68 (its issue I03). This
feature fixes it here **without changing the design**.

### Decision: keep ROS parameters, ship a params file

- **Keep `tracker_params.py` as is.** Every tracker field stays a ROS parameter,
  so `WorldTrackerConfig` remains the single source of truth.
- **Ship two files in `config/`:**
  - `semantic_map.yaml` — the tracker's scalar settings, PASA on, matching the
    values the robot runs today in `dome_vision`'s `roboflow_oak.yaml`.
  - `class_profiles.yaml` — the `can` and `cup` profiles, including `abbrev`,
    `merge_radius_m` and `drift_tolerance_m`.
- **The launch file always passes them.** The node never again starts on bare
  defaults by accident.
- **No dependency on `dome_vision`.** Pointing at its YAML would tie this
  package to the repo it was split out of (F33 G4).

### Also ported from F68

- `WorldTracker` raises when `use_class_profiles` is true but no profiles load.
  That silent case is what let the bug hide.

### Out of scope

- The F33 TF33.0 SLAM re-basing run. It stays in F33 and uses this config once
  it lands.
- Removing the semantic layer from `dome_vision`. That is a separate feature
  there, after this one and TF33.0 pass.
- Re-tuning any tracker value. The numbers are copied as-is.

## How to Demo

**Setup**: robot on external power, OAK-D up via `dome_vision`'s vision node
only (no `dome_vision` semantic node). Two cans about 0.5 m apart, ~1.2 m in
front of the camera.

**Steps**:
1. `bl dome_semantic semantic.launch.py --map_name f34test --static_map_odom true`
2. `ros2 param get /semantic_map use_class_profiles`
3. `ros2 topic echo /semantic/targets --once`
4. `ros2 topic hz /targets/assoc_diag`

**Expected output**:
- `use_class_profiles` is `True`.
- `/semantic/targets` holds **two** `can` targets, not one.
- `/targets/assoc_diag` is publishing (it is silent when PASA is off).

## Process Gate

After creating this feature file and the corresponding task file, **stop and present the plan to the user**. Do not write any code or content until the user gives explicit approval to proceed.
