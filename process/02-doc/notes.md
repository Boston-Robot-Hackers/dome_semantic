# Notes

Semi-permanent project notes — durable architecture decisions that don't
belong in a feature/task file and would get lost in `current.md`'s churn.

## Dependency discipline

`WorldTracker`'s pure closure needs `pydantic`, `pyyaml`, `numpy` — all
already present in the workspace Python environment, no new system deps.
It deliberately does **not** need `torch`/`torchvision`/`cv2`: those belong to
`dome_vision`'s `EmbeddingExtractor` (image embedding inference), which never
moved here. This package only ever *compares* embedding vectors
(`embedding_similarity.cosine_sim`), never *extracts* them.

## Watch list: dome_vision features targeting the ported code

`dome_vision_ros/semantic_map_node.py` **still imports and runs**
`dome_vision.world_tracker.WorldTracker` directly today — `dome_vision`'s
copy is still in that repo, though the robot now runs this package's node.
Four `dome_vision` features, all now **deferred**, describe planned changes to
exactly the modules ported here (`world_tracker.py`, `targets.py`,
`association.py`, `config.py`):

- **F39** — duplicate confirmed-target collapse (post-confirmation merge pass)
- **F40** — `/odom_raw`-based stopped detection for a tighter association radius
- **F56** — split `WorldTracker` into `target_store.py`/`target_stats.py`/`target_serializer.py`
- **F57** — consolidate the `PotentialTarget`/`ConfirmedTarget` data model

**Why this matters here**: F33's stated intent is a one-way migration —
*"dome_vision keeps OAK/depth/detection publishing; the map/tracker moves"*
(TF33.2). Once this package's own ROS node (TF33.3/TF33.4) is built and
proven,
`dome_vision`'s `semantic_map_node.py` gets retired and its
`world_tracker.py`/`association.py`/etc. get deleted. At that point these
four features become moot *in dome_vision* (their target file will be gone).
If the underlying improvements are still wanted, they'd need to be
re-authored against `dome_semantic`'s own structure — not silently assumed
to carry over, since by then this package's modules may already differ
(TF33.3's map-frame re-basing, TF33.4's typed publishing).

**How to apply**: `dome_vision` F71 (retire the semantic layer) does the
deletion; its TF71.0 checks whether F39/F40/F56/F57 landed there in the
meantime. If any did, decide then whether the same improvement is still
wanted here.

## Bag replay of a drive (TF36)

Used to compare tracker changes on identical TF and detections, so SLAM's
run-to-run variance drops out.

**Record** on the robot, with drivers, OAK-D detection only and real SLAM
running (the recorder subscribes to `/oak/detections_3d`, so the vision node
runs inference even without the semantic node):

```
ros2 bag record -o ~/bags/<name> /tf /tf_static /oak/detections_3d /odom /scan
```

**Replay** with the live stack stopped (no drivers, SLAM or vision — the bag
supplies their TF). Use a fresh `map_name` each time, so nothing is restored
from an earlier save. Three terminals, from `~/ros2_ws`:

```
ros2 run dome_semantic semantic_map_node --ros-args -r __node:=semantic_map \
  -p use_sim_time:=true -p map_name:=<replay_name> \
  -p class_profile_path:=$(ros2 pkg prefix dome_semantic)/share/dome_semantic/config/class_profiles.yaml \
  --params-file $(ros2 pkg prefix dome_semantic)/share/dome_semantic/config/semantic_map.yaml
ros2 bag record -o ~/bags/<replay_name> /semantic/targets
ros2 bag play ~/bags/<name> --clock
```

Stop the recorder and the node once play ends.
