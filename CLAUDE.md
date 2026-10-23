# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

Read and follow all rules in the `.claude/` folder:
- `.claude/process.md` — development workflow and feature/task tracking rules
- `process/02-doc/current.md` — session handoff; only the `## Open` section
  matters for new work, see `process/02-doc/history.md` for the completed-work
  log
- `process/02-doc/notes.md` — semi-permanent project notes

Before writing or reviewing code, read and follow `.claude/style_guide.md`
(coding standards, style rules, and review checklist) — apply it yourself
before committing; do not substitute a generic/plugin review for it.

We are developing dome_semantic, the semantic map for the DOME robot (F33).
It tracks confirmed object targets (two-tier confirmation, label-constrained
association, lost/removed timeouts) in the SLAM `map` frame and publishes
`SemanticTargetArray` (`dome_semantic_msgs`) for `dome_mission`'s go-to-label
behavior to consume. Neutral package: depends only on `dome_semantic_msgs`
and TF — `dome_nav` never depends on it and vice versa.

All process files live under `process/`: literate docs in
`process/01-literate/`, project docs in `process/02-doc/`, features in
`process/03-features/`, tasks in `process/04-tasks/`, issues in
`process/05-issues/`, and the spec at `process/02-doc/spec.md`.

## Agent model selection

Default subagent dispatches to haiku; upgrade only when the task needs
judgment, not just data-gathering:
- **haiku** — file/log discovery, "where is X defined", dependency-closure
  scans, counting, formatting. Use the `Explore` agent type for this.
- **sonnet** — analysis, code review, writing, moderate reasoning, synthesis
  across subagent findings.
- **opus** — architecture decisions, novel debugging, cross-cutting design
  tradeoffs.

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
