---
version: "1.0"
generated: "2026-08-03"
---

# `embedding_similarity.py` — The Smallest File With the Most History

## What it does

One function, `cosine_sim(a, b) -> float`, computing the
[cosine similarity](https://en.wikipedia.org/wiki/Cosine_similarity) between
two vectors: the cosine of the angle between them, `dot(a, b) / (|a| * |b|)`,
ranging from -1 (opposite direction) to 1 (identical direction), with 0
meaning orthogonal / unrelated. In this codebase, `a` and `b` are visual
embedding vectors — fixed-length numeric fingerprints of an object's
appearance, produced by a neural feature extractor upstream. Two embeddings
with a cosine similarity near 1 came from visually similar-looking objects.

```python
def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)
```

The zero-norm guard handles the degenerate case of an all-zero embedding
vector — dividing by zero would otherwise raise or produce `NaN`; returning
`0.0` (the "unrelated" score) is the sane fallback for a vector that carries
no directional information at all.

## Why this file exists at all

This function used to live inside `dome_vision`'s `embedding.py`, alongside
`EmbeddingExtractor` — the class that actually *runs* a MobileNetV3 model
(via `torch`/`torchvision`) over a cropped detection image to produce an
embedding in the first place. `WorldTracker.combined_sim()` (see
`08-world_tracker.md`) only ever *compares* embeddings someone else already
extracted — it never runs the model itself.

Porting `world_tracker.py` into this new, lightweight `dome_semantic`
package (F33 T02) meant a choice: copy `embedding.py` whole (and pull
`torch`/`torchvision`/`cv2` into a package that's supposed to be a
ROS/TF-only tracking core), or split the one function that's actually
needed. This 15-line file is the result of the second choice.
`EmbeddingExtractor` stayed behind in `dome_vision`, where the image
inference — and its heavy dependency stack — belongs.

## Observations

- **This module is a case study in dependency-boundary discipline**, not a
  novel piece of engineering: the interesting decision (numpy-only
  comparison vs. torch-carrying extraction) is documented in the module's
  own header comment, and the *code* itself is exactly what any cosine
  similarity implementation looks like.
- **No caller in `dome_semantic` currently supplies real embeddings.**
  `WorldTracker.update_embedding()` exists and is exercised by tests with
  synthetic vectors, but the ROS-facing `SemanticMapNode` doesn't yet
  subscribe to an embeddings topic the way the old `dome_vision_ros` node
  did (`/oak/embeddings`) — that wiring wasn't in scope for F33 T02–T04.
