# I8 — Inferência e modelagem do normal (Sprint 3)

Para acompanhar a entrega do publisher, comece pelo
[resumo da atividade 06 e sua relação com a arquitetura](docs/sprints/atividade-06-resumo.md).
Para extração e similaridade, consulte o [resumo da atividade 10](docs/sprints/atividade-10-resumo.md).

Fluxo local reproduzível: manifesto → modelo normal e classificador → calibração
→ inferência → evento 6c validado. A execução real usa ResNet18 com pesos oficiais
`IMAGENET1K_V1`; testes podem injetar doubles explicitamente.

## Instalação

```powershell
uv sync --extra dev
uv build --wheel
```

O wheel inclui `preprocessing`, `feature_extractor`, `normal_model`, `src` e os
comandos instaláveis. Contratos e taxonomia podem ser importados sem importar
Torch: `import src.contracts, src.taxonomy`.

## Dataset e comandos

**Etapas 11–15 ainda bloqueadas para reprodução neste checkout:** não foram encontradas as 369 imagens, manifesto real ou previsões de calibração/teste. Os modelos e relatórios publicados são históricos. Consulte o [inventário, correções e roteiro exato](docs/evidencias/etapas-11-15/README.md); nenhum mock substitui os dados ausentes.

[`dataset/manifest.example.csv`](dataset/manifest.example.csv) documenta os
campos `product_id,image,label,piece_id,session_id,split`; `source_image` é
opcional para aumentos. Caminhos relativos são resolvidos a partir do manifesto.
O validador rejeita campos vazios, splits/rótulos inválidos, imagens ilegíveis,
peças ou sessões em splits diferentes e imagens duplicadas por SHA-256.

```powershell
uv run i8-prepare-dataset dataset/manifest.csv
uv run i8-build-normal --product produto_001 --images data/produto_001/train/normal --output models
uv run i8-train-classifier --manifest dataset/manifest.csv --taxonomy ..\a1\shared\artifacts\defect-taxonomy\defects-a1-1.0.0\content.json --taxonomy-descriptor ..\a1\shared\artifacts\defect-taxonomy\defects-a1-1.0.0\descriptor.json --taxonomy-version defects-a1-1.0.0 --product produto_001 --output models/classifier.json
uv run i8-calibrate --input calibration.jsonl --manifest dataset/manifest.csv --output models/policy.json --product produto_001 --normal-version normal-1.0.0 --classifier-version classifier-1.0.0 --taxonomy-version defects-a1-1.0.0
uv run i8-infer --image data/produto_001/test.jpg --normal-model models/normal_produto_001_normal-1.0.0.json --classifier models/classifier.json --policy models/policy.json --taxonomy ..\a1\shared\artifacts\defect-taxonomy\defects-a1-1.0.0\content.json --taxonomy-descriptor ..\a1\shared\artifacts\defect-taxonomy\defects-a1-1.0.0\descriptor.json --taxonomy-version defects-a1-1.0.0
uv run i8-replay --input replay.jsonl --output events.jsonl --normal-model models/normal.json --classifier models/classifier.json --policy models/policy.json --taxonomy taxonomy.json --taxonomy-descriptor descriptor.json --taxonomy-version defects-a1-1.0.0 --artifact-version composition-1.0.0
uv run i8-evaluate test-predictions.jsonl --output reports/evaluation.json
uv run i8-benchmark --image data/produto_001/test.jpg --repeat 10 --output reports/benchmark.json --normal-model models/normal.json --classifier models/classifier.json --policy models/policy.json --taxonomy taxonomy.json --taxonomy-descriptor descriptor.json --taxonomy-version defects-a1-1.0.0
uv run python -m pytest -q
```

O modo normal-only de `i8-infer` exige a opção explícita `--normal-only` e não
classifica defeitos conhecidos. O modo completo exige classificador e política.
Artefatos ausentes ou incompatíveis são erros, nunca defaults silenciosos.

## Modelo, política e contrato

