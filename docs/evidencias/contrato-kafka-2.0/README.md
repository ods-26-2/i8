# Evidências locais — contrato industrial 2.0

Atualização do PR I8 #5, baseada em `61928e05ac2fc5f8daaaffe5e563832ded7eb7fd`, em 05/11/2026. Tópico/schema final `ods.industria.defeito_classificado`, versão `2.0`; `occurred_at` obrigatório. Suporte explícito ao legado `ods.i8.piece_analysis`/`1.0` preservado. Candidata 1.1 substituída e recusada pelo runtime; documentos, schemas e mocks antigos são históricos.

## Execução local

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest -q -p no:cacheprovider --basetemp=<diretorio-temporario-isolado> tests/test_contracts_6c.py tests/test_kafka_contract_1_1_candidate.py tests/test_kafka_contract_2_0.py --tb=short
```

Resultado: **110 testes aprovados**, um aviso de depreciação do plugin pytest-asyncio no Python 3.14. O primeiro ensaio no sandbox não pôde preparar diretórios temporários; a execução completa foi repetida fora dessa restrição, sem alterar os testes. `git diff --check` também passou.

Os novos testes exercitam quatro resultados nos validadores JSON Schema/runtime, oito exemplos negativos, pares cruzados de nome/versão, versão não publicada, builder 2.0 com três tempos preservados, horário obrigatório/inválido, rejeição da candidata e equivalência do default com legado explícito. Os testes legados verificam estrutura, taxonomia real com hash, classes e compatibilidade original.

## Limites

Estes resultados são locais, não GitHub Actions. Não foi executado Torch, inferência real, banco, Kafka, hardware ou comunicação com A1 2.0. A suíte de ML não foi executada porque Torch não está instalado neste ambiente. O script de interoperabilidade A1 publicado para a candidata 1.1 precisa ser atualizado junto com o A1 antes da prova conjunta 2.0.

O publisher Kafka I8 permanece pendente. CLI/runtime existentes continuam gerando o legado pelo default durante expand. Ativação 2.0 exige chamada explícita do builder e consumidor A1 compatível; ver [migração](../../contratos/kafka-i8-2.0.md).
