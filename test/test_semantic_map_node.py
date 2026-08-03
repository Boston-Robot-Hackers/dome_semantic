#!/usr/bin/env python3
# test_semantic_map_node — F33 T03: TF integration + re-basing wiring
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import math
from unittest.mock import MagicMock, patch

import pytest
import rclpy
from builtin_interfaces.msg import Time as RosTime
from geometry_msgs.msg import Point, TransformStamped
from std_msgs.msg import Header
from vision_msgs.msg import BoundingBox3D, Detection3D, Detection3DArray, ObjectHypothesisWithPose

from dome_semantic.map_rebasing import PlanarTransform
from dome_semantic.targets import ConfirmedTarget


@pytest.fixture(scope="module", autouse=True)
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    from dome_semantic.semantic_map_node import SemanticMapNode
    with patch("tf2_ros.TransformListener"):
        n = SemanticMapNode()
    n.tf_buffer = MagicMock()
    n.adapter.tf_buffer = n.tf_buffer
    yield n
    n.destroy_node()


def make_detections(entries: list, sec: int = 1, nanosec: int = 0) -> Detection3DArray:
    """entries: list of (x, y, z, label, track_id)."""
    msg = Detection3DArray()
    msg.header = Header()
    msg.header.stamp = RosTime(sec=sec, nanosec=nanosec)
    for x, y, z, label, track_id in entries:
        det = Detection3D()
        det.bbox = BoundingBox3D()
        det.bbox.center.position = Point(x=x, y=y, z=z)
        hyp = ObjectHypothesisWithPose()
        hyp.hypothesis.class_id = label
        det.results = [hyp]
        det.id = str(track_id) if track_id is not None else ""
        msg.detections.append(det)
    return msg


def make_transform_stamped(x=0.0, y=0.0, yaw=0.0) -> TransformStamped:
    tf = TransformStamped()
    tf.transform.translation.x = x
    tf.transform.translation.y = y
    tf.transform.rotation.z = math.sin(yaw / 2)
    tf.transform.rotation.w = math.cos(yaw / 2)
    return tf


def make_point_result(x, y, z):
    from geometry_msgs.msg import PointStamped
    p = PointStamped()
    p.point.x, p.point.y, p.point.z = x, y, z
    return p


def test_on_detections_confirms_after_enough_frames(node):
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped()
    node.tf_buffer.transform.return_value = make_point_result(1.0, 2.0, 0.0)

    for i in range(6):
        msg = make_detections([(0.1, 0.1, 1.0, "can", 7)], sec=1 + i)
        node.on_detections(msg)

    confirmed = node.tracker.confirmed_targets
    assert len(confirmed) == 1
    assert confirmed[0].label == "can"
    assert confirmed[0].xyz_world == pytest.approx((1.0, 2.0, 0.0))


def test_on_detections_drops_when_tf_unavailable(node):
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped()
    node.tf_buffer.transform.side_effect = Exception("no transform")

    msg = make_detections([(0.1, 0.1, 1.0, "can", 7)])
    node.on_detections(msg)  # must not raise

    assert node.tracker.confirmed_targets == []
    assert node.tracker.potential_targets == []


def test_lookup_map_to_odom_returns_none_on_lookup_exception():
    import tf2_ros
    from dome_semantic.semantic_map_node import SemanticMapNode
    with patch("tf2_ros.TransformListener"):
        node = SemanticMapNode()
    node.tf_buffer = MagicMock()
    node.tf_buffer.lookup_transform.side_effect = tf2_ros.LookupException("no tf")

    assert node.lookup_map_to_odom(RosTime(sec=1, nanosec=0)) is None
    node.destroy_node()


def test_lookup_map_to_odom_converts_transform():
    from dome_semantic.semantic_map_node import SemanticMapNode
    with patch("tf2_ros.TransformListener"):
        node = SemanticMapNode()
    node.tf_buffer = MagicMock()
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(1.0, 2.0, math.pi / 2)

    result = node.lookup_map_to_odom(RosTime(sec=1, nanosec=0))

    assert result == PlanarTransform(1.0, 2.0, pytest.approx(math.pi / 2))
    node.destroy_node()


def test_maybe_rebase_applies_delta_on_jump(node):
    target = ConfirmedTarget(
        target_id=1, label="can", canonical_class="can", xyz_world=(0.0, 0.0, 1.0),
        observation_count=5, confirmed_at_s=1.0, last_seen_s=1.0,
    )
    node.tracker.confirmed.append(target)
    node.last_map_t_odom = PlanarTransform(0.0, 0.0, 0.0)
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(3.0, 0.0, 0.0)

    node.maybe_rebase(RosTime(sec=2, nanosec=0))

    assert target.xyz_world == pytest.approx((3.0, 0.0, 1.0))
    assert node.last_map_t_odom == PlanarTransform(3.0, 0.0, pytest.approx(0.0))


def test_maybe_rebase_noop_within_epsilon(node):
    target = ConfirmedTarget(
        target_id=1, label="can", canonical_class="can", xyz_world=(0.0, 0.0, 1.0),
        observation_count=5, confirmed_at_s=1.0, last_seen_s=1.0,
    )
    node.tracker.confirmed.append(target)
    node.last_map_t_odom = PlanarTransform(0.0, 0.0, 0.0)
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(0.001, 0.0, 0.0)

    node.maybe_rebase(RosTime(sec=2, nanosec=0))

    assert target.xyz_world == pytest.approx((0.0, 0.0, 1.0))


def test_maybe_rebase_seeds_baseline_without_rebasing_on_first_call(node):
    target = ConfirmedTarget(
        target_id=1, label="can", canonical_class="can", xyz_world=(5.0, 5.0, 1.0),
        observation_count=5, confirmed_at_s=1.0, last_seen_s=1.0,
    )
    node.tracker.confirmed.append(target)
    assert node.last_map_t_odom is None
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(9.0, 9.0, 1.0)

    node.maybe_rebase(RosTime(sec=2, nanosec=0))

    assert target.xyz_world == pytest.approx((5.0, 5.0, 1.0))
    assert node.last_map_t_odom == PlanarTransform(9.0, 9.0, pytest.approx(1.0))
