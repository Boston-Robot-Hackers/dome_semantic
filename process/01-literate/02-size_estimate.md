---
version: "1.0"
generated: "2026-08-03"
---

# `size_estimate.py` — How Big Is the Thing You Just Saw?

## What problem this solves

Position alone doesn't always disambiguate objects. Two cups sitting close
together, briefly out of the camera's view and re-detected, could
plausibly be either "the same cup, slightly drifted" or "two different
cups." `SizeEstimate` gives the association logic (`association.py`) a
second, independent signal: how wide and tall does the detected bounding box
project to, in real-world metres, at the depth it was seen? Two detections
of genuinely the same physical object should agree on size even if their
positions have drifted a little; two different objects usually won't.

## The value type

```python
@dataclass
class SizeEstimate:
    width_m: float
    height_m: float
    aspect_ratio: float
    depth_quality: float  # 0.0–1.0; 0 means no usable depth
```

`depth_quality` is the field every consumer checks first.  It's binary in
this module's own implementation (`1.0` or `0.0` — see below) but typed as a
continuous `0.0–1.0` range deliberately, so a richer depth-confidence source
upstream (e.g. per-pixel stereo confidence from the OAK-D) could populate it
with a graded value without changing this dataclass's shape or any
consumer's comparison (`>= size_confidence_floor`).

## Projecting a bounding box to real-world size

```python
def estimate_size_m(bbox_pixels, depth_m, fx, fy) -> SizeEstimate:
    bw, bh = bbox_pixels
    intr = Intrinsics(fx=fx, fy=fy, cx=0.0, cy=0.0)
    depth_quality = 1.0 if depth_m > 0 else 0.0
    if depth_quality == 0:
        return SizeEstimate(
            width_m=0.0, height_m=0.0, aspect_ratio=0.0, depth_quality=0.0
        )
    width_m = bw * depth_m / intr.fx
    height_m = bh * depth_m / intr.fy
    aspect_ratio = height_m / width_m if width_m > 0 else 0.0
    return SizeEstimate(
        width_m=width_m,
        height_m=height_m,
        aspect_ratio=aspect_ratio,
        depth_quality=depth_quality,
    )
```

This reuses `geometry.Intrinsics` but with `cx=cy=0.0` — worth pausing on,
since it looks at first glance like a bug (real optical centers are rarely
exactly zero). It isn't: `pixel_to_xyz` needs the true optical center because
it projects an *absolute pixel position* into an absolute 3D point. This
function instead projects a *width in pixels* (a difference, `bw`, not a
position) into a real-world width — the offset-from-center term that `cx`
subtracts out cancels between the box's two edges regardless of where the
center actually is, so it's correctly omitted here rather than incorrectly
defaulted.

The formula itself is the same inverse-pinhole scaling used in
`geometry.pixel_to_xyz`: a pixel span, at a given depth, corresponds to a
real-world span of `pixels * depth / focal_length`. Applied separately to
width (via `fx`) and height (via `fy`), since a camera's horizontal and
vertical focal lengths can differ slightly.

## The all-or-nothing depth quality

Unlike `geometry.pixel_to_xyz` (which returns `None` on invalid depth),
`estimate_size_m` always returns a `SizeEstimate` — just one with every
numeric field zeroed and `depth_quality=0.0`. This is a small but consistent
design choice: callers that pattern-match on "is there a usable size here"
check `depth_quality`, never do a `None`-check on the return value itself.
`association.py`'s `size_check_fails` and `pasa_cost_components` both follow
this convention (`size_est.depth_quality >= size_confidence_floor` /
`< size_confidence_floor`), never `size_est is None`.

## Observations

- **`depth_quality` is currently binary** (`estimate_size_m` never produces
  anything between 0 and 1) even though the field is typed as continuous —
  worth remembering when reading `association.py`'s
  `size_confidence_floor` comparisons: today they're effectively "was there
  *any* depth reading," not "how good was it."
- **No caller in `dome_semantic` currently invokes `estimate_size_m`.**
  `SemanticMapNode` (see `13-semantic_map_node.md`) only receives
  already-3D `Detection3DArray` centroids — no pixel bounding box, no raw
  depth — so this function's real call site (2D detection + depth →
  `WorldTracker` observation) hasn't been wired into the ROS layer yet. The
  pure logic and its association-side consumers (`assoc_cost_size_weight`,
  `welford_update_size`) are tested and ready for when it is.
