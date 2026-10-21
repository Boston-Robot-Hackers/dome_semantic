# Current status

**2026-08-03** — see `02-doc/history.md` for the completed-work log.

## Open

- **Repo state**: `dome_semantic`, `dome_nav`, and `~/j3` are all committed
  and pushed to `origin/main` as of today. Nothing pending, nothing staged.
- **Next actual step: TF33.0, real-hardware verification** (see task file for
  the full bottom-up procedure and per-component launch/diagnostic commands).
  TF33.1-TF33.6 are done (msgs, tracker port, map-frame TF + re-basing, typed
  publishing, persistence) but have never been run against real OAK-D
  hardware — only unit-tested. No combined launch file exists yet (that's
  TF33.8, not started). **Now running on the robot** (confirmed 2026-08-27:
  OAK-D present via `lsusb`) — TF33.0 is in progress.
- **TF33.7 (fake detection producer) — designed, deferred.** Full design
  exists (a pure `fake_scenario.py` scenario model — object list + Gaussian
  noise + seeded dropout — plus a `tools/fake_detections.py` live publisher
  mirroring `dome_mission/tools/nav_intent_check.py`, plus a smoke test),
  verified against `WorldTrackerConfig`'s actual confirmation thresholds.
  Deferred because it's "too much" until TF33.0 shows whether it's actually
  needed — the design lived in a local plan file on the prior VM session and
  was not committed; re-derive or ask if it turns out to be needed after all.
- **TF33.8–TF33.10** — sub-stack launch integration, Pi CPU measurement,
  docs: not started. TF33.5 superseded by F35 (consumer is `dome_mission`,
  not this package).

## Session note

Picking this up on the robot: run TF33.0 before planning any new code — its
findings determine whether TF33.7/TF33.8 are still the right next tasks or
need rethinking.
