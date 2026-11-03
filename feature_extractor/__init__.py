"""ResNet18 pré-treinada sem a camada de classificação."""

import torch
from torch import Tensor, nn
from torchvision.models import resnet18

try:  # package import (i8.feature_extractor) and repository-root import both work
    from ..preprocessing import WEIGHTS
except ImportError:
    from preprocessing import WEIGHTS


class FeatureExtractor:
    name = "resnet18"
    weights_name = "IMAGENET1K_V1"
    embedding_dim = 512
    preprocessing_version = "imagenet-resnet18-v1"

    def __init__(self, device: str = "cpu", *, weights=WEIGHTS, model=None) -> None:
        if device not in {"cpu", "auto", "cuda"}:
            raise ValueError("Dispositivo deve ser cpu, auto ou cuda.")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA solicitada, mas não está disponível.")
        self.device = torch.device(device)
        if weights is None and model is None:
            raise ValueError("Pesos oficiais são obrigatórios fora de testes explícitos.")
        self.weights_name = getattr(weights, "name", "TEST_DOUBLE")
        self.model = model if model is not None else resnet18(weights=weights)
        self.model.fc = nn.Identity()
        self.model.to(self.device).eval()
        self.model.requires_grad_(False)

    @torch.inference_mode()
    def extract(self, image: Tensor) -> Tensor:
        """Recebe C×H×W e devolve um vetor de 512 valores na CPU."""
        if image.ndim != 3 or tuple(image.shape) != (3, 224, 224):
            raise ValueError("imagem deve ser um tensor C×224×224")
        result = self.model(image.unsqueeze(0).to(self.device)).squeeze(0).cpu()
        if result.ndim != 1 or result.numel() != self.embedding_dim:
            raise ValueError(f"extrator devolveu dimensão incompatível: {tuple(result.shape)}")
        if not torch.isfinite(result).all():
            raise ValueError("extrator devolveu vetor não finito")
        return result
