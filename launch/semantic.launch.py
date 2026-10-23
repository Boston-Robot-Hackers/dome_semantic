#!/usr/bin/env python3
# semantic.launch.py — launch the dome_semantic semantic_map_node
# Author: Pito Salas and Claude Code
# Open Source Under MIT license

"""Node-only launch for the semantic map (TF33.8 Part A).

Starts `semantic_map_node` — no OAK-D, SLAM, or Nav2. `map_name` is required
because it keys persistence (`~/.dome/semantic_maps/<map_name>.json`); the
node's own "unknown" default would silently share one file across maps.

`static_map_odom` also starts an identity `map→odom` static transform, the
no-SLAM setup for bench checks. Never combine it with SLAM: both would
publish `map→odom`.
"""

from better_launch import BetterLaunch, launch_this


@launch_this(ui=True)
def semantic_launch(
    map_name: str = "",
    publish_every_n: int = 5,
    static_map_odom: bool = False,
):
    if not map_name:
        raise ValueError(
            "map_name is required: "
            "bl dome_semantic semantic.launch.py --map_name <name>"
        )

    bl = BetterLaunch()

    if static_map_odom:
        bl.node(
            "tf2_ros",
            "static_transform_publisher",
            name="map_odom_identity",
            cmd_args=["--frame-id", "map", "--child-frame-id", "odom"],
        )

    bl.node(
        "dome_semantic",
        "semantic_map_node",
        name="semantic_map",
        params={"map_name": map_name, "publish_every_n": publish_every_n},
        ros_waittime=30.0,
    )
