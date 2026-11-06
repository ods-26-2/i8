"""Compatibility facade for the canonical I8 extraction pipeline.

New code should use :class:`feature_extractor.FeatureExtractor` directly.
This facade keeps the historical Portuguese API while guaranteeing the same
ResNet18 weights and ImageNet preprocessing used by training and inference.
"""

from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.models import resnet18

from feature_extractor import FeatureExtractor
from preprocessing import WEIGHTS, transform_image


class MotorSimilaridade:
    """Extract canonical embeddings and calculate bounded cosine similarity."""

    def __init__(self, device_mode: str = "auto", *, weights=WEIGHTS) -> None:
        if weights is None:
            model = resnet18(weights=None)
            self.extractor = FeatureExtractor(device_mode, weights=None, model=model)
        else:
            self.extractor = FeatureExtractor(device_mode, weights=weights)
        self.device = self.extractor.device

    def extrair_vetor(self, imagem_input: str | Path | Image.Image) -> torch.Tensor:
        """Return a ``(1, 512)`` embedding using the canonical preprocessing."""
        if isinstance(imagem_input, (str, Path)):
            path = Path(imagem_input)
            if not path.is_file():
                raise FileNotFoundError(f"O ficheiro de imagem não existe: {path}")
            with Image.open(path) as image:
                tensor = transform_image(image)
        elif isinstance(imagem_input, Image.Image):
            tensor = transform_image(imagem_input)
        else:
            raise TypeError("imagem_input deve ser caminho ou PIL.Image.Image")
        return self.extractor.extract(tensor).unsqueeze(0)

    @staticmethod
    def calcular_score(vetor_alvo: torch.Tensor, vetor_referencia: torch.Tensor) -> float:
        """Return cosine similarity normalized from ``[-1, 1]`` to ``[0, 1]``."""
        raw = float(F.cosine_similarity(vetor_alvo, vetor_referencia).item())
        return max(0.0, min(1.0, (raw + 1.0) / 2.0))


__all__ = ["MotorSimilaridade"]
