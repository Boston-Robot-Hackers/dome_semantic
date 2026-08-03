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
- **Persist across visibility gaps**: a confirmed target survives brief
  occlusion/pan-away (`lost_timeout_s`) before being dropped
  (`remove_timeout_s`); `to_json`/`from_json` round-trip confirmed targets
  across process restarts.
- **Publish** (later task): `SemanticTargetArray` on `/semantic/targets`, the
  contract `dome_mission` already consumes.

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

See `03-features/notdone/F33-semantic-exploration.md` and
`04-tasks/notdone/TF33-semantic-exploration.md` for the full feature/task
record.
