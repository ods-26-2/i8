# Evidências S3-04 — Extração e similaridade

Data: 05/11/2026. Base I8: `3100ce3eb3b06d928b0418e29827b727d4bf9a30`.
Branch: `feat/s3-04-extrator-unico`. Resultados obtidos sobre as alterações locais,
antes do commit de publicação. O escopo corresponde à atividade 10 do plano.

- [Regressão anterior](antes.txt): 148 testes aprovados e dois Kafka ignorados.
- [Suíte nova](depois.txt): 171 aprovados e os mesmos dois ignorados.
- [Medição CPU](medicao.json): pesos oficiais, cinco repetições após aquecimento.

Os 23 casos novos cobrem vetores inválidos, incompatibilidade dimensional,
normalização, imagem/arquivo com a mesma transformação, um único extrator,
preservação da métrica do modelo normal e wheel instalado fora do checkout.
Os testes usam doubles explicitamente; a medição adicional executa a ResNet18
real com pesos oficiais. Nenhum teste atribui qualidade industrial a dados sintéticos.

## Reproduzir em Docker

Na raiz I8:

```bash
docker build -f validacao-local/Dockerfile.inferencia -t ver1-i8-inferencia:test .
docker run --rm --network none ver1-i8-inferencia:test
mkdir -p validacao-local/evidencias-s304
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD/validacao-local/evidencias-s304:/data" \
  ver1-i8-inferencia:test python docs/evidencias/s3-04/gerar_entradas.py /data/entradas
docker run --rm --cpus 2 --memory 2g --user "$(id -u):$(id -g)" \
  -e TORCH_HOME=/tmp/torch \
  -v "$PWD/validacao-local/evidencias-s304:/data" \
  ver1-i8-inferencia:test python -m scripts.benchmark_similarity \
  --reference /data/entradas/referencia.ppm --image /data/entradas/alvo.ppm \
  --output /data/medicao.json --repeat 5
```

A construção baixa dependências; a suíte executa sem rede e não baixa pesos.
O último comando precisa acessar o download oficial de pesos na primeira
execução do container. `TORCH_HOME` fica no próprio container descartável.
Não há Kafka ou banco nesse laboratório; os containers terminam com `--rm`.

O JSON identifica os arquivos por SHA-256, versões, dispositivo, threads, métrica,
tempos mínimo/mediano/máximo e memória. `ru_maxrss` mede o pico do processo inteiro,
incluindo alocações nativas Torch, imports e carga dos pesos. O tamanho lógico
dos parâmetros, cerca de 42,6 MiB, é informado separadamente e não representa
toda a memória do processo. Os dois aliases apontaram para o mesmo modelo.

A [automação de extração e similaridade](../../../.github/workflows/testes-similaridade.yml)
repete a suíte em Docker e guarda XML/log no pacote `evidencias-similaridade-i8`
por 30 dias. O benchmark de recursos é uma medição local, não executada a cada PR.

Esta entrega não treina, calibra ou avalia classes reais, não modifica o contrato
Kafka, não publica no barramento compartilhado e não comprova desempenho na
Jetson. A prova publisher/A1 continua separada. Os tempos dependem do ambiente.
