#!/usr/bin/env python3
# embedding_similarity — cosine similarity between two embedding vectors
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
#
# Split out of dome_vision's embedding.py (F33 T02): that module also defines
# EmbeddingExtractor, which pulls in torch/torchvision/cv2 to run a MobileNetV3
# inference pass. WorldTracker only ever compares already-extracted embedding
# vectors — it never runs extraction itself — so this package only needs the
# numpy-only comparison, not the ML/CV stack. EmbeddingExtractor stays in
# dome_vision, which is where the image inference happens.

import numpy as np


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)
