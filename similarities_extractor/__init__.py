"""Shared extraction and explicit pairwise cosine similarity; no industrial triage."""

import math
from pathlib import Path

from PIL import Image
import torch
import torch.nn.functional as F

from feature_extractor import FeatureExtractor
from preprocessing import load_image, transform_image


class ImageProcessingError(ValueError):
    """Image or extracted embedding is invalid."""


class ModelInitializationError(RuntimeError):
    """The canonical feature extractor could not be initialized."""


class MotorSimilaridade:
    """Reuse a caller's extractor, or create one canonical extractor.

    Extraction returns one CPU embedding with shape (1, D), preserving the
    original public layout. Pairwise scores now use cosine-affine-v1 in [0,1].
    This pairwise metric is separate from the calibrated normal-model score.
    """

    score_metric = "cosine-affine-v1"

    def __init__(self, device_mode="auto", *, extractor=None):
        try:
            self.extractor = extractor if extractor is not None else FeatureExtractor(device_mode)
        except Exception as exc:
            raise ModelInitializationError(str(exc)) from exc
        self.device = self.extractor.device
        # Compatibility aliases reference the same model, never a second ResNet.
        self.modelo = self.extractor.model

    def extrair_vetor(self, imagem_input):
        try:
            if isinstance(imagem_input, (str, Path)):
                tensor = load_image(Path(imagem_input))
            elif isinstance(imagem_input, Image.Image):
                tensor = transform_image(imagem_input)
            else:
                raise ValueError("Esperado caminho ou PIL.Image")
            vector = self.extractor.extract(tensor)
            if vector.ndim != 1 or vector.numel() != self.extractor.embedding_dim:
                raise ValueError("Embedding deve conter uma única referência da dimensão esperada")
            if not torch.isfinite(vector).all():
                raise ValueError("Embedding não finito")
            return vector.unsqueeze(0)
        except Exception as exc:
            raise ImageProcessingError(f"Falha ao extrair vetor da imagem: {exc}") from exc

    @staticmethod
    def _vector(value):
        if not isinstance(value, torch.Tensor) or not value.is_floating_point():
            raise ValueError("Embedding deve ser um tensor de ponto flutuante")
        if value.ndim == 2 and value.shape[0] == 1:
            value = value.squeeze(0)
        if value.ndim != 1 or value.numel() == 0 or not torch.isfinite(value).all():
            raise ValueError("Embedding deve ser um vetor finito e não vazio")
        value = value.detach().to(device="cpu", dtype=torch.float64)
        norm = torch.linalg.vector_norm(value)
        if not torch.isfinite(norm) or norm <= 0:
            raise ValueError("Embedding deve ter norma positiva e finita")
        return value / norm

    def calcular_score(self, vetor_alvo, vetor_referencia):
        left, right = self._vector(vetor_alvo), self._vector(vetor_referencia)
        if left.shape != right.shape:
            raise ValueError("Embeddings possuem dimensões incompatíveis")
        raw = F.cosine_similarity(left, right, dim=0).item()
        if not math.isfinite(raw):
            raise ValueError("Similaridade não finita")
        return float(max(0.0, min(1.0, (raw + 1.0) / 2.0)))
