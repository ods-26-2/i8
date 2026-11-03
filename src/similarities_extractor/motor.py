import logging
from pathlib import Path
from typing import Union, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models

from src.preprocessing import load_image
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
    ) -> None:
        """
        Args:
            device_mode: Dispositivo de execução ('auto', 'cpu', 'cuda').
            weights: Pesos pré-treinados do modelo. Passar None para pesos aleatórios em testes.
        """
        self.device = self._resolve_device(device_mode)
        self.modelo = self._build_model(weights)

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

    def extrair_vetor(self, imagem_input: Union[str, Path]) -> torch.Tensor:

        """
        Carrega uma imagem e extrai o seu vetor de características.

        Args: imagem_input: Caminho do ficheiro (str/Path).

        Returns: torch.Tensor: Vetor de características extraído de dimensão (1, D).

        Raises: ImageProcessingError: Se a imagem não puder ser lida ou processada.
        """

        path = Path(imagem_input)
        if not path.is_file():
            raise ImageProcessingError(f"O ficheiro de imagem não existe: {path}")

        try:
            img_tensor = load_image(path).unsqueeze(0).to(self.device)
            
            with torch.inference_mode():
                vetor = self.modelo(img_tensor)

            return vetor
        except Exception as err:
            logger.error("Erro durante o cálculo de inferência: %s", err)
            raise ImageProcessingError(f"Falha ao extrair vetor da imagem: {err}") from err

    def calcular_score(self, vetor_alvo: torch.Tensor, vetor_referencia: torch.Tensor) -> float:
        """
        Calcula a similaridade de cosseno entre dois vetores e normaliza.

        Returns: float: Valor escalar de similaridade normalizado (0.0 a 1.0).
        """
        if vetor_alvo.shape != vetor_referencia.shape:
            logger.warning("Dimensões distintas detetadas: %s vs %s", vetor_alvo.shape, vetor_referencia.shape)

        similaridade = F.cosine_similarity(vetor_alvo, vetor_referencia)
        valor_bruto = similaridade.item()
        
        # Normalizacao da escala de [-1, 1] para [0, 1] exigida pela Arquitetura 6c
        score_normalizado = (valor_bruto + 1.0) / 2.0
        score_normalizado = max(0.0, min(1.0, score_normalizado))
        
        return float(score_normalizado)