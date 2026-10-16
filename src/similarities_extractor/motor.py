import logging
from pathlib import Path
from typing import Union, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image, UnidentifiedImageError

from .exceptions import ImageProcessingError, ModelInitializationError

# Registo de logs estruturado
logger = logging.getLogger(__name__)


class MotorSimilaridade:
    """
    Motor responsável pela extração de vetores de características (embeddings)
    e cálculo de similaridade visual entre imagens utilizando redes neuronais.
    """

    def __init__(
        self,
        device_mode: str = "auto",
        weights: Optional[models.ResNet18_Weights] = models.ResNet18_Weights.DEFAULT,
        custom_transform: Optional[transforms.Compose] = None
    ) -> None:
        """
        Inicializa a arquitetura do modelo e o pipeline de pré-processamento.

        Args:
            device_mode: Dispositivo de execução ('auto', 'cpu', 'cuda').
            weights: Pesos pré-treinados do modelo. Passar None para pesos aleatórios em testes.
            custom_transform: Pipeline opcional para substituir o pré-processamento padrão.
        """
        self.device = self._resolve_device(device_mode)
        self.modelo = self._build_model(weights)
        self.preprocesso = custom_transform or self._default_transform()

    def _resolve_device(self, device_mode: str) -> torch.device:
        """Define o dispositivo de computação (CPU/GPU)."""
        if device_mode == "auto":
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            device = torch.device(device_mode)
        
        logger.info("MotorSimilaridade inicializado no dispositivo: %s", device)
        return device

    def _build_model(self, weights: Optional[models.ResNet18_Weights]) -> nn.Module:
        """Carrega e prepara a arquitetura ResNet18."""
        try:
            modelo = models.resnet18(weights=weights)
            modelo.fc = nn.Identity()  # Remove a camada de classificação final
            modelo.to(self.device)
            modelo.eval()
            return modelo
        except Exception as err:
            logger.error("Falha ao inicializar o modelo ResNet18: %s", err)
            raise ModelInitializationError(f"Erro ao inicializar a rede neuronal: {err}") from err

    @staticmethod
    def _default_transform() -> transforms.Compose:
        """Retorna o pipeline padrão de pré-processamento de imagem."""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def extrair_vetor(self, imagem_input: Union[str, Path, Image.Image]) -> torch.Tensor:
        """
        Carrega uma imagem e extrai o seu vetor de características.

        Args:
            imagem_input: Caminho do ficheiro (str/Path) ou objeto PIL.Image.

        Returns:
            torch.Tensor: Vetor de características extraído de dimensão (1, D).

        Raises:
            ImageProcessingError: Se a imagem não puder ser lida ou processada.
        """
        img = self._load_image(imagem_input)

        try:
            img_tensor = self.preprocesso(img).unsqueeze(0).to(self.device)
            
            # torch.inference_mode() é a evolução do torch.no_grad() para maior desempenho em inferência
            with torch.inference_mode():
                vetor = self.modelo(img_tensor)

            return vetor
        except Exception as err:
            logger.error("Erro durante o cálculo de inferência: %s", err)
            raise ImageProcessingError(f"Falha ao extrair vetor da imagem: {err}") from err

    def _load_image(self, imagem_input: Union[str, Path, Image.Image]) -> Image.Image:
        """Garante a leitura segura de ficheiros e a conversão do espaço de cor para RGB."""
        if isinstance(imagem_input, (str, Path)):
            path = Path(imagem_input)
            if not path.is_file():
                raise ImageProcessingError(f"O ficheiro de imagem não existe: {path}")
            try:
                with Image.open(path) as img:
                    return img.convert("RGB")
            except (UnidentifiedImageError, OSError) as err:
                raise ImageProcessingError(f"Ficheiro de imagem inválido ou corrompido em {path}: {err}") from err
        elif isinstance(imagem_input, Image.Image):
            return imagem_input.convert("RGB")
        else:
            raise ImageProcessingError(
                f"Entrada inválida. Esperado str, Path ou PIL.Image, recebido: {type(imagem_input).__name__}"
            )

    def calcular_score(self, vetor_alvo: torch.Tensor, vetor_referencia: torch.Tensor) -> float:
        """
        Calcula a similaridade de cosseno entre dois vetores.

        Returns:
            float: Valor escalar de similaridade (-1.0 a 1.0).
        """
        if vetor_alvo.shape != vetor_referencia.shape:
            logger.warning("Dimensões distintas detetadas: %s vs %s", vetor_alvo.shape, vetor_referencia.shape)

        similaridade = F.cosine_similarity(vetor_alvo, vetor_referencia)
        return float(similaridade.item())