#!/usr/bin/env python3
# size_estimate — SizeEstimate dataclass and pinhole-projection helper
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from dataclasses import dataclass

from dome_semantic.geometry import Intrinsics


@dataclass
class SizeEstimate:
    width_m: float
    height_m: float
    aspect_ratio: float
    depth_quality: float  # 0.0–1.0; 0 means no usable depth


def estimate_size_m(bbox_pixels: tuple, depth_m: float, fx: float, fy: float) -> SizeEstimate:
    bw, bh = bbox_pixels
    intr = Intrinsics(fx=fx, fy=fy, cx=0.0, cy=0.0)
    depth_quality = 1.0 if depth_m > 0 else 0.0
    if depth_quality == 0:
        return SizeEstimate(width_m=0.0, height_m=0.0, aspect_ratio=0.0, depth_quality=0.0)
    width_m = bw * depth_m / intr.fx
    height_m = bh * depth_m / intr.fy
    aspect_ratio = height_m / width_m if width_m > 0 else 0.0
    return SizeEstimate(width_m=width_m, height_m=height_m, aspect_ratio=aspect_ratio, depth_quality=depth_quality)
