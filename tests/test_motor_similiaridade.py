import pytest
from PIL import Image, ImageDraw
import torch

from src.similarities_extractor import (
    MotorSimilaridade, 
    aplicar_triagem_limiar_duplo,
    ImageProcessingError
)

@pytest.fixture
def motor_teste():
    """
    Inicializa o motor em modo CPU e SEM pesos pré-treinados (weights=None).
    Isto garante que o teste é instantâneo e funciona offline na esteira de CI/CD.
    """
    return MotorSimilaridade(device_mode="cpu", weights=None)

@pytest.fixture
def imagens_teste(tmp_path):
    """Cria imagens temporárias para os testes."""
    path_ouro = tmp_path / "peca_ouro.jpg"
    path_duvida = tmp_path / "peca_duvida.jpg"
    
    img_ouro = Image.new('RGB', (300, 300), color=(180, 180, 180))
    img_ouro.save(path_ouro)
    
    img_duvida = img_ouro.copy()
    ImageDraw.Draw(img_duvida).line([100, 100, 140, 140], fill=(200, 0, 0), width=5)
    img_duvida.save(path_duvida)
    
    return path_ouro, path_duvida


# --- Testes de Caminho Feliz (Happy Path) ---

def test_extracao_vetor(motor_teste, imagens_teste):
    """Verifica a extração correta de tensores."""
    path_ouro, _ = imagens_teste
    
    vetor = motor_teste.extrair_vetor(path_ouro)
    
    assert isinstance(vetor, torch.Tensor)
    assert vetor.shape[-1] > 0


def test_calculo_similaridade_identica(motor_teste, imagens_teste):
    """Garante que a mesma imagem tem similaridade 1.0."""
    path_ouro, _ = imagens_teste
    
    vetor1 = motor_teste.extrair_vetor(path_ouro)
    vetor2 = motor_teste.extrair_vetor(path_ouro)
    
    score = motor_teste.calcular_score(vetor1, vetor2)
    assert score == pytest.approx(1.0, rel=1e-3)


def test_triagem_limiar_duplo_regras():
    """Testa as lógicas de negócio dos limiares."""
    assert aplicar_triagem_limiar_duplo(0.96)[0] == "APROVADO"
    assert aplicar_triagem_limiar_duplo(0.80)[0] == "REPROVADO"
    assert aplicar_triagem_limiar_duplo(0.90)[0] == "DUVIDA"


# --- Testes de Caminho Triste (Sad Path / Casos de Erro) ---

def test_deve_falhar_com_arquivo_inexistente(motor_teste):
    """Garante que a exceção correta é lançada se a imagem não existir."""
    caminho_invalido = "diretorio_fantasma/imagem_que_nao_existe.jpg"
    
    # O pytest.raises verifica se a exceção esperada foi realmente atirada
    with pytest.raises(ImageProcessingError, match="não existe"):
        motor_teste.extrair_vetor(caminho_invalido)


def test_deve_falhar_com_arquivo_corrompido(motor_teste, tmp_path):
    """Garante que a exceção correta é lançada se o ficheiro não for uma imagem válida."""
    arquivo_corrompido = tmp_path / "texto_falso.jpg"
    arquivo_corrompido.write_text("Isto não é um binário de imagem, é apenas texto.")
    
    with pytest.raises(ImageProcessingError, match="inválido ou corrompido"):
        motor_teste.extrair_vetor(arquivo_corrompido)