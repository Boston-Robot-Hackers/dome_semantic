---
version: "1.0"
generated: "2026-08-03"
---

# `geometry.py` — From Pixels to Metres

## Why this module exists

Everything downstream of a camera detection — association, size estimation,
confirmation — works in *metres, in some 3D frame*. But a neural detector's
raw output is a bounding box in *pixels, on a 2D image*. `geometry.py` is the
one place that boundary gets crossed: it holds the camera model
(`Intrinsics`), a small value type for a pixel-space box (`PixelBox`), and
the projection math connecting the two (`pixel_to_xyz`, `box_to_xyz`).

Nothing in this module imports ROS, numpy, or anything from elsewhere in
`dome_semantic` — it's the lowest layer in the package's dependency graph,
which is why it's numbered first.

## The pinhole camera model, in four numbers

`Intrinsics` holds `fx`, `fy` (focal length, in pixels, along each axis) and
`cx`, `cy` (the pixel coordinates of the optical center — usually close to
the image center, but not assumed to be exactly centered). This is the
[pinhole camera model](https://en.wikipedia.org/wiki/Pinhole_camera_model)
reduced to the four numbers this codebase actually needs: given a pixel and
a depth reading (from the OAK-D's stereo depth), those four numbers are
enough to recover the point's real-world X and Y.

```python
def pixel_to_xyz(pixel_x, pixel_y, depth_m, intrinsics) -> tuple | None:
    if intrinsics is None or depth_m is None or depth_m <= 0:
        return None
    intr = (
        intrinsics
        if isinstance(intrinsics, Intrinsics)
        else Intrinsics.from_tuple(intrinsics)
    )
    return (
        (pixel_x - intr.cx) * depth_m / intr.fx,
        (pixel_y - intr.cy) * depth_m / intr.fy,
        depth_m,
    )
```

The derivation is the standard inverse pinhole projection: a pixel offset
from the optical center, `(pixel_x - cx)`, scales linearly with depth — twice
as far away, twice as much real-world distance per pixel. Dividing that
scaled offset by the focal length converts pixels to metres. `depth_m`
becomes the Z coordinate directly, since depth *is* the camera-frame Z by
definition for a forward-facing camera.

The `None`-on-invalid-input behavior (`intrinsics is None or depth_m is None
or depth_m <= 0`) is deliberate: a stereo depth reading can legitimately fail
(no texture to match, object too close/far, occlusion), and zero or negative
depth has no physical meaning to project. Every caller in this codebase
receives that `None` and treats it as "no size estimate this frame," not as
an error.

## Two entry points, one underlying formula

`pixel_to_xyz` takes a raw pixel coordinate. `box_to_xyz` takes a `PixelBox`
and projects its *center*:

```python
def box_to_xyz(box: PixelBox, depth_m, intrinsics):
    return pixel_to_xyz(box.cx, box.cy, depth_m, intrinsics)
```

`PixelBox` itself is a small immutable value type (`x1, y1, x2, y2` — corner
form) with derived `cx`/`cy`/`width`/`height` properties and a `clamp()` that
constrains a box to an image's bounds. `from_center()` is the inverse
constructor: given a detector's typical center+size output, build the
corner-form box. Neither `PixelBox` nor `Intrinsics` does anything beyond
hold values and offer the couple of derived properties/constructors that
callers need — there's no behavior here that isn't a direct consequence of
the pinhole model.

## Observations

- **`Intrinsics.from_tuple` accepts a bare 4-tuple as well as an `Intrinsics`
  instance** (`pixel_to_xyz`'s `intrinsics` parameter takes either) — a small
  ergonomic concession so callers with intrinsics loaded from a plain
  4-number config don't need to construct a dataclass first.
- **Neither dataclass validates its inputs** (e.g. `fx == 0` would divide by
  zero in `pixel_to_xyz`). That's consistent with this module's role as pure
  math over already-validated camera calibration data — the calibration
  values come from a one-time setup step, not untrusted runtime input.
- **This module currently has one live caller in the package**:
  `size_estimate.estimate_size_m` uses `Intrinsics` directly (see that file's
  literate doc). `pixel_to_xyz`/`box_to_xyz`/`PixelBox` are the general
  projection API a full 2D-detection pipeline would use; the current
  `SemanticMapNode` only receives already-3D detections
  (`Detection3DArray`), so those two functions aren't on this package's live
  call path yet.
