"""Carregamento e transformação das imagens analisadas pelo I8."""

from pathlib import Path

from PIL import Image, ImageOps
from torch import Tensor
from torchvision.models import ResNet18_Weights

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
WEIGHTS = ResNet18_Weights.IMAGENET1K_V1


def list_images(directory: Path) -> list[Path]:
    """Lista somente arquivos do diretório informado, em ordem estável."""
    if not directory.is_dir():
        raise ValueError(f"Diretório de imagens inexistente ou inválido: {directory}")
    paths = sorted(p for p in directory.iterdir()
                   if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    if not paths:
        raise ValueError(f"Nenhuma imagem suportada encontrada em: {directory}")
    return paths


def load_image(path: Path) -> Tensor:
    """RGB, resize 256, recorte central 224 e normalização ImageNet."""
    with Image.open(path) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        return WEIGHTS.transforms()(rgb)
