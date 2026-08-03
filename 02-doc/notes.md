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
copy is the live, currently-deployed tracker, not a stale fork. Four
`dome_vision` features are **not done** and describe planned changes to
exactly the modules ported here (`world_tracker.py`, `targets.py`,
`association.py`, `config.py`):

- **F39** — duplicate confirmed-target collapse (post-confirmation merge pass)
- **F40** — `/odom_raw`-based stopped detection for a tighter association radius
- **F56** — split `WorldTracker` into `target_store.py`/`target_stats.py`/`target_serializer.py`
- **F57** — consolidate the `PotentialTarget`/`ConfirmedTarget` data model

**Why this matters here**: F33's stated intent is a one-way migration —
*"dome_vision keeps OAK/depth/detection publishing; the map/tracker moves"*
(TF33 T02). Once this package's own ROS node (T03/T04) is built and proven,
`dome_vision`'s `semantic_map_node.py` gets retired and its
`world_tracker.py`/`association.py`/etc. get deleted. At that point these
four features become moot *in dome_vision* (their target file will be gone).
If the underlying improvements are still wanted, they'd need to be
re-authored against `dome_semantic`'s own structure — not silently assumed
to carry over, since by then this package's modules may already differ
(T03's map-frame re-basing, T04's typed publishing).

**How to apply**: before deleting `dome_vision`'s originals, check whether
F39/F40/F56/F57 landed there in the meantime — if any did, decide then
whether the same improvement is still wanted here.
