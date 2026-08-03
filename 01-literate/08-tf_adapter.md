---
version: "1.0"
generated: "2026-08-03"
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
        result = self.tf_buffer.transform(point, self.target_frame)
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

- **Every caller treats `None` the same way: drop this one point, keep
  going.** `SemanticMapNode.on_detections` counts drops and logs a single
  throttled warning if *every* detection in a message was dropped, rather
  than warning once per dropped point — see `13-semantic_map_node.md`.
- **This adapter has no retry or buffering of its own.** A single missed
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
