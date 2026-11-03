"""Persisted reference-normal model."""
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
    preprocessing_version: str = "imagenet-resnet18-v1"

    @classmethod
    def build(cls, embeddings, product_id, model_version, feature_extractor, weights):
        values=np.asarray(embeddings,dtype=np.float64)
        if values.ndim!=2 or 0 in values.shape or not np.isfinite(values).all(): raise ValueError("embeddings inválidos")
        if not all(isinstance(s,str) and s.strip() for s in (product_id,model_version,feature_extractor,weights)): raise ValueError("metadados inválidos")
        return cls(product_id,model_version,feature_extractor,weights,values.shape[0],values.shape[1],values.mean(axis=0).tolist(),values.std(axis=0).tolist(),datetime.now(timezone.utc).isoformat())
    def save(self,path:Path):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("x",encoding="utf-8") as stream: json.dump(asdict(self),stream,ensure_ascii=False,indent=2,allow_nan=False); stream.write("\n")
    @classmethod
    def load(cls,path:Path):
        with path.open(encoding="utf-8") as stream: value=cls(**json.load(stream))
        if value.embedding_dim!=len(value.mean) or value.embedding_dim!=len(value.std) or value.image_count<1 or not np.isfinite(value.mean).all() or not np.isfinite(value.std).all(): raise ValueError("artefato normal inválido")
        if value.preprocessing_version!="imagenet-resnet18-v1": raise ValueError("pré-processamento incompatível")
        return value
