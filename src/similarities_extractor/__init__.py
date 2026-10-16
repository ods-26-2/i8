"""Pacote do Motor de Similaridade Visual."""

from .motor import MotorSimilaridade
from .triagem import aplicar_triagem_limiar_duplo
from .exceptions import (
    MotorSimilaridadeError,
    ImageProcessingError,
    ModelInitializationError,
)

__all__ = [
    "MotorSimilaridade",
    "aplicar_triagem_limiar_duplo",
    "MotorSimilaridadeError",
    "ImageProcessingError",
    "ModelInitializationError",
]