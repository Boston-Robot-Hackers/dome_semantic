# dome_semantic — Spec

## Purpose

Semantic map for the DOME robot (F33). Tracks confirmed object targets in
the SLAM `map` frame, so `dome_mission`'s go-to-label behavior can resolve a
label (e.g. "can") to a pose without either `dome_nav` or `dome_mission`
depending on the object-detection stack directly.

## Behaviors

- **Track**: ingest `(xyz, label, frame_num, track_id, size_est)` observations
  into a two-tier state machine — `PotentialTarget` accumulates evidence,
  `ConfirmedTarget` holds a reliable estimate once enough frames/time have
  accumulated. Association is label-constrained (a cup observation never
  merges into a can's track).
- **Record in `map` at observation time**: each detection is transformed
  `camera_link → map` at its own stamp. Stored targets are **not re-based**
  when SLAM steps `map → odom` (F36).
- **Persist across visibility gaps**: a confirmed target unseen for
  `lost_timeout_s` is marked lost (F36). It is **kept indefinitely if it
  had at least `min_keep_obs` observations**; otherwise it is deleted once
  lost, since a short burst of evidence is more likely a false confirmation
  than a real object (F37). Kept lost targets keep publishing (consumers
  judge them by `last_seen`), are drawn dimmed in RViz, and are saved.
  Same-label confirmed targets closer than the class's `merge_radius_m`
  merge into the older ID. Potentials still expire after `lost_timeout_s`.
  `to_json`/`from_json` round-trip confirmed targets across process
  restarts.
- **Publish** (later task): `SemanticTargetArray` on `/semantic/targets`, the
  contract `dome_mission` already consumes.

## Support tooling

Hardware checks needed to verify F33 on the robot live here too, even when
they span other packages. The first is the **power load test**: the robot's
5 V supply browns out under OAK-D load, which blocks the TF33.0 hardware
runs.

## Origin

`world_tracker.py` and its pure dependency closure (`association.py`,
`class_profiles.py`, `size_estimate.py`, `targets.py`, `tracker_config.py`,
`geometry.py`) were ported from `dome_vision` (F33 T02), behavior-preserving —
same tolerances/thresholds, same test suite. One deviation: `cosine_sim` was
split out of `dome_vision`'s `embedding.py` into a small local
`embedding_similarity.py`, so this package avoids `embedding.py`'s
`torch`/`torchvision`/`cv2` dependencies (needed only by `EmbeddingExtractor`,
which stays in `dome_vision` — the tracker only ever compares
already-extracted embedding vectors, never runs extraction itself).

See `process/03-features/notdone/F33-semantic-exploration.md` and
`process/04-tasks/notdone/TF33-semantic-exploration.md` for the full feature/task
record.
