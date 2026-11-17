---
version: "1.1"
generated: "2026-11-13"
---

# `tracker_config.py` — Every Tuning Knob, Documented Where It's Declared

## The single source of truth

`WorldTrackerConfig` is a `pydantic.BaseModel` holding every tunable
threshold `WorldTracker` and `TargetAssociator` read: association distances,
confirmation thresholds, timeout windows, the F38 PASA cost weights, camera
intrinsics, and convergence criteria. Roughly twenty fields, each with an
inline comment explaining not just *what* the value controls but *why* its
particular default was chosen — several comments reference the actual
reasoning behind a number (e.g. why `confirmed_assoc_mult` is 2.0 rather
than 1.0: "tolerates typical odometry drift while keeping two objects 1.2 m
apart from collapsing into one target").

That density of inline rationale is what makes `tracker_params.py`'s
introspection approach (declaring every field as a ROS parameter by walking
`model_fields`, see `11-tracker_params.md`) worth doing instead of
hand-copying a subset: the documentation for *why* a value is what it is
lives in exactly one place, and stays attached to the field even as the ROS
parameter surface is generated from it mechanically.

## Two families of knobs

The fields split cleanly into two groups, reflecting the two association
strategies in `association.py`:

**Baseline association** (always active): `max_assoc_dist_m`,
`confirmed_assoc_mult`, `min_frames`, `min_time_s`, `lost_timeout_s`,
`require_anchor`, `min_keep_obs` — the core confirm/lose lifecycle every
target goes through regardless of any other feature being enabled. A
confirmed target is marked lost after `lost_timeout_s`. There is no
forget-after-a-while timer (`remove_timeout_s` was removed by F36); instead,
a target that goes lost with fewer than `min_keep_obs` observations is
deleted at once (F37), and the rest are kept. The same timeout drops stale
potentials.

**F38 PASA association** (opt-in via `use_class_profiles`): everything
prefixed `assoc_cost_*`, plus `class_profile_path` /
`class_profiles_inline`, `stationary_window_s`, `size_confidence_floor`. The
module's own comment is explicit about this being additive, not a
replacement: *"Master switch for F38 PASA association. False = pre-F38
label+distance behavior."* Turning `use_class_profiles` off doesn't leave
these fields in some half-configured state — `association.TargetAssociator.find_match`
routes to `find_match_baseline` instead of `find_match_pasa` entirely, so
the PASA-only fields simply go unread.

## Why `class_profile_path` is `str | None`, not required

```python
class_profile_path: str | None = None
class_profiles_inline: list | None = None
```

Neither is required even when PASA is on — `WorldTracker.load_profiles()`
only attempts to load profiles `if self.config.use_class_profiles`, and even
then, an empty `self.profiles` dict is a valid (if degraded) state: PASA
association still runs, it just has no per-class overrides to apply,
falling back to the same default radius the baseline path would use. This
is what makes `class_profiles_inline` safe to exclude from ROS-parameter
declaration in `tracker_params.py` — a deployment that never sets it doesn't
lose PASA entirely, only the parts of PASA that depend on class-specific
priors.

## A config for confirmation timing, phrased as physical reasoning

```python
min_frames: int = 5
min_time_s: float = 1.0
```

These two together, not either alone, gate promotion (see
`world_tracker.WorldTracker.promote()`): an object needs *both* enough
independent sightings *and* enough elapsed wall-clock time. `min_frames`
alone would let a burst of detections in a fraction of a second (e.g. a
high-framerate detector momentarily catching five frames of the same
transient object) trigger confirmation; `min_time_s` alone would let a
single lingering detection re-counted every tick satisfy the threshold
without ever being independently re-observed. Requiring both is a
deliberate defense against either failure mode individually.

## Observations

- **`fx`/`fy` default to specific measured values** (`493.86`/`493.87`) —
  the comment notes these are "512×512 measured values," i.e. calibrated for
  a specific camera/resolution combination, not a generic placeholder. A
  different camera or resolution needs these overridden, not assumed
  correct by default.
- **This file has zero behavior** — no methods beyond what pydantic
  generates, no validators. All meaning is in field defaults and comments;
  every actual *use* of these values lives in `association.py` and
  `world_tracker.py`. Reading this file in isolation tells you what's
  tunable; it doesn't tell you what any value does without cross-referencing
  those two files.
- **Unknown keys are silently ignored.** pydantic's default drops extra
  fields, so a config still passing the removed `remove_timeout_s` (or any
  typo) builds without complaint. `model_config = {"extra": "forbid"}`
  would turn that into a construction error.
