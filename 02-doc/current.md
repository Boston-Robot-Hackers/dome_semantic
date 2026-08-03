# Current status

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

## Open

- **F33/TF33 feature and task records still live in `dome_nav`**
  (`03-features/notdone/F33-semantic-exploration.md`,
  `04-tasks/notdone/TF33-semantic-exploration.md`), not here — same
  relocate-with-the-code pattern F35 used (moved at T08, once the extraction
  was complete), not relocated on day one. This package has no `.md` task
  records of its own yet.
- **T03** — `map`-frame recording + re-basing on SLAM `map→odom` jumps: not
  started.
- **T04** — typed `SemanticTargetArray` publishing + node wiring (this
  package's first ROS node): not started.
- **T06–T10** — persistence, fake-detection sim tool, sub-stack launch
  integration, Pi CPU measurement, docs: not started.
