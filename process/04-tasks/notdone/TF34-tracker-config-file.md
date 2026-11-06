# TF34 Ship the tracker config for Feature F34

Task file name must be `TFNN-<slug>.md` where `NN` matches the feature number.

Each step is numbered `TFNN.N`, matching this file's own `TFNN` (e.g. `TF03.0`,
`TF03.1`, ...), starting at `.0`.

For each task step, add a test when feasible. If not feasible, note why.

## TF34.0 — Fail loudly when PASA has no profiles

**Status**: done (2026-10-24)

**Description**: Port `dome_vision` F68's guard. In `WorldTracker.__init__`,
raise `ValueError` when `use_class_profiles` is true and no profiles loaded from
either `class_profiles_inline` or `class_profile_path`.

*Test*: constructing a `WorldTracker` with `use_class_profiles=True` and no
profile source raises.

## TF34.1 — Ship `config/class_profiles.yaml`

**Status**: done (2026-10-24)

**Description**: Copy the `can` and `cup` profiles from `dome_vision`'s
`roboflow_oak.yaml` (`world_tracker.class_profiles_inline`) into a top-level
`class_profiles:` list, values unchanged.

*Test*: `load_class_profiles` on the shipped file returns `can` and `cup`, each
with `abbrev`, `merge_radius_m` and `drift_tolerance_m` set.

## TF34.2 — Ship `config/semantic_map.yaml` and install both files

**Status**: done (2026-10-24)

**Description**: A ROS params file for the `semantic_map` node with the tracker's
scalar settings, matching `roboflow_oak.yaml`. `use_class_profiles: true` and
the `assoc_cost_*` weights are the ones that matter. Add both files to
`setup.py`'s `data_files` under `share/dome_semantic/config`.

*Test*: the file's parameters build a valid `WorldTrackerConfig` with
`use_class_profiles` true. Unknown keys must fail, so a typo can't hide.

## TF34.3 — Launch always passes the config

**Status**: done (2026-10-24)

**Description**: `semantic.launch.py` passes `semantic_map.yaml` to the node,
and sets `class_profile_path` to the installed `class_profiles.yaml`. Use
better_launch's own mechanism for package share paths and params files; no
hand-patched YAML.

*Test*: extend `test_semantic_launch.py`. The node's params include the params
file and a `class_profile_path` that resolves to an existing file.

## TF34.4 — PASA behaviour test on the shipped config

**Status**: done (2026-10-24)

**Description**: The feature's dedicated test task. Build a `WorldTracker` from
the shipped files. Confirm one `can`, then bring a second into view 0.5 m away,
as a spin survey does. They must stay **two** targets; at defaults (PASA off)
the 0.6 m confirmed radius absorbs the second.

Seen together from the first frame, both confirm even at defaults, so the
order matters and the test encodes it.

*Test*: this step is the test.

## TF34.5 — Hardware check on the robot

**Status**: not done

**Description**: Run F34's demo on external power. Record in
`process/02-doc/current.md` whether `use_class_profiles` reads true, the target
count for two cans 0.5 m apart, and the `/targets/assoc_diag` rate.

*Test*: manual and hardware-only; the notes record the command, setup and
observation.
