#!/usr/bin/env python3
# semantic_map_node — F33 T03: map-frame recording + re-basing on map->odom jumps
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
#
# Subscribes /oak/detections_3d, transforms each detection camera_link -> map
# at observation time (F33 G1), and re-bases every stored WorldTracker target
# whenever the map->odom transform jumps beyond a small epsilon (a SLAM
# correction). Typed SemanticTargetArray publishing and full param wiring is
# T04 - this node proves the TF integration only.

import rclpy
import tf2_ros
from rclpy.node import Node
from vision_msgs.msg import Detection3DArray

from dome_semantic.map_rebasing import (
    PlanarTransform,
    has_jumped,
    rebase_delta,
    rebase_tracker,
    yaw_from_quaternion,
)
from dome_semantic.tf_adapter import TFAdapter
from dome_semantic.world_tracker import WorldTracker, WorldTrackerConfig

CAMERA_FRAME = "camera_link"
MAP_FRAME = "map"
ODOM_FRAME = "odom"


class SemanticMapNode(Node):
    def __init__(self, config: WorldTrackerConfig | None = None):
        super().__init__("semantic_map")
        self.tracker = WorldTracker(config or WorldTrackerConfig())
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.adapter = TFAdapter(self.tf_buffer, CAMERA_FRAME, MAP_FRAME)
        self.last_map_t_odom: PlanarTransform | None = None
        self.frame_num = 0
        self.sub = self.create_subscription(
            Detection3DArray, "/oak/detections_3d", self.on_detections, 10
        )

    def lookup_map_to_odom(self, stamp) -> PlanarTransform | None:
        try:
            tf = self.tf_buffer.lookup_transform(MAP_FRAME, ODOM_FRAME, stamp)
        except (
            tf2_ros.LookupException,
            tf2_ros.ConnectivityException,
            tf2_ros.ExtrapolationException,
        ):
            return None
        t = tf.transform.translation
        q = tf.transform.rotation
        return PlanarTransform(t.x, t.y, yaw_from_quaternion(q.z, q.w))

    def maybe_rebase(self, stamp) -> None:
        current = self.lookup_map_to_odom(stamp)
        if current is None:
            return
        if self.last_map_t_odom is not None and has_jumped(self.last_map_t_odom, current):
            delta = rebase_delta(self.last_map_t_odom, current)
            rebase_tracker(self.tracker, delta)
            self.get_logger().info("map->odom jumped; re-based stored targets.")
        self.last_map_t_odom = current

    def on_detections(self, msg: Detection3DArray) -> None:
        stamp = msg.header.stamp
        timestamp_s = stamp.sec + stamp.nanosec * 1e-9
        self.maybe_rebase(stamp)

        observations = []
        tf_dropped = 0
        for det in msg.detections:
            pos = det.bbox.center.position
            xyz_cam = (pos.x, pos.y, pos.z)
            xyz_map = self.adapter.transform(xyz_cam, stamp)
            if xyz_map is None:
                tf_dropped += 1
                continue
            label = det.results[0].hypothesis.class_id if det.results else ""
            track_id = int(det.id) if det.id else None
            observations.append((xyz_map, label, self.frame_num, track_id))

        if tf_dropped and not observations:
            self.get_logger().warning(
                f"Dropped {tf_dropped} detection(s): no TF {CAMERA_FRAME} -> {MAP_FRAME}. "
                "No targets will be confirmed until the map->odom->base_link->camera_link "
                "chain is available (check SLAM/localization is running).",
                throttle_duration_sec=5.0,
            )

        self.frame_num += 1
        self.tracker.update(observations, timestamp_s)


def main() -> None:
    rclpy.init()
    node = SemanticMapNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
