"""Representação do normal por centro e desvio padrão populacional no I8."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np


@dataclass
class NormalModel:
    product_id: str
    model_version: str
    feature_extractor: str
    weights: str
    image_count: int
    embedding_dim: int
    mean: list[float]
    std: list[float]
    created_at: str

    @classmethod
    def build(cls, embeddings: np.ndarray, product_id: str,
              model_version: str, feature_extractor: str, weights: str) -> "NormalModel":
        values = np.asarray(embeddings, dtype=np.float64)
        if values.ndim != 2 or 0 in values.shape:
            raise ValueError("Esperada uma matriz não vazia de N embeddings.")
        if not np.isfinite(values).all():
            raise ValueError("Embeddings contêm valores não finitos.")
        if not all(s.strip() for s in (product_id, model_version, feature_extractor, weights)):
            raise ValueError("Identificadores e versão não podem estar vazios.")
        return cls(product_id, model_version, feature_extractor, weights,
                   values.shape[0], values.shape[1], values.mean(axis=0).tolist(),
                   values.std(axis=0).tolist(), datetime.now(timezone.utc).isoformat())

    def save(self, path: Path) -> None:
        """Um JSON pequeno mantém metadados e vetores no mesmo artefato."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(asdict(self), stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")

    @classmethod
    def load(cls, path: Path) -> "NormalModel":
        with path.open(encoding="utf-8") as stream:
            return cls(**json.load(stream))
