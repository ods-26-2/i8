"""ResNet18 pré-treinada sem a camada de classificação."""

import torch
from torch import Tensor, nn
from torchvision.models import resnet18

from i8.preprocessing import WEIGHTS


class FeatureExtractor:
    name = "resnet18"
    weights_name = "IMAGENET1K_V1"
    embedding_dim = 512

    def __init__(self, device: str = "cpu") -> None:
        if device not in {"cpu", "auto", "cuda"}:
            raise ValueError("Dispositivo deve ser cpu, auto ou cuda.")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA solicitada, mas não está disponível.")
        self.device = torch.device(device)
        self.model = resnet18(weights=WEIGHTS)
        self.model.fc = nn.Identity()
        self.model.to(self.device).eval()
        self.model.requires_grad_(False)

    @torch.inference_mode()
    def extract(self, image: Tensor) -> Tensor:
        """Recebe C×H×W e devolve um vetor de 512 valores na CPU."""
        return self.model(image.unsqueeze(0).to(self.device)).squeeze(0).cpu()
