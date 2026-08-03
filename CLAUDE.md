# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

Read and follow all rules in the `.claude/` folder:
- `.claude/process.md` — development workflow and feature/task tracking rules
- `.claude/style_guide.md` — coding standards, style rules, and review checklist
- `02-doc/current.md` — session handoff and current status
- `02-doc/notes.md` — semi-permanent project notes

We are developing dome_semantic, the semantic map for the DOME robot (F33).
It tracks confirmed object targets (two-tier confirmation, label-constrained
association, lost/removed timeouts) in the SLAM `map` frame and publishes
`SemanticTargetArray` (`dome_semantic_msgs`) for `dome_mission`'s go-to-label
behavior to consume. Neutral package: depends only on `dome_semantic_msgs`
and TF — `dome_nav` never depends on it and vice versa.

Literate docs are in `01-literate/`, project docs are in `02-doc/`, features are
in `03-features/`, tasks are in `04-tasks/`, issues are in `05-issues/`, and the
spec is in `02-doc/spec.md`.

## Sibling packages

- **dome_nav** — navigation/SLAM primitives (explorer, slam_manager). No
  mission or semantic knowledge.
- **dome_mission** — mission-sequencing layer; owns `/intent`; consumes this
  package's `SemanticTargetArray` for label→pose resolution.
- **dome_semantic_msgs** — `SemanticTarget`/`SemanticTargetArray` messages
  (ament_cmake interface package) this package publishes.
- **dome_vision** — OAK-D detection/depth pipeline; this package's
  `world_tracker.py` (and its pure dependency closure) was ported from there
  (F33 T02), behavior-preserving. `dome_vision` keeps
  `EmbeddingExtractor`/OAK/depth/detection publishing.
