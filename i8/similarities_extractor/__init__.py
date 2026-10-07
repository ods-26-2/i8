"""Extração de vetores e cálculo de similaridade entre imagens."""

import torch
import torchvision.models as models
import torchvision.transforms as transforms
import torch.nn.functional as F
from PIL import Image

class MotorSimilaridade:
    def __init__(self, device_mode="auto"):
        
        # Configuração de Dispositivo 
        if device_mode == "auto":
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device_mode)
            
        self.modelo = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        self.modelo.fc = torch.nn.Identity() 
        self.modelo.to(self.device)
        self.modelo.eval()
        
        # Pipeline de Pre-processamento
        self.preprocesso = transforms.Compose([
            transforms.Resize((224, 224)), # Redimensionamento
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def extrair_vetor(self, imagem_input):
    
        # Aceita tanto o caminho do arquivo (string) quanto a imagem em memoria (PIL Image).
        
        if isinstance(imagem_input, str):
            img = Image.open(imagem_input).convert('RGB')
        else:
            img = imagem_input.convert('RGB')
            
        # Joga a imagem pre-processada para a GPU (ou CPU)
        img_tensor = self.preprocesso(img).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            vetor = self.modelo(img_tensor)
            
        return vetor

    def calcular_score(self, vetor_alvo, vetor_referencia):
        # Calcula a similaridade de cosseno
        similaridade = F.cosine_similarity(vetor_alvo, vetor_referencia)
        return similaridade.item()
