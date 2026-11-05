# Sprint 3 — Publicação Kafka I8, atividade 06

O I8 pode publicar eventos industriais 2.0 e confirmar sua entrega ao broker.
O fluxo reutiliza `EventPublisher` e o validador de contrato/taxonomia existente.
O adaptador Kafka não importa Torch. A implementação segue para revisão pela
branch `feat/publisher-kafka-i8`; a homologação externa e a ativação compartilhada não
são comprovadas por este laboratório.

Para uma leitura inicial sem comandos, consulte o
[resumo da atividade 06 e da arquitetura](sprints/atividade-06-resumo.md).

## Comportamento

- `src/kafka_transport.py` usa `confluent-kafka`, recomendado pelo guia B2.
- Tópico e schema são `ods.industria.defeito_classificado`, versão `2.0`.
- O transporte recusa legado 1.0, candidata 1.1 e identidades incompatíveis.
- O broker vem de `KAFKA_BROKER_URL`, obrigatório; não há endereço de nuvem fixo.
- `KAFKA_TOPIC` pode ser informado, mas deve coincidir com a identidade industrial.
- `KAFKA_DELIVERY_TIMEOUT` limita cada espera de entrega/encerramento em segundos,
  entre 1 e 300, com padrão 10. Um envio seguido de encerramento pode esperar até
  duas vezes esse limite.
- O produtor usa idempotência, `acks=all` e chave `session_id`. Ele não cria tópicos.
- Só há sucesso após callback de entrega sem erro. Enfileirar a mensagem ou
  esvaziar a fila sem callback não comprova entrega.
- O recibo registra `message_id`, tópico, partição e offset. Ele comprova aceite
  pelo broker, não persistência ou processamento posterior no A1.
- O cliente trata retries internos dentro do prazo de entrega. Uma falha interrompe
  o processamento: eventos seguintes não ultrapassam uma entrega incerta.
- `close()` executa flush com prazo. Os comandos usam gerenciador de contexto
  para finalizar o cliente também em caso de erro.

A publicação é síncrona, com um evento pendente por chamador. Isso simplifica a
confirmação e a ordem neste incremento, mas não comprova vazão industrial. O
adaptador não é compartilhável entre threads. Idempotência do cliente não elimina
duplicatas de reenvios explícitos ou reinicializações; o A1 continua deduplicando
por identidade. Uma única réplica no laboratório não prova tolerância a perda de
broker, mesmo com `acks=all`.

## Publicar eventos existentes sem modelos

Na raiz I8, em um ambiente Python dedicado:

```bash
python -m pip install -r requirements-kafka.txt
export KAFKA_BROKER_URL="host-do-broker:porta"
export KAFKA_TOPIC="ods.industria.defeito_classificado"
export KAFKA_DELIVERY_TIMEOUT=10
python -m scripts.publish_events --input events.jsonl \
  --taxonomy ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/content.json \
  --taxonomy-descriptor ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/descriptor.json \
  --taxonomy-version defects-a1-1.0.0
```

O arquivo contém um evento completo por linha. O comando não fabrica horários,
IDs ou resultados e não executa inferência. Ele carrega a taxonomia real, verifica
seu hash e valida cada evento antes do envio. A primeira falha interrompe o arquivo
e resulta em código diferente de zero. Linhas anteriores podem ter sido entregues;
seu recibo é escrito no stdout imediatamente após confirmação.

Na instalação completa com uv, use `uv sync --extra dev --extra kafka`; o comando
instalável equivalente é `uv run --extra kafka i8-publish-events` com os mesmos argumentos.
Essa instalação completa inclui as dependências de inferência, ao contrário do
comando leve de `pip` acima.

## Publicar o resultado do replay

O comando de inferência/replay existente recebe a opção `--kafka`:

```bash
uv run --extra kafka i8-replay --input replay.jsonl --output events-kafka.jsonl \
  --normal-model models/normal.json --classifier models/classifier.json \
  --policy models/policy.json \
  --taxonomy ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/content.json \
  --taxonomy-descriptor ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/descriptor.json \
  --taxonomy-version defects-a1-1.0.0 --artifact-version composition-1.0.0 --kafka
```

