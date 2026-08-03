---
version: "1.0"
generated: "2026-08-03"
---

# `class_profiles.py` — Teaching the Tracker What Kind of Object It's Looking At

## The problem: not all objects behave the same

A generic tracker treats every object identically: same association radius,
same confirmation threshold, same drift tolerance. But a coffee mug sitting
on a table and a person walking through the scene have almost nothing in
common physically — one never moves, the other moves constantly; their sizes
differ by an order of magnitude; conflating them with one set of thresholds
means either the mug is too twitchy about tiny odometry drift, or the person
is falsely "confirmed" as a stationary landmark after a few seconds of
standing still.

`class_profiles.py` (F38, PASA — Profile-Aware Spatial Association) gives
each object *class* — not each instance — a declarative bundle of physical
priors: expected size range, expected motion, how tightly a re-observation
should be trusted to be "the same object." `association.py`'s PASA cost
function (see `07-association.md`) reads these profiles; the simpler
baseline association path (`find_match_baseline`) ignores them entirely and
uses one fixed radius for everything.

## The profile itself

```python
class TargetClassProfile(BaseModel):
    canonical_class: str
    display_name: str | None = None
    abbrev: str | None = None
    detector_labels: list = []
    height_range_m: tuple
    diameter_range_m: tuple
    aspect_ratio_range: tuple
    max_stationary_speed_mps: float
    size_confidence_floor: float = 0.5
    depth_noise_scale: float = 1.0
    merge_radius_m: float | None = None
    drift_tolerance_m: float | None = None
```

Two fields carry outsized weight in association behavior, worth calling out
individually:

- **`max_stationary_speed_mps`** feeds `association.TargetAssociator.is_stationary`
  — a class-specific speed threshold under which a target's observed motion
  is attributed to sensor/odometry noise rather than the object actually
  moving. A `0.02 m/s` default (2 cm/s) is generous noise tolerance for
  something that's supposed to never move; a class profile for something
  that *can* move slightly (say, on a vibrating surface) could set this
  higher without every other class's tolerance changing.
- **`drift_tolerance_m`**, when set, *replaces* the default
  `confirmed_assoc_mult * max_assoc_dist_m` confirmed-target association
  radius for that class specifically (see `association.py`'s
  `find_match_pasa`). The intent, per that function's own docstring: a known
  stationary class like a mug shouldn't need a wide re-association radius to
  tolerate odometry drift, because it never actually moves — a tight radius
  based on expected *sensor* noise alone is enough, and using it prevents
  two real, distinct mugs 0.5 m apart from being merged into one target
  under the wider default radius.

## Two ways to supply profiles

```python
def parse_class_profiles(entries: list) -> dict: ...
def load_class_profiles(path: str) -> dict: ...
```

`load_class_profiles` reads a YAML file (`class_profiles: [...]` at the top
level) and delegates to `parse_class_profiles`, which is the one that
actually validates each entry into a `TargetClassProfile` and keys the
result dict by `canonical_class`. `WorldTracker.load_profiles()` picks
between the two based on `WorldTrackerConfig.class_profiles_inline` (already
parsed, e.g. embedded in a launch-time config) vs. `class_profile_path` (a
file on disk) — `class_profiles_inline` wins when both are set. See
`tracker_params.py`'s literate doc for why `class_profiles_inline` in
particular is excluded from ROS-parameter declaration (it's a list, not a
legal scalar ROS param type).

## Detector labels vs. canonical classes: why the indirection

A detector might emit `"cup"`, `"coffee_cup"`, or `"mug_v2"` for what this
system wants to treat as one class. `detector_labels` on a profile lists
every raw label that maps to its `canonical_class`; two small helper
functions build lookup tables from that:

```python
def build_label_map(profiles: dict) -> dict:
    mapping = {}
    for canonical, profile in profiles.items():
        for lbl in profile.detector_labels:
            mapping[lbl] = canonical
    return mapping
```

`WorldTracker.associate()` runs every incoming observation's raw label
through this map (`self.label_map.get(obs.label, obs.label)`) before doing
anything else with it — so association, confirmation, and the published
`SemanticTarget.label` all operate on the canonical name, and a detector
model upgrade that renames its output classes doesn't require touching
`WorldTracker` itself, only the profile YAML. `build_abbrev_map` does the
same indirection for a profile's optional `abbrev` (a short display form),
used by describe-scene—style summaries.

## Observations

- **A profile's fields are all *priors*, not measurements** — `is_stationary`
  in `association.py` still checks actual observed motion against
  `max_stationary_speed_mps`; the profile only supplies the threshold, it
  doesn't assert the object *is* stationary. `diameter_range_m` is read too,
  but only as a normalization span for the PASA size-cost term
  (`association.pasa_cost_components`), not as a plausibility gate — nothing
  rejects a detection for falling outside the range. `height_range_m` and
  `aspect_ratio_range` aren't read by any function in this module at all;
  they look like the start of a plausibility-gate feature that hasn't been
  wired into `association.py` yet.
- **Every field beyond `canonical_class` has a class-level default or is
  `None`-able**, so a minimal profile (just a name and the three required
  physical-range tuples) is valid — PASA features degrade gracefully rather
  than requiring every knob to be set for every class.
- **YAML loading has no schema-version or migration story.** A renamed or
  removed field in `TargetClassProfile` would fail pydantic validation on
  load with a low-level error, not a friendly one — acceptable for a
  hand-authored, small config file, but worth knowing if this ever becomes a
  larger, machine-generated config.