O modelo normal usa exclusivamente amostras `CONFORMING` do split `train`. O
classificador é uma regressão softmax linear determinística sobre embeddings
ResNet18, treinada por gradiente descendente com semente e persistida com produto,
classes, ordem, dimensão, pesos e versão do pré-processamento. O softmax é apenas
confiança operacional do classificador conhecido; não prova ausência de anomalia
desconhecida.

A política é versionada e calibrada exclusivamente no split `calibration`. A
precedência é:

1. classe conhecida acima de `known_confidence` e fora da região normal:
   `NON_CONFORMING`;
2. similaridade acima de `conforming_similarity` com margem inclusiva:
   `CONFORMING`;
3. similaridade abaixo de `anomaly_similarity` com margem inclusiva:
   `ANOMALY`;
4. demais casos: `UNCERTAIN`.

`uncertain_margin` cria uma faixa de segurança junto aos limites; as fronteiras
sem margem são inclusivas nos limites configurados. `ANOMALY` é desvio detectado,
enquanto `UNCERTAIN` é abstenção por evidência ambígua.

O contrato final Kafka é `ods.industria.defeito_classificado`, versão `2.0`, com
`occurred_at` obrigatório indicando a conclusão da análise. A candidata `1.1` foi
substituída antes da ativação. Durante a estratégia expand, o builder mantém por
padrão o legado `ods.i8.piece_analysis`/`1.0`; a versão `2.0` deve ser solicitada
explicitamente. Pares cruzados e a candidata substituída são recusados. Consulte
[contrato e migração](docs/contratos/kafka-i8-2.0.md). O transporte Kafka 2.0 está
implementado no [publisher e replay opcional](docs/kafka-publisher.md); a ativação
no barramento compartilhado permanece pendente. A construção
e validação reutilizam `build_piece_analysis` e `validate_piece_analysis`.
`taxonomy_version` e `artifact_version` identificam os artefatos efetivos;
`defect_class` só é publicado em `NON_CONFORMING`. Mídia, evidência S4 e decisões
de negócio A1 não entram no evento.

## Runtime, replay e benchmark

[`src/runtime.py`](src/runtime.py) correlaciona por `source_id`, `session_id` e
`frame_index`. A bbox é `[x_min,y_min,x_max,y_max]`. Há limite de quantidade,
TTL configurável usando relógio local de chegada e distinção de expiração nas
estatísticas. O limite de quantidade não é limite fixo em bytes. O replay executa
inferência real, fecha os recortes temporários e escreve eventos 6c validados.

O benchmark separa aquecimento, pré-processamento, extração, decisão e montagem/
validação do evento; exporta média, p50, p95, hardware, dispositivo, artefatos e
memória medida por `tracemalloc`. A medição é local e não comprova SLA ponta a
ponta.

## Estado Sprint 3

- S3-01/S3-02: implementado — contrato 6c e taxonomia A1 versionada com hash.
- S3-04: extrator e transformação compartilhados na inferência e similaridade;
  validação de vetores, regressão Docker e medição CPU disponíveis para revisão
  na branch `feat/s3-04-extrator-unico`. Referências antigas devem ser regeneradas;
  o score já usado pelo modelo normal foi preservado.
- S3-05: implementado no fluxo local; avaliação industrial permanece pendente
  até haver dataset real separado por peça/sessão.
- S3-06: implementado no replay local; integração externa P2/P4/P6/B1 permanece
  pendente por ausência de contratos/bibliotecas operacionais.
- S3-12: ferramentas e testes implementados; hardware-alvo e dados reais ainda
  são necessários para evidência de desempenho e qualidade.

Validação histórica do fluxo de inferência: `84 passed`, wheel construído e imports verificados em ambiente
temporário fora do repositório. A validação do novo publisher está nas
[evidências da atividade 06](docs/evidencias/publicacao-kafka-i8/README.md); ela não reexecuta a suíte completa com Torch.
Não são escopo backend A1, banco, revisão humana,
relatórios de negócio, S4, S5 ou P7.
