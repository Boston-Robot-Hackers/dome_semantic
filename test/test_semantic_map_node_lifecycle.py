#!/usr/bin/env python3
# test_semantic_map_node_lifecycle — TF-listener node naming and shutdown
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Runs in its own file because each test needs a fresh rclpy context,
initialised with the launch file's global `__node` remap (which renames
every node in the process).
"""

from unittest.mock import patch

import pytest
import rclpy
from rclpy.executors import ExternalShutdownException

TEST_DOMAIN_ID = 88  # keeps test traffic off a live robot's graph


@pytest.fixture
def node(tmp_path):
    from dome_semantic.semantic_map_node import SemanticMapNode

    rclpy.init(
        args=["--ros-args", "-r", "__node:=semantic_map"], domain_id=TEST_DOMAIN_ID
    )
    with patch(
        "dome_semantic.semantic_persistence.semantic_map_dir",
        return_value=str(tmp_path),
    ):
        n = SemanticMapNode()
    yield n
    n.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


def test_tf_listener_node_not_renamed_by_launch_remap(node):
    assert node.get_name() == "semantic_map"
    assert node.tf_node.get_name() == "semantic_map_tf_listener"


def test_spin_tf_absorbs_external_shutdown(node):
    """On Ctrl-C, rcl's signal handler shuts the context down under the
    running TF executor, which raises ExternalShutdownException in its thread;
    spin_tf must end quietly instead of printing a traceback.
    """
    with patch.object(
        node.tf_executor, "spin", side_effect=ExternalShutdownException()
    ):
        node.spin_tf()


def test_destroy_node_stops_tf_thread(node):
    node.destroy_node()
    node.tf_thread.join(timeout=2.0)
    assert not node.tf_thread.is_alive()
