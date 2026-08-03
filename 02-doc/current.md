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
  this, just check it live.
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
