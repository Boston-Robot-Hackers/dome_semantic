#!/usr/bin/env python3
# test_semantic_map_node — F33 T03: TF integration + re-basing wiring
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

import json
import math
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import rclpy
import tf2_ros
from builtin_interfaces.msg import Time as RosTime
from geometry_msgs.msg import Point, TransformStamped
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import Header
from std_srvs.srv import Trigger
from tf2_msgs.msg import TFMessage
from vision_msgs.msg import (
    BoundingBox3D,
    Detection3D,
    Detection3DArray,
    ObjectHypothesisWithPose,
)

from dome_semantic.map_rebasing import PlanarTransform
from dome_semantic.targets import ConfirmedTarget

TEST_DOMAIN_ID = 87  # keeps test traffic off a live robot's graph


@pytest.fixture(scope="module", autouse=True)
def ros():
    rclpy.init(domain_id=TEST_DOMAIN_ID)
    yield
    rclpy.shutdown()


@pytest.fixture(autouse=True)
def isolate_semantic_map_dir(tmp_path):
    """Every test in this file constructs a SemanticMapNode, which now loads a
    persisted map on startup (F33 T06) — redirect that off the real ~/.dome so
    tests never depend on, or pollute, the developer's actual home directory.
    """
    with patch(
        "dome_semantic.semantic_persistence.semantic_map_dir",
        return_value=str(tmp_path),
    ):
        yield


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
    node.tf_buffer.transform.side_effect = tf2_ros.LookupException("no transform")

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
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(
        1.0, 2.0, math.pi / 2
    )

    result = node.lookup_map_to_odom(RosTime(sec=1, nanosec=0))

    assert result == PlanarTransform(1.0, 2.0, pytest.approx(math.pi / 2))
    node.destroy_node()


def test_maybe_rebase_applies_delta_on_jump(node):
    target = ConfirmedTarget(
        target_id=1,
        label="can",
        canonical_class="can",
        xyz_world=(0.0, 0.0, 1.0),
        observation_count=5,
        confirmed_at_s=1.0,
        last_seen_s=1.0,
    )
    node.tracker.confirmed.append(target)
    node.last_map_t_odom = PlanarTransform(0.0, 0.0, 0.0)
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(3.0, 0.0, 0.0)

    node.maybe_rebase(RosTime(sec=2, nanosec=0))

    assert target.xyz_world == pytest.approx((3.0, 0.0, 1.0))
    assert node.last_map_t_odom == PlanarTransform(3.0, 0.0, pytest.approx(0.0))


def test_maybe_rebase_noop_within_epsilon(node):
    target = ConfirmedTarget(
        target_id=1,
        label="can",
        canonical_class="can",
        xyz_world=(0.0, 0.0, 1.0),
        observation_count=5,
        confirmed_at_s=1.0,
        last_seen_s=1.0,
    )
    node.tracker.confirmed.append(target)
    node.last_map_t_odom = PlanarTransform(0.0, 0.0, 0.0)
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(
        0.001, 0.0, 0.0
    )

    node.maybe_rebase(RosTime(sec=2, nanosec=0))

    assert target.xyz_world == pytest.approx((0.0, 0.0, 1.0))


def test_publish_targets_after_confirmation(node):
    node.publish_every_n = 1  # publish every tick so the final call reflects the target
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped()
    node.tf_buffer.transform.return_value = make_point_result(1.0, 2.0, 0.0)
    node.pub_targets = MagicMock()

    for i in range(6):
        msg = make_detections([(0.1, 0.1, 1.0, "can", 7)], sec=1 + i)
        node.on_detections(msg)

    published = node.pub_targets.publish.call_args.args[0]
    assert published.header.frame_id == "map"
    assert len(published.targets) == 1
    target = published.targets[0]
    assert target.schema_version == 1
    assert target.target_id == "1"
    assert target.label == "can"
    assert target.observation_count == 6
    assert target.pose.position.x == pytest.approx(1.0)
    assert target.pose.position.y == pytest.approx(2.0)
    assert target.pose.orientation.w == pytest.approx(1.0)
    assert target.track_ids == ["7"]


def test_publish_targets_skips_still_potential_and_lost(node):
    node.publish_every_n = 1
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped()
    node.tf_buffer.transform.return_value = make_point_result(1.0, 2.0, 0.0)
    node.pub_targets = MagicMock()

    msg = make_detections([(0.1, 0.1, 1.0, "can", 7)], sec=1)
    node.on_detections(msg)  # one observation: still a potential, not confirmed

    published = node.pub_targets.publish.call_args.args[0]
    assert published.targets == []


