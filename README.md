# I8 — Modelagem do normal (Sprint 1)

Entrega de João Vitor: uma representação inicial da peça correta, construída
exclusivamente a partir de imagens previamente consideradas normais. O mesmo
código atende diferentes produtos; cada execução informa seu `product_id`.

Modelar o normal, nesta versão, significa extrair um vetor de 512 características
de cada imagem e calcular o centro (média por dimensão) desses vetores. Também
guardamos o desvio padrão populacional (`ddof=0`). Não há treinamento da rede.

## Arquitetura

- `i8/preprocessing/`: listagem de imagens, correção da orientação EXIF,
  conversão RGB e transformação oficial dos pesos da ResNet18.
- `i8/feature_extractor/`: ResNet18 com pesos `IMAGENET1K_V1`, camada final
  substituída por identidade, modo de avaliação e gradientes desativados.
- `i8/normal_model/`: cálculo das estatísticas e salvamento/leitura de JSON.
- `i8/similarities_extractor/`: extração de vetores e similaridade por cosseno.
- `scripts/build_normal_model.py`: argumentos, execução e resumo no terminal.
- `tests/`: testes locais com imagens sintéticas pequenas e temporárias.
- `models/`: destino sugerido dos artefatos, ignorados pelo Git.
- `shared/` e `docs/contratos/`: contrato de saída e exemplos de integração.

Os parâmetros de execução são passados pela CLI. O `pyproject.toml` mantém a
configuração do pacote e dos testes na raiz do repositório.

## Instalação

Use Python 3.11 ou superior em ambiente virtual. Na raiz do repositório:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Em Linux/macOS, ative com `source .venv/bin/activate`. Para uso sem testes,
instale apenas `requirements.txt`.

Dependências: PyTorch, torchvision, NumPy e Pillow; pytest para testes.
O instalador deve resolver uma dupla compatível de torch/torchvision dentro das
faixas declaradas. CUDA não é obrigatória. Para CUDA, o ambiente precisa de uma
instalação compatível do PyTorch e dos drivers.

Na primeira execução com imagens válidas, torchvision baixa os pesos pré-treinados
(aproximadamente 45 MB) para o cache do PyTorch. Essa etapa requer internet; depois,
o cache pode ser reutilizado offline. `TORCH_HOME` permite escolher o cache.
Falhas no download interrompem a execução: não há fallback para pesos aleatórios.

## Dataset e execução

Prepare imagens normais do mesmo produto e condições de captura consistentes:

```text
data/
└── produto_001/
    └── train/
        └── normal/
            ├── img001.jpg
            └── img002.png
```

`data/` não é versionado. Os formatos aceitos são JPG/JPEG, PNG, BMP, TIFF/TIF e
WebP, com extensões sem distinção entre maiúsculas e minúsculas. A listagem é
ordenada, sem busca em subpastas; arquivos de outras extensões são ignorados.

Na raiz do repositório:

```powershell
python scripts/build_normal_model.py --product produto_001 --images ./data/produto_001/train/normal --output ./models
```

Parâmetros opcionais: `--model-version 1.0.0` e `--device cpu|auto|cuda`.
CPU é o padrão; `auto` seleciona CUDA quando disponível e CPU caso contrário.
Solicitar `cuda` explicitamente sem suporte gera erro.

Para outro produto, altere `--product` e `--images`. Cada execução cria um arquivo
único; não sobrescreve modelos anteriores. O identificador do produto fica nos
metadados, sem ser usado como caminho no sistema de arquivos.

O resumo informa produto, imagens encontradas/processadas/ignoradas, extrator,
dispositivo, dimensão e caminho do artefato. Imagens corrompidas geram avisos com
seus caminhos e são ignoradas. Pasta inválida, vazia ou sem imagens válidas resulta
em código de saída 1 e nenhum novo artefato.

## Artefato

Um arquivo `normal_<data UTC>_<identificador>.json` contém:

| Campo | Conteúdo |
| --- | --- |
| `product_id` | Identificador recebido pela CLI |
| `model_version` | Versão informada, padrão `1.0.0` |
| `feature_extractor` | `resnet18` |
| `weights` | `IMAGENET1K_V1` |
| `image_count` | Quantidade efetivamente processada |
| `embedding_dim` | 512 |
| `mean` | Lista com a média por dimensão |
| `std` | Lista com o desvio padrão por dimensão |
| `created_at` | Data/hora ISO 8601 com fuso UTC |

JSON foi escolhido porque os dois vetores de 512 valores são pequenos, legíveis
e permanecem junto dos metadados, sem sincronização entre arquivos. Leitura:

```python
from pathlib import Path
from i8.normal_model import NormalModel

model = NormalModel.load(Path("models/normal_<data UTC>_<identificador>.json"))
print(model.product_id, model.embedding_dim, model.mean[:5])
```

## Testes

```powershell
python -m pytest -q
```

Os testes não exigem GPU, internet nem pesos baixados. Exercitam o pré-processamento
real e a arquitetura ResNet18 real; substituem o carregamento dos pesos por pesos
aleatórios **somente nos testes**. Isso verifica dimensões e funcionamento do
pipeline, sem comprovar qualidade dos embeddings pré-treinados. Também verificam
média, desvio, leitura/escrita, dados inválidos e diferentes produtos.

## Contratos de integração

- `shared/schemas/i8-piece-analyzed.schema.json`: schema do evento publicado;
- `shared/mocks/i8-piece-*.json`: exemplos de saída do I8;
- `docs/contratos/i8-a1.md`: contrato entre I8 e A1;
- `docs/contratos/b1.md`: envelope comum dos eventos.

A taxonomia completa e os eventos de triagem pertencem ao A1 e, por isso, não
foram duplicados neste repositório.

## Limitações e escopo

- Esta implementação ainda **não classifica tipos conhecidos de defeitos**,
  **não executa triagem** e **não implementa similaridade final**. Essas funções
  pertencem a outras etapas/responsabilidades: classificação na Sprint 2 de João;
  similaridade e triagem de Ícaro. Não implementa responsabilidades de Samuel.
- Não altera o contrato I8 → A1 nem implementa frontend, backend A1, banco,
  MQTT, P7, I11/P2, relatórios ou auditoria.
- Pesos ImageNet são genéricos e não foram ajustados nem validados para um produto
  industrial. A média é uma referência inicial, não um detector ou decisão de
  conformidade; não produz distância, limiar, confiança ou aprovação/reprovação.
- O resize mantém a proporção com lado menor 256, seguido de recorte central
  224×224, conversão para [0, 1] e normalização ImageNet. O recorte pode perder
  detalhes nas bordas; use imagens com o produto centralizado.
- Iluminação, fundo, posição e diversidade dos dados afetam a representação.
  Uma única imagem é aceita, mas seu desvio será zero e sua representatividade
  limitada. Diferentes modos normais podem não ser bem resumidos por uma média.
- Processa uma imagem por vez e mantém embeddings em memória (N×512). Não é um
  pipeline de tempo real e não promete o SLA de 200 ms do sistema completo.
- Modelos, pesos e datasets grandes não devem ser adicionados ao Git.

## Docker (Build e Teste)

- Construir o docker para testes.
- Rodar a pasta de testes.
- Adicionando o seginte comando no terminal: `docker build -t motor-similaridade . && docker run --rm motor-similaridade`.