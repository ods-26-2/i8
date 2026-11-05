# Contrato industrial Kafka I8 -> A1 2.0

Decisao de implementacao VER-1: topico e schema `ods.industria.defeito_classificado`, `schema_version` **2.0**, produtor `I8`, tipo `event`. O nome segue o dominio funcional do Guia B2. A ativacao no barramento compartilhado e o aceite TRA-1 continuam pendentes; este PR nao implementa publisher Kafka nem comprova integracao real.

## Versoes e estrategia expand

| Interface | Identidade | Estado |
|---|---|---|
| Legado 1.0 | `ods.i8.piece_analysis` | Validador e builder preservados; default do builder durante expand |
| Candidata 1.1 | `ods.i8.piece_analysis` | Substituida antes de ativacao; runtime recusa; arquivos preservados como historico |
| Industrial 2.0 | `ods.industria.defeito_classificado` | Interface final deste incremento; ativacao explicita |

Renomear a identidade e acrescentar `occurred_at` obrigatorio rompe a interface 1.0. Por isso usamos major 2.0, sem modificar silenciosamente 1.0. Pares cruzados de nome/versao sao recusados. Os arquivos 1.1 sao historicos, nao uma terceira interface suportada.

## Horarios e identidade

- `captured_at`: captura original, preservada de P4/P6.
- `occurred_at`: conclusao real da analise I8; obrigatorio e explicitamente fornecido pelo chamador em 2.0.
- `published_at`: preparacao da primeira publicacao; nao e confirmacao do broker.
- Todos em UTC com milissegundos (`YYYY-MM-DDTHH:mm:ss.SSSZ`); datas impossiveis sao recusadas.
- Retry preserva evento completo, UUID, sequencia e horarios. Replay preserva captura e informa a analise do replay. Nao fabricar tempos para converter registros antigos.

Payload, quatro resultados, taxonomia, UUID v4, contexto fonte/sessao/quadro/deteccao, bbox com area positiva e scores finitos 0-1 permanecem. `defect_class` existe apenas em NON_CONFORMING e deve pertencer a taxonomia carregada. I8 nao publica midia nem decisao industrial do A1.

## Uso explicito do builder

`build_piece_analysis(..., schema_version="2.0", occurred_at="2026-11-05T13:00:00.080Z")` seleciona a identidade industrial. Os demais campos obrigatorios continuam sendo fornecidos pelo chamador. Sem `schema_version`, o builder continua em 1.0 para preservar os chamadores durante expand. `occurred_at` nao e aceito no legado estrito.

O topico de transporte deve ser igual ao `schema` do evento. O mapeamento executavel `SCHEMAS_BY_VERSION` publica as duas identidades; a biblioteca ainda nao envia eventos a Kafka. CLI/runtime existentes nao sao migrados automaticamente para 2.0 neste PR.

## Ordem de ativacao

1. Acordar nome/versao com TRA-1 e preparar o topico funcional.
2. Implantar A1 aceitando explicitamente legado 1.0 e industrial 2.0, com commit apos persistencia.
3. Ativar I8/publisher e fake em 2.0, uma publicacao por evento; nao publicar simultaneamente nos dois topicos.
4. Validar entrega, duplicacao, persistencia e recuperacao; depois retirar consumo legado quando nao houver produtores/mensagens restantes.

Eventos historicos 1.0 nao sao reescritos. O topico legado efetivamente utilizado deve ser configurado durante a transicao. A composicao, publisher I8 e teste real sao entregas separadas.

## Arquivos e testes

- Schema: `shared/schemas/6c/i8-defeito-classificado.2.0.schema.json`.
- Exemplos sinteticos: `shared/mocks/kafka-2.0/` (quatro validos, oito invalidos).
- Testes: `tests/test_contracts_6c.py`, `tests/test_kafka_contract_2_0.py` e regressao de rejeicao da candidata 1.1.
- Evidencias deste incremento: `docs/evidencias/contrato-kafka-2.0/README.md`.

Os resultados antigos 1.1 e a interoperabilidade publicada anteriormente sao historicos; nao comprovam interoperabilidade 2.0. S4/S5/P7 e dataset/calibracao nao mudam aqui.