Esse caminho usa os artefatos e a inferência real já existentes, sem inventar
scores. Após cada inferência, ele registra `occurred_at` pelo relógio UTC local,
registra `published_at` na montagem e preserva `captured_at` do quadro. O formato
dos três campos é UTC com milissegundos. O replay atribui sequência crescente a
cada sessão dentro da execução, iniciada em zero. A sessão deve ser processada
por um único produtor; a sequência não é persistida entre execuções. Runtime
contínuo e reinício coordenado de sessões pertencem ao fechamento S3-06.

Antes de enviar, o replay grava e descarrega o evento no arquivo de saída. Em
modo Kafka, esse arquivo deve ser novo: um arquivo existente não é sobrescrito.
Em falha de entrega, use `publish_events` sobre o JSONL preservado para reenviar
os mesmos eventos. Não refaça a inferência para tentar recuperar uma publicação:
isso criaria novos IDs e novos horários. Reenviar o arquivo inteiro pode repetir
eventos já confirmados; o A1 precisa deduplicá-los.

O JSONL é uma ajuda local de recuperação, não uma outbox transacional: não há
garantia contra queda física entre inferência, escrita e entrega. Sem `--kafka`,
o replay continua offline, construindo legado 1.0 como antes. O builder global
também mantém seu padrão 1.0; não houve migração silenciosa de outros chamadores.

## Testar no Linux com Docker

Os repositórios A1 e I8 devem estar lado a lado, com a taxonomia A1 disponível.
Este laboratório é o protótipo isolado da equipe: não acessa o broker da turma,
não publica portas Kafka e não deve permanecer ativo durante testes compartilhados.

Na raiz I8:

```bash
docker build -f validacao-local/Dockerfile.publisher -t ver1-i8-publisher:test .
docker run --rm ver1-i8-publisher:test
mkdir -p validacao-local/evidencias
export VER1_UID="$(id -u)" VER1_GID="$(id -g)"
docker compose -p ver1-i8-publisher -f validacao-local/compose.publisher.yml run --rm --build publisher-tests
docker compose -p ver1-i8-publisher -f validacao-local/compose.publisher.yml down -v
```

Crie a pasta de evidências antes do Compose para que o relatório tenha permissão
de escrita com seu usuário Linux. O relatório gerado é
`validacao-local/evidencias/publisher-kafka.json`, fora do versionamento.

O primeiro comando de testes cobre contrato legado/2.0, rejeição da candidata,
entrega, falha, timeout, fila cheia, validação antes do envio, preservação de
identidade, encerramento e replay com inferência explicitamente substituída por
double. Ele não instala Torch ou baixa pesos. A prova do Compose usa Kafka real,
taxonomia A1 real e quatro resultados sintéticos pela CLI de produção. Ela
republica um evento com o mesmo ID, lê os cinco registros e confere conteúdo,
chave, partição e offsets. Também verifica falha contra um broker indisponível.

Isso não é uma prova de inferência real, P2, persistência A1, hardware, múltiplas
partições, desempenho ou Google Cloud. A validação de modelos e do fluxo real
completo permanece nas atividades 17–18. O prazo de entrega é configurável, não
uma evidência de SLA.

## Referências

A [automação no GitHub Actions](../.github/workflows/testes-publisher.yml) executa
a mesma seleção em Docker, separando contratos/publisher/replay dos dois testes
com broker real. A taxonomia A1 é obtida do commit fixo
`f4141bb43a2d13127cf2dcc380d991322be7ad35`, mantendo os repositórios lado a lado.
Os relatórios XML, logs, ambiente e JSON da prova ficam no pacote
`evidencias-publisher-i8`, retido por 30 dias. Os testes locais continuam disponíveis.

- [Evidências locais e limites](evidencias/publicacao-kafka-i8/README.md).
- [Contrato industrial 2.0](contratos/kafka-i8-2.0.md).
- [Cliente Python oficial: callbacks e flush](https://docs.confluent.io/kafka-clients/python/current/index.html).
- [Configuração librdkafka: idempotência e prazos](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md).
