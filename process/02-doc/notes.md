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

## Watch list: dome_vision features targeting the ported code (resolved)

**Resolved 2026-11-13 by `dome_vision` F71**, which deleted that repo's copy of
the tracker (`world_tracker.py`, `semantic_map_node.py`, `tf_adapter`, class
profiles). **This package is now the only semantic map.**

- `dome_vision` F39, F40, F56 and F57 (merge pass, `/odom_raw` stopped
  detection, `WorldTracker` split, target data model) never landed there and
  are moot. Re-author them here if still wanted; **F39's merge idea is
  already done** by F36's `target_merge.py`.
- `dome_control`'s `behavior_manager` and `dome_vision`'s image node now read
  this package's `config/class_profiles.yaml` and `/semantic/targets`, so
  changes to either reach them.

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
