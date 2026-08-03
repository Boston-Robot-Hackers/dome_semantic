#!/usr/bin/env python3
# geometry — camera intrinsics, pixel boxes, and projection helpers
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from dataclasses import dataclass


@dataclass(frozen=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float

    @classmethod
    def from_tuple(cls, values: tuple) -> "Intrinsics":
        return cls(
            fx=float(values[0]),
            fy=float(values[1]),
            cx=float(values[2]),
            cy=float(values[3]),
        )


@dataclass(frozen=True)
class PixelBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def from_center(cls, x: float, y: float, width: float, height: float) -> "PixelBox":
        half_w = width / 2.0
        half_h = height / 2.0
        return cls(x - half_w, y - half_h, x + half_w, y + half_h)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def clamp(self, width_px: int, height_px: int) -> "PixelBox":
        return PixelBox(
            x1=max(0.0, min(float(width_px), self.x1)),
            y1=max(0.0, min(float(height_px), self.y1)),
            x2=max(0.0, min(float(width_px), self.x2)),
            y2=max(0.0, min(float(height_px), self.y2)),
        )


def pixel_to_xyz(
    pixel_x: float,
    pixel_y: float,
    depth_m: float | None,
    intrinsics: Intrinsics | tuple | None,
) -> tuple[float, float, float] | None:
    if intrinsics is None or depth_m is None or depth_m <= 0:
        return None
    intr = intrinsics if isinstance(intrinsics, Intrinsics) else Intrinsics.from_tuple(intrinsics)
    return (
        (pixel_x - intr.cx) * depth_m / intr.fx,
        (pixel_y - intr.cy) * depth_m / intr.fy,
        depth_m,
    )


def box_to_xyz(
    box: PixelBox,
    depth_m: float | None,
    intrinsics: Intrinsics | tuple | None,
) -> tuple[float, float, float] | None:
    return pixel_to_xyz(box.cx, box.cy, depth_m, intrinsics)
