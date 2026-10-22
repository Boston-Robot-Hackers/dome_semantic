#!/usr/bin/env python3
# test_tf_adapter — unit tests for TFAdapter using a mock tf2 Buffer
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

from unittest.mock import MagicMock

import tf2_ros
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PointStamped, TransformStamped

from dome_semantic.tf_adapter import TFAdapter


def make_point_stamped(x, y, z):
    p = PointStamped()
    p.point.x = x
    p.point.y = y
    p.point.z = z
    return p


def make_adapter(tx=1.0, ty=2.0, tz=3.0):
    buf = MagicMock()
    buf.transform.return_value = make_point_stamped(tx, ty, tz)
    return TFAdapter(buf, "camera_link", "map"), buf


def test_transform_returns_correct_xyz():
    adapter, _ = make_adapter(1.5, 2.5, 0.1)
    result = adapter.transform((0.0, 0.0, 1.0), MagicMock())
    assert result == (1.5, 2.5, 0.1)


def test_transform_uses_correct_frames():
    adapter, buf = make_adapter()
    stamp = MagicMock()
    adapter.transform((0.1, 0.2, 0.3), stamp)
    call_args = buf.transform.call_args
    point_arg = call_args[0][0]
    target_arg = call_args[0][1]
    assert point_arg.header.frame_id == "camera_link"
    assert target_arg == "map"


def test_transform_passes_xyz_to_point():
    adapter, buf = make_adapter()
    adapter.transform((1.1, 2.2, 3.3), MagicMock())
    sent = buf.transform.call_args[0][0]
    assert abs(sent.point.x - 1.1) < 1e-6
    assert abs(sent.point.y - 2.2) < 1e-6
    assert abs(sent.point.z - 3.3) < 1e-6


def test_transform_uses_observation_stamp():
    """F33 G1: transform 'at observation time', not time-zero/latest-available."""
    adapter, buf = make_adapter()
    stamp = MagicMock()
    adapter.transform((0.0, 0.0, 0.0), stamp)
    sent = buf.transform.call_args[0][0]
    assert sent.header.stamp is stamp


def test_transform_returns_none_on_exception():
    buf = MagicMock()
    buf.transform.side_effect = tf2_ros.LookupException("TF not available")
    adapter = TFAdapter(buf, "camera_link", "map")
    assert adapter.transform((1.0, 0.0, 0.0), MagicMock()) is None


def test_custom_frames_respected():
    buf = MagicMock()
    buf.transform.return_value = make_point_stamped(0, 0, 0)
    adapter = TFAdapter(buf, "base_link", "map")
    adapter.transform((0.0, 0.0, 0.0), MagicMock())
    sent_point = buf.transform.call_args[0][0]
    target = buf.transform.call_args[0][1]
    assert sent_point.header.frame_id == "base_link"
    assert target == "map"


def test_transform_with_real_buffer():
    """A real Buffer needs tf2_geometry_msgs loaded to transform PointStamped."""
    buf = tf2_ros.Buffer()
    camera_in_map = TransformStamped()
    camera_in_map.header.frame_id = "map"
    camera_in_map.child_frame_id = "camera_link"
    camera_in_map.transform.translation.x = 1.0
    camera_in_map.transform.rotation.w = 1.0
    buf.set_transform_static(camera_in_map, "test")
    adapter = TFAdapter(buf, "camera_link", "map")
    assert adapter.transform((0.5, 0.0, 0.2), Time()) == (1.5, 0.0, 0.2)
