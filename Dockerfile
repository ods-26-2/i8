# Usa a imagem oficial leve do Python baseada em Debian Bookworm
FROM python:3.11-slim

# Evita a criacao de ficheiros .pyc dentro do contentor
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Garante que a raiz /app esta no caminho de importação do Python
ENV PYTHONPATH=/app

# Define o diretorio de trabalho interno
WORKDIR /app

# Copia e instala as dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o codigo-fonte do projeto para dentro do contentor
COPY . .

# Executa o Pytest 
CMD ["pytest", "-v"]