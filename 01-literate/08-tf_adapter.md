---
version: "1.2"
generated: "2026-10-22"
---

# `tf_adapter.py` — A Small, Deliberately Boring Wrapper Around TF

## What it does

One class, one method: `TFAdapter.transform(xyz, stamp)` takes a 3D point in
some source frame and returns it in some target frame, using ROS's [tf2](https://docs.ros.org/en/humble/Tutorials/Intermediate/Tf2/Tf2-Main.html)
transform tree — or `None` if the transform isn't available. In
`SemanticMapNode`, `source_frame="camera_link"` and `target_frame="map"`:
every detection's position gets run through this before it ever reaches
`WorldTracker`.

```python
def transform(self, xyz: tuple, stamp) -> "tuple[float, float, float] | None":
    point = PointStamped()
    point.header.frame_id = self.source_frame
    point.header.stamp = stamp
    point.point.x, point.point.y, point.point.z = xyz
    try:
        result = self.tf_buffer.transform(
            point, self.target_frame, timeout=Duration(seconds=TF_WAIT_S)
        )
        return (result.point.x, result.point.y, result.point.z)
    except (
        tf2_ros.LookupException,
        tf2_ros.ConnectivityException,
        tf2_ros.ExtrapolationException,
    ):
        return None
```

There isn't much here by design — this file's value is almost entirely in
what it *doesn't* do (see below) and in being small enough to mock
trivially in tests: the constructor takes an already-built `tf2_ros.Buffer`
rather than building one itself, so a test can hand it a `MagicMock` and
control exactly what `.transform()` returns or raises, with no live ROS
graph involved.

## The import that does nothing visible

```python
import tf2_geometry_msgs  # noqa: F401  registers PointStamped with tf2
```

`tf2_ros.Buffer.transform()` is **type-dispatched**: it looks up a
per-message-type transform function in a registry. Those functions are
registered as a *side effect of importing* `tf2_geometry_msgs`. Without the
import, a real buffer raises `TypeException: PointStamped is not loaded or
supported` on the first detection.

- **Why it hid for so long**: every unit test mocked `.transform()`, so the
  registry was never consulted. It surfaced only on the first real-robot run
  (TF33.0).
- **The guard against regression** is `test_transform_with_real_buffer`,
  which drives a real `tf2_ros.Buffer` with a static transform instead of a
  mock.

## Why `stamp` is a required argument, not "now" or "latest"

This adapter was ported from an earlier version living in `dome_vision_ros`
(F33 T03). The original had a subtle bug: it looked up the transform at
time-zero / "latest available" rather than at the detection's own capture
time. For a camera that's moving, "latest available" is *wrong* — by the
time a detection is processed, the robot may have moved, and transforming
the detection through the *current* transform rather than the transform *at
the moment the detection was captured* introduces a positional error
proportional to how much the robot moved in between.

F33's own design decision (G1: "detections are transformed into the `map`
frame *at observation time*") is exactly what fixing this bug required —
this port takes the message's own `stamp` and passes it straight through to
`tf_buffer.transform()`, so the lookup asks tf2 for the transform tree as it
existed at that specific instant, not whatever tf2 happens to have cached
most recently.

## Waiting briefly for a transform that hasn't arrived yet

Asking for the transform *at the detection's stamp* has a timing catch.
Detections are stamped ~2 ms before they arrive, but odometry TF lags
**10-150 ms** behind. A zero-wait lookup therefore always asked for a time
slightly *past* the newest transform in the buffer, raised
`ExtrapolationException`, and **every detection was dropped** — found on the
second real-robot run (TF33.0).

The fix is a bounded wait, `TF_WAIT_S = 0.2`: `Buffer.transform` polls until
the stamp's transform lands or the timeout expires.

- **Why 0.2 s**: comfortably above the observed worst-case lag, yet short
  next to the ~10 fps detection rate's tolerance for a stale callback.
- **The concurrency precondition**: the wait blocks inside the detection
  callback, so TF messages must keep being delivered *meanwhile*. The node
  spins in a `MultiThreadedExecutor`, and `TransformListener` subscribes in
  its own `ReentrantCallbackGroup`, so TF callbacks run on another thread
  while `on_detections` waits. Under a single-threaded executor the wait
  would always time out.
- **The guard** is a late-arriving-TF regression test: the transform is
  added to a real buffer from another thread after the lookup has begun.

## Why the exception handling was narrowed

The original also caught a blind `except Exception`. This port catches
exactly the three tf2 exceptions this codebase already treats as "the
transform genuinely isn't available right now" everywhere else a TF lookup
happens (`dome_nav`'s `explorer_manager_node.py`, and this same
package's own `semantic_map_node.lookup_map_to_odom`):
`LookupException` (frame doesn't exist / no connection between frames yet),
`ConnectivityException` (frames aren't connected in the tree), and
`ExtrapolationException` (the requested time is outside the buffer's known
range — too far in the past or, for a moving robot, slightly in the
future). A genuine bug elsewhere inside this method — a programming error,
not a transform-availability problem — now propagates as a real exception
instead of being silently swallowed and reported to the caller as "no
transform," which would make the bug much harder to notice.

## Observations

- **Mock-only tests can't catch registration bugs.** The real-buffer test
  above is the pattern to follow whenever a ROS library relies on
  import-time side effects.

- **Every caller treats `None` the same way: drop this one point, keep
  going.** `SemanticMapNode.on_detections` counts drops and logs a single
  throttled warning if *every* detection in a message was dropped, rather
  than warning once per dropped point — see `13-semantic_map_node.md`.
- **This adapter has no retry or buffering beyond the 0.2 s wait.** A single missed
  transform on one detection is just gone — there's no "try again next
  tick with the same point," because by next tick there's a new detection
  anyway. This is a fire-and-forget-per-observation design, consistent with
  the tracker being built to tolerate occasional gaps (that's what
  `lost_timeout_s` and the false-split-recovery logic in `association.py`
  are for) rather than requiring every single frame to succeed.
- **The class has no teardown / lifecycle of its own** — it holds a
  reference to a buffer it didn't create and never closes it. Ownership of
  the underlying `tf2_ros.Buffer`/`TransformListener` pair belongs entirely
  to whoever constructs the `TFAdapter` (in production, `SemanticMapNode`).
