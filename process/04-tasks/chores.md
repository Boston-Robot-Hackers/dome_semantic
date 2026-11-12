# Chores

Simple bug fixes and refactors (no spec/behavior change). One line each:
- [ ] <what and why>
- [x] Replace the `MultiThreadedExecutor` in `semantic_map_node.py` with
  plain `rclpy.spin(node)`. TF now arrives on its **own** node
  (`semantic_map_tf_listener`) and thread (`spin_tf`). Not
  `spin_thread=True`: on the shared node, rclpy's one-executor-per-node rule
  let the listener's executor steal the node (late-TF test failed), and its
  thread printed an `ExternalShutdownException` traceback on Ctrl-C.
  `destroy_node` must not join that thread (deadlocks inside
  `rclpy.shutdown()`); it's a daemon. Why: the
  multi-threaded executor cost ~40% of a core dispatching the 67 Hz `/tf`
  (robot, 2026-11-10: 46.2% vs 8.6%). Late-TF regression test now runs on a
  `SingleThreadedExecutor`; added a test that `main` uses plain spin.
  The listener node uses `use_global_arguments=False`: launch's
  `__node:=semantic_map` remap renamed it too (duplicate-name rosout warning
  on the robot). Naming, shutdown and destroy tests in
  `test_semantic_map_node_lifecycle.py`.
  Robot check 2026-11-11 (vision + `--static_map_odom true`): semantic node
  ~10% of a core, down from 42–48%; `/targets/assoc_diag` still 10 Hz;
  final build's Ctrl-C saves cleanly: no traceback, no hang, only the one
  startup "no TF" drop.
- [x] RViz markers name targets the way `dome_vision`'s annotated image does
  (`CN4` = the class profile's `abbrev` + target ID, via `short_label`;
  first two letters upper-cased when a class has no abbrev),
  instead of `T4 can/1700` (the number was `observation_count`, which kept
  climbing). Sphere 8 cm, image-box green; 5 cm label just above it; no
  connecting line; potential dots 4 cm. Why: markers were tiny and the label
  floated far off. Marker-content and `short_label` tests added. **Still to
  do:** look at it in RViz.
- [x] Import tf2_geometry_msgs in tf_adapter.py: without it Buffer.transform
  raised TypeException on PointStamped (found in TF33.0 on the robot; mocked
  unit tests hid it). Added real-Buffer regression test.
- [x] Wait up to 0.2 s for the detection-stamp TF in tf_adapter.py (TF keeps
  arriving on the listener's own thread; originally a MultiThreadedExecutor,
  replaced later for CPU cost): odometry TF lags 10-150 ms
  behind detection stamps, so the zero-wait lookup always extrapolated and
  every detection was dropped (found in TF33.0 on the robot). Added a
  late-arriving-TF regression test.
- [x] Add `process/02-doc/power_load_test.md`, a runbook for the staged OAK
  power load test, linked from `power_system_testing.md` step 2, so the
  procedure and the 2026-11-05 lessons (USB 2 fallback, USB 3 Wi-Fi
  interference) aren't lost in `current.md`.
