# Sprint 3 — Fechamento VER-1

## Etapas 11–15: reprodução pendente por ausência dos dados

Há modelos e métricas históricos, mas não imagens, manifesto real ou previsões de calibração/teste neste checkout. Consulte o [inventário e roteiro reproduzível](../evidencias/etapas-11-15/README.md). Não marcar as etapas concluídas com base em testes sintéticos ou no código das ferramentas.

Este índice organiza a documentação por assunto e pelo plano coletivo de fechamento da Sprint 3. A numeração das sprints em documentos anteriores é mantida como histórico; este índice não redefine o backlog nem cria novos IDs de atividade.

## Contrato Kafka I8/A1 — atividades 01–02

Escopo: tópico/schema final `ods.industria.defeito_classificado`, versão 2.0, captured_at/occurred_at/published_at, validação, fixtures e compatibilidade explícita com legado `ods.i8.piece_analysis`/1.0. A candidata 1.1 foi substituída antes da ativação; aceite externo TRA-1 e ativação no barramento compartilhado permanecem pendentes.

- [Contrato e decisões](../contratos/kafka-i8-2.0.md).
- [Evidências de contrato](../evidencias/contrato-kafka-2.0/README.md).
- PRs de revisão: [A1 #5](https://github.com/ods-26-2/a1/pull/5) e [I8 #5](https://github.com/ods-26-2/i8/pull/5).

## Ingestão Kafka A1 — atividades 03–05

Escopo: consumidor, confirmação após persistência/rejeição durável, retry, produtor fake, saúde, shutdown e contexto de testes Docker.

- [PR A1 #6](https://github.com/ods-26-2/a1/pull/6).
- [Evidências da ingestão](https://github.com/ods-26-2/a1/blob/fix/consumidor-kafka-confiavel/docs/evidencias/ingestao-kafka-a1/README.md).
- [Roteiro Linux e laboratório](https://github.com/ods-26-2/a1/blob/fix/consumidor-kafka-confiavel/validacao-local/README.md).

As evidências distinguem testes unitários com Kafka simulado de uma prova local com broker e banco reais. A prova usa eventos sintéticos; não comprova inferência industrial I8.

## Publicação e integração I8 — atividade 06 e provas 07–09/18

Comece pelo [resumo da atividade 06 e sua relação com a arquitetura](atividade-06-resumo.md).

O [publisher Kafka I8 e o replay opcional](../kafka-publisher.md) estão implementados na branch `feat/publisher-kafka-i8`, para revisão com João, responsável principal, e apoio de Ícaro no transporte. O caminho 2.0 valida antes do envio e exige confirmação de entrega. A prova local usa eventos sintéticos, não inferência real. Samuel participa das provas A1. A ativação compartilhada e o fluxo real I8 → A1 precisam de aceite próprio; este incremento não encerra as atividades 17–18.

## Outros escopos do fechamento

- [Unificação de extração e similaridade, S3-04](atividade-10-resumo.md): atividade 10 implementada em branch separada para revisão; extrator compartilhado, regressão e medição CPU disponíveis.
- Dataset, artefatos, calibração e avaliação: atividades 11–16.
- Entrada/runtime I8, S3-06, e fluxo real: atividades 17–18.
- Evidência S4, histórico, relatórios e métricas S5: atividades 19–23.
- Atuação P7, taxonomia e componentes B6: atividades 24–27.
- Composição S3-12, regressão, desempenho, evidências e consolidação: atividades 28–32.

Fonte de numeração: plano_fechamento_sprint3_dependencias.pdf fornecido pela equipe. Datas e aceites devem ser confirmados pelo grupo. Publicar uma branch ou um PR de rascunho não encerra uma atividade nem comprova uma dependência externa.
