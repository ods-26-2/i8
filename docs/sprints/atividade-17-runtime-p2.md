# Sprint 3 — atividade 17: integração CPU do I8 com P2

O I8 passa a poder executar sua ResNet18 pelo P2 real. Imagem e pré-processamento continuam no I8; P2 executa o tensor; modelo normal, classificador e política continuam no I8. O caminho PyTorch existente permanece como opção padrão.

A seleção é explícita por `--p2-engine` no replay. Não há troca silenciosa para Torch quando P2 falha. Nesta entrega, o backend permitido é ONNX Runtime CPU em FP32 (`P2_BACKEND=ort`). TensorRT/Jetson exige outra prova.

## Como testar no Linux com Docker

Na pasta que contém I8 e o clone P2, fixe P2 no commit abaixo. Execute a construção na raiz do I8:

```bash
git clone https://github.com/ods-26-2/p2.git ../p2
git -C ../p2 checkout fddf028c025b4a9be22d3a67696a13c0c65b9b0e
mkdir -p validacao-local/evidencias-p2
docker build --build-context p2=../p2 -f validacao-local/Dockerfile.p2 -t ver1-i8-p2:test .
docker run --rm --network none --cpus 2 --memory 3g \
  -e P2_EVIDENCE_DIR=/evidencias \
  -v "$PWD/validacao-local/evidencias-p2:/evidencias" \
  ver1-i8-p2:test python -m pytest -q -p no:cacheprovider \
  --junitxml=/evidencias/regressao.xml
```

A construção instala P2 e baixa pesos oficiais. A execução dos testes não tem rede. Não inicia Kafka, banco ou hardware; o container termina com `--rm`. O workflow `testes-p2.yml` repete esse procedimento e guarda XML/JSON/log por 30 dias.

## Pacote e replay fora dos testes

Dentro desse ambiente, prepare uma exportação nova. `export_p2_extractor` recusa diretório existente para preservar artefatos anteriores:

```bash
python -m scripts.export_p2_extractor --output /tmp/i8-resnet-package --version 1.0.0
p2-build /tmp/i8-resnet-package --cpu-only --engine-dir /tmp/i8-engines
export P2_ENGINE_DIR=/tmp/i8-engines
export P2_BACKEND=ort
```

Acrescente ao comando de replay já documentado:

```text
--p2-engine i8-resnet18-imagenet-1.0.0
--artifact-version i8-resnet18-imagenet-1.0.0-fp32
```

No modo P2, `artifact_version` deve ser exatamente o `engine_version` efetivo. `--kafka` continua opcional e exige as configurações do laboratório Kafka. O teste deste incremento usa transporte em memória e não comprova envio ao A1.

O pacote MODEL contém `metadata.json` e `resnet18.onnx`. O metadado acrescenta um bloco `i8_extractor` de rastreabilidade, preservado pelo build P2. O adaptador verifica nomes, formas, tipos, versão, metadados e SHA-256 do ONNX indicado pelo manifesto P2. Esses metadados não são assinatura ou homologação; a prova compara numericamente a exportação oficial com Torch.

`load/info/infer/release` pertencem ao P2; o adaptador controla o ciclo de vida. O handle é liberado ao encerrar o replay ou quando falha a preparação do pipeline/transporte. Erros de engine, entrada e saída interrompem a execução. A política e sua fórmula não mudam.

## Critérios comprovados e pendentes

A prova usa ResNet18 e pesos oficiais reais, P2 real e imagens sintéticas identificadas. Compara vetores com Torch (`atol=5e-5`, `rtol=1e-4`) e verifica decisão equivalente com os artefatos históricos. Exercita recorte/correlação e evento industrial 2.0 em memória. Não comprova precisão com peças reais nem todos os quatro resultados industriais.

**A atividade 17 avançou, mas não está encerrada:** faltam dados reais acessíveis, validação do pacote aceito pela equipe, entrada operacional P4/I1 ou P6 e medição no alvo. A atividade 18 depende também da demonstração real da atividade 15 e da entrega pelo Kafka até o A1/PostgreSQL.

[Atualização das dependências](dependencias-fechamento-atualizacao.md). [Evidências](../evidencias/atividade-17-p2/README.md).