def test_publish_throttled_by_publish_every_n(node):
    node.publish_every_n = 3
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped()
    node.tf_buffer.transform.return_value = make_point_result(1.0, 2.0, 0.0)
    node.pub_targets = MagicMock()

    for i in range(6):
        msg = make_detections([(0.1, 0.1, 1.0, "can", 7)], sec=1 + i)
        node.on_detections(msg)

    assert node.pub_targets.publish.call_count == 2  # frame_num 3 and 6


def test_describe_scene_no_targets(node):
    request = Trigger.Request()
    response = Trigger.Response()

    result = node.on_describe_scene(request, response)

    assert result.success is True
    assert result.message == "I don't see any objects right now."


def test_describe_scene_lists_confirmed_targets(node):
    node.tracker.confirmed.append(
        ConfirmedTarget(
            target_id=1,
            label="can",
            canonical_class="can",
            xyz_world=(1.0, 2.0, 0.0),
            observation_count=5,
            confirmed_at_s=1.0,
            last_seen_s=1.0,
        )
    )
    request = Trigger.Request()
    response = Trigger.Response()

    result = node.on_describe_scene(request, response)

    assert result.success is True
    assert result.message == "I see 1 can."


def test_node_loads_existing_semantic_map_on_construction(tmp_path):
    # tmp_path here is the same directory isolate_semantic_map_dir (autouse)
    # already pointed semantic_map_dir at for this test.
    envelope = {
        "map_name": "unknown",  # SemanticMapNode's default map_name param
        "targets": [
            {
                "target_id": 1,
                "label": "can",
                "xyz_world": [1.0, 2.0, 0.0],
                "observation_count": 5,
                "confirmed_at_s": 1.0,
                "last_seen_s": 1.0,
                "embedding": None,
            }
        ],
    }
    (tmp_path / "unknown.json").write_text(json.dumps(envelope))

    from dome_semantic.semantic_map_node import SemanticMapNode

    with patch("tf2_ros.TransformListener"):
        loaded_node = SemanticMapNode()
    try:
        assert len(loaded_node.tracker.confirmed) == 1
        assert loaded_node.tracker.confirmed[0].label == "can"
    finally:
        loaded_node.destroy_node()


def test_node_save_writes_current_tracker_state(node, tmp_path):
    node.tracker.confirmed.append(
        ConfirmedTarget(
            target_id=1,
            label="cup",
            canonical_class="cup",
            xyz_world=(3.0, 4.0, 0.0),
            observation_count=6,
            confirmed_at_s=1.0,
            last_seen_s=1.0,
        )
    )

    node.save()

    envelope = json.loads((tmp_path / "unknown.json").read_text())
    assert envelope["map_name"] == "unknown"
    assert envelope["targets"][0]["label"] == "cup"


def test_maybe_rebase_seeds_baseline_without_rebasing_on_first_call(node):
    target = ConfirmedTarget(
        target_id=1,
        label="can",
        canonical_class="can",
        xyz_world=(5.0, 5.0, 1.0),
        observation_count=5,
        confirmed_at_s=1.0,
        last_seen_s=1.0,
    )
    node.tracker.confirmed.append(target)
    assert node.last_map_t_odom is None
    node.tf_buffer.lookup_transform.return_value = make_transform_stamped(9.0, 9.0, 1.0)

    node.maybe_rebase(RosTime(sec=2, nanosec=0))

    assert target.xyz_world == pytest.approx((5.0, 5.0, 1.0))
    assert node.last_map_t_odom == PlanarTransform(9.0, 9.0, pytest.approx(1.0))


def wait_until(condition, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_detection_waits_for_tf_arriving_after_it():
    """Odometry TF lags detection stamps on the robot; on_detections must be
    able to wait for it, so TF callbacks have to run while it blocks.
    """
    from dome_semantic.semantic_map_node import SemanticMapNode

    node = SemanticMapNode()
    source = rclpy.create_node("tf_and_detection_source")
    tf_pub = source.create_publisher(TFMessage, "/tf", 10)
    det_pub = source.create_publisher(Detection3DArray, "/oak/detections_3d", 10)
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin)
    spinner.start()
    try:
        assert wait_until(
            lambda: (
                tf_pub.get_subscription_count() > 0
                and det_pub.get_subscription_count() > 0
            ),
            5.0,
        )
        det_pub.publish(make_detections([(0.0, 0.0, 1.0, "cup", None)], sec=100))
        time.sleep(0.05)
        camera_in_map = make_transform_stamped(x=1.0)
        camera_in_map.header.frame_id = "map"
        camera_in_map.header.stamp = RosTime(sec=100)
        camera_in_map.child_frame_id = "camera_link"
        tf_pub.publish(TFMessage(transforms=[camera_in_map]))
        assert wait_until(lambda: node.tracker.potentials, 2.0)
    finally:
        executor.shutdown()
        spinner.join()
        source.destroy_node()
        node.destroy_node()
