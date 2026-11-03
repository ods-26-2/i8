"""Reference-normal distance, persisted with explicit compatibility metadata."""
from dataclasses import dataclass
import math
import numpy as np

from . import NormalModel

@dataclass(frozen=True)
class NormalDistance:
    score: float
    distance: float

def distance_to_normal(embedding, model: NormalModel) -> NormalDistance:
    value = np.asarray(embedding, dtype=np.float64)
    mean = np.asarray(model.mean, dtype=np.float64)
    std = np.asarray(model.std, dtype=np.float64)
    if value.shape != (model.embedding_dim,):
        raise ValueError("embedding possui dimensão incompatível com o modelo normal")
    if not np.isfinite(value).all():
        raise ValueError("embedding não finito")
    # Standardised Euclidean distance; score is a bounded monotonic evidence score.
    distance = float(np.sqrt(np.mean(((value - mean) / np.maximum(std, 1e-6)) ** 2)))
    score = float(math.exp(-distance))
    return NormalDistance(score=score, distance=distance)
