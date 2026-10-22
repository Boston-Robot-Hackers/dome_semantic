# Chores

Simple bug fixes and refactors (no spec/behavior change). One line each:
- [ ] <what and why>
- [x] Import tf2_geometry_msgs in tf_adapter.py: without it Buffer.transform
  raised TypeException on PointStamped (found in TF33.0 on the robot; mocked
  unit tests hid it). Added real-Buffer regression test.
