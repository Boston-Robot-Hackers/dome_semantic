#!/usr/bin/env python3
# tf_adapter — transforms 3D points between TF frames using an injected tf2 Buffer
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
#
# Ported from dome_vision_ros (F33 T03), targeting `map` instead of `odom`
# (F33 G1: map is the frame of record). One behavior change from the
# original: the transform lookup now uses the observation's own stamp
# instead of time-zero/"latest available" - F33 G1 calls for transforming
# "at observation time", and using the real stamp is what that means.

from geometry_msgs.msg import PointStamped


class TFAdapter:
    """Transforms a 3D point from source_frame to target_frame via tf2.

    Accepts a tf2_ros.Buffer at construction so the buffer can be mocked in
    tests without a running ROS2 daemon. Returns None on any transform failure
    so callers can decide whether to drop or fallback the observation.
    """

    def __init__(self, tf_buffer, source_frame: str, target_frame: str):
        self.tf_buffer = tf_buffer
        self.source_frame = source_frame
        self.target_frame = target_frame

    def transform(self, xyz: tuple, stamp) -> "tuple[float, float, float] | None":
        """Return xyz transformed to target_frame at `stamp`, or None if unavailable."""
        point = PointStamped()
        point.header.frame_id = self.source_frame
        point.header.stamp = stamp
        point.point.x = float(xyz[0])
        point.point.y = float(xyz[1])
        point.point.z = float(xyz[2])
        try:
            result = self.tf_buffer.transform(point, self.target_frame)
            return (result.point.x, result.point.y, result.point.z)
        except Exception:
            return None
