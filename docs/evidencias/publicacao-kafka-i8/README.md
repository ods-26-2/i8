# Sprint 3 — Evidências da publicação Kafka I8

Data: 05/11/2026. Base I8: `66ee06599182aa78eedf9d58bc4041db54ecc4fd`.
Branch local: `feat/publisher-kafka-i8`; execução sobre alterações locais ainda
sem commit. Não foi executado GitHub Actions para este incremento.

## Resultado final

**141 testes aprovados**, sem testes ignorados nesta seleção:

- 110 de contratos, legado 1.0, industrial 2.0 e rejeição da candidata 1.1;
- 24 de configuração, entrega, falha, retry com mesma identidade e CLI;
- 5 de replay, horários, arquivo de recuperação e imports sem Torch;
- 2 com cliente Kafka real: publicação/consumo e broker indisponível.

A [saída dos testes](RESULTADOS.txt) identifica o comando completo. O
[relatório da prova](publisher-kafka.json) registra cinco publicações, quatro
eventos distintos e cinco recibos de entrega. O mesmo evento é reenviado sem
alterar ID, sequência, horários ou payload; a segunda entrega ocupa outro offset.
Isso demonstra por que o A1 ainda precisa deduplicar reenvios explícitos.

O laboratório usa Kafka 3.9.1, uma partição, uma réplica, Python 3.11 e taxonomia
A1 carregada com validação de hash. Os quatro resultados publicados são
sintéticos. A CLI `scripts.publish_events` é a mesma disponível para uso normal.
O teste do replay usa uma função de inferência substituta explícita; não baixa
pesos e não apresenta seus resultados como inferência industrial real.

## Falha encontrada e correção

A primeira prova enviou e leu os eventos, mas falhou ao gravar o JSON do relatório:
o Compose havia criado a pasta de evidências com outro proprietário. A pasta
vazia foi recriada com o usuário Linux. A repetição passou nos dois testes de
integração, e a seleção final completa passou nos 141 testes. O roteiro agora
orienta criar a pasta e exportar UID/GID antes de executar o Compose.

## Encerramento e limites

O projeto Docker `ver1-i8-publisher` foi encerrado com `down -v`; broker, serviço
de criação do tópico e rede foram removidos. Não houve acesso ao Kafka Google
Cloud nem criação de tópico no barramento compartilhado.

Esta prova não executa modelo real, P2, hardware, persistência A1, múltiplas
partições ou medição de desempenho. Não substitui homologação TRA-1/B2 e não
encerra as atividades 17–18. A suíte completa de inferência com Torch não foi
executada neste incremento.

Consulte o [roteiro Linux e comportamento de retry](../../kafka-publisher.md).
