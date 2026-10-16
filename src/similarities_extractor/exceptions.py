"""Exceções personalizadas para o motor de similaridade."""

class MotorSimilaridadeError(Exception):
    """Exceção base para todos os erros do motor de similaridade."""
    pass


class ImageProcessingError(MotorSimilaridadeError):
    """Lançada quando ocorre uma falha ao carregar ou pré-processar uma imagem."""
    pass


class ModelInitializationError(MotorSimilaridadeError):
    """Lançada quando ocorre uma falha ao inicializar a rede neuronal."""
    pass