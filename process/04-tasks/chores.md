# Chores

Simple bug fixes and refactors (no spec/behavior change). One line each:
- [ ] <what and why>
- [x] Import tf2_geometry_msgs in tf_adapter.py: without it Buffer.transform
  raised TypeException on PointStamped (found in TF33.0 on the robot; mocked
  unit tests hid it). Added real-Buffer regression test.
- [x] Wait up to 0.2 s for the detection-stamp TF in tf_adapter.py (and spin
  the node in a MultiThreadedExecutor so TF keeps arriving): odometry TF lags 10-150 ms
  behind detection stamps, so the zero-wait lookup always extrapolated and
  every detection was dropped (found in TF33.0 on the robot). Added a
  late-arriving-TF regression test.
