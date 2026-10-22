#!/usr/bin/env python3
# semantic_map_node — F33 T04/T06: typed publishing, node wiring, persistence
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Subscribes /oak/detections_3d, transforms each detection camera_link -> map
at observation time (F33 G1), and re-bases every stored WorldTracker target
whenever the map->odom transform jumps beyond a small epsilon (a SLAM
correction). Publishes the confirmed map as a typed `SemanticTargetArray`
(F33 G2) plus RViz markers, an association-diagnostics feed, and a
`/describe_scene` service. Confirmation-threshold tuning is ROS-declared via
`declare_tracker_config` (WorldTrackerConfig stays the single source of
truth, F34 precedent) so it is launch-overridable without a hand-duplicated
param list.

Target orientation is always published identity: WorldTracker has no object-
facing estimate (only position), so there is nothing non-arbitrary to put in
`pose.orientation` yet — the mission-layer consumer uses yaw for the robot's
own arrival heading, not a claim about the object.

The `map_name` ROS param (F33 T06, G8) keys persistence to the currently
loaded SLAM map, mirroring `explorer_manager_node`'s own `map_name` param and
`slam_manager`'s `--map_name` CLI convention: the semantic map for a given
SLAM map is restored on startup (`semantic_persistence.load_semantic_map`)
and saved on shutdown (`save`, called from `main`'s `finally`).
"""

import json

import rclpy
import tf2_ros
from builtin_interfaces.msg import Duration, Time
from dome_semantic_msgs.msg import SemanticTarget, SemanticTargetArray
from geometry_msgs.msg import Point, Vector3
from rclpy.node import Node
from std_msgs.msg import ColorRGBA, String
from std_srvs.srv import Trigger
from vision_msgs.msg import Detection3DArray
from visualization_msgs.msg import Marker, MarkerArray

from dome_semantic.map_rebasing import (
    PlanarTransform,
    has_jumped,
    rebase_delta,
    rebase_tracker,
    yaw_from_quaternion,
)
from dome_semantic.semantic_persistence import load_semantic_map, save_semantic_map
from dome_semantic.tf_adapter import TFAdapter
from dome_semantic.tracker_params import declare_tracker_config

CAMERA_FRAME = "camera_link"
MAP_FRAME = "map"
ODOM_FRAME = "odom"
SCHEMA_VERSION = 1
MARKER_LIFETIME = Duration(sec=2, nanosec=0)


def make_marker(
    stamp, frame_id: str, ns: str, marker_id: int, marker_type: int
) -> Marker:
    m = Marker()
    m.header.stamp = stamp
    m.header.frame_id = frame_id
    m.ns = ns
    m.id = marker_id
    m.type = marker_type
    m.action = Marker.ADD
    m.pose.orientation.w = 1.0
    m.lifetime = MARKER_LIFETIME
    return m


def seconds_to_ros_time(seconds: float) -> Time:
    sec = int(seconds)
    return Time(sec=sec, nanosec=round((seconds - sec) * 1e9))


class SemanticMapNode(Node):
    def __init__(self):
        super().__init__("semantic_map")
        self.declare_parameter("publish_every_n", 5)
        self.publish_every_n = self.get_parameter("publish_every_n").value
        self.declare_parameter("map_name", "unknown")
        self.map_name: str = self.get_parameter("map_name").value
        self.tracker = load_semantic_map(
            self.map_name, declare_tracker_config(self), self.get_logger().warning
        )
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.adapter = TFAdapter(self.tf_buffer, CAMERA_FRAME, MAP_FRAME)
        self.last_map_t_odom: PlanarTransform | None = None
        self.frame_num = 0
        self.sub = self.create_subscription(
            Detection3DArray, "/oak/detections_3d", self.on_detections, 10
        )
        self.pub_targets = self.create_publisher(
            SemanticTargetArray, "/semantic/targets", 10
        )
        self.pub_markers = self.create_publisher(MarkerArray, "/targets/markers", 10)
        self.pub_assoc_diag = self.create_publisher(String, "/targets/assoc_diag", 10)
        self.srv_describe_scene = self.create_service(
            Trigger, "/describe_scene", self.on_describe_scene
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
        if self.last_map_t_odom is not None and has_jumped(
            self.last_map_t_odom, current
        ):
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

        if self.tracker.config.use_class_profiles and self.tracker.assoc_log:
            self.publish_assoc_diag()
        if self.frame_num % self.publish_every_n == 0:
            self.publish_targets()
            self.publish_markers()

    def publish_targets(self) -> None:
        msg = SemanticTargetArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = MAP_FRAME
        for t in self.tracker.confirmed:
            if t.is_lost:
                continue
            target = SemanticTarget()
            target.schema_version = SCHEMA_VERSION
            target.target_id = str(t.target_id)
            target.label = t.label
            target.pose.position.x, target.pose.position.y, target.pose.position.z = (
                t.xyz_world
            )
            target.pose.orientation.w = 1.0
            target.observation_count = t.observation_count
            target.last_seen = seconds_to_ros_time(t.last_seen_s)
            target.track_ids = [str(tid) for tid in sorted(t.track_ids)]
            msg.targets.append(target)
        self.pub_targets.publish(msg)

    def publish_markers(self) -> None:
        stamp = self.get_clock().now().to_msg()
        array = MarkerArray()
        label_z_offset = 0.08

        for t in self.tracker.confirmed:
            if t.is_lost:
                continue
            x, y, z = t.xyz_world
            base_id = t.target_id * 3

            sphere = make_marker(
                stamp, MAP_FRAME, "semantic_map", base_id, Marker.SPHERE
            )
            sphere.pose.position.x = x
            sphere.pose.position.y = y
            sphere.pose.position.z = z
            sphere.scale = Vector3(x=0.03, y=0.03, z=0.03)
            sphere.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.8)
            array.markers.append(sphere)

            text = make_marker(
                stamp, MAP_FRAME, "semantic_map", base_id + 1, Marker.TEXT_VIEW_FACING
            )
            text.pose.position.x = x
            text.pose.position.y = y
            text.pose.position.z = z + label_z_offset
            text.scale.z = 0.12
            text.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)
            text.text = f"T{t.target_id} {t.canonical_class}/{t.observation_count}"
            array.markers.append(text)

            line = make_marker(
                stamp, MAP_FRAME, "semantic_map", base_id + 2, Marker.LINE_STRIP
            )
            line.scale.x = 0.005
            line.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.5)
            line.points = [Point(x=x, y=y, z=z), Point(x=x, y=y, z=z + label_z_offset)]
            array.markers.append(line)

        for pt in self.tracker.potential_targets:
            x, y, z = pt.xyz_world
            dot = make_marker(
                stamp, MAP_FRAME, "semantic_map_potential", pt.target_id, Marker.SPHERE
            )
            dot.pose.position.x = x
            dot.pose.position.y = y
            dot.pose.position.z = z
            dot.scale = Vector3(x=0.02, y=0.02, z=0.02)
            dot.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=0.5)
            array.markers.append(dot)

        self.pub_markers.publish(array)

    def publish_assoc_diag(self) -> None:
        msg = String()
        msg.data = json.dumps(self.tracker.assoc_log)
        self.pub_assoc_diag.publish(msg)

    def on_describe_scene(self, request, response):
        visible = [t for t in self.tracker.confirmed if not t.is_lost]
        if not visible:
            response.success = True
            response.message = "I don't see any objects right now."
            return response
        counts: dict[str, int] = {}
        for t in visible:
            counts[t.label] = counts.get(t.label, 0) + 1
        profiles = self.tracker.profiles
        parts = [
            f"{n} {profiles[label].display_name or label if label in profiles else label}"
            for label, n in counts.items()
        ]
        desc = (
            parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        )
        response.success = True
        response.message = "I see " + desc + "."
        return response

    def save(self) -> None:
        path = save_semantic_map(self.tracker, self.map_name)
        self.get_logger().info(f"Semantic map saved to {path}")


def main() -> None:
    rclpy.init()
    node = SemanticMapNode()
    try:
        # Multi-threaded so TF keeps arriving while on_detections waits for it.
        rclpy.spin(node, executor=rclpy.executors.MultiThreadedExecutor())
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.save()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
