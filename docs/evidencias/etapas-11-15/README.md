# Etapas 11–15 — auditoria local e roteiro reproduzível

Base: `52301258ee27ed8b25ba9bc17a497630880398a9`, branch `fix/sprint3-etapas-11-15`. Este incremento **não conclui as etapas 11–15**: faltam dados essenciais. Não houve treino, calibração, nova avaliação real ou publicação Kafka.

## O que realmente existe

O inventário percorreu todo o repositório, inclusive arquivos ignorados e caches, excluindo somente `.git`. Foram encontradas **zero imagens e zero manifestos CSV reais**. Há modelos e relatórios históricos, mas não as 369 imagens declaradas, nem previsões de calibração/teste que permitam reproduzir seus números. O template CSV novo contém somente o cabeçalho e não representa amostras.

`reports/replay-input-csv-001.jsonl` referencia quatro imagens em `D:\ver-1\dataset\organized\test`; nenhuma existe neste ambiente. Os quatro eventos de saída são NON_CONFORMING no contrato legado 1.0. O relatório de avaliação declara 74 amostras, mas suporte zero para ANOMALY. Não inferimos rótulos a partir dos pesos nem transformamos mocks em dados reais.

- [Inventário local com hashes e situação Git](inventario-local.json).
- [Pacote de demonstração bloqueado](demonstracao-bloqueada.json).

A ausência se refere ao escopo local auditado, não prova que João não tenha dados em outra máquina. Para prosseguir, o responsável pelos dados deve fornecer localização acessível, manifesto, licença/origem, identidade de peça/sessão e rótulos, incluindo anomalias desconhecidas.

## Correções disponíveis

- `prepare_dataset` agora verifica decodificação das imagens, quantidade alegada, hashes, peça/sessão, duplicação e origem de aumentos independentemente da ordem das linhas; permite ANOMALY somente fora do treino conhecido.
- Treino normal aceita `--manifest` e usa exclusivamente CONFORMING/train/produto. Classificador valida o manifesto antes de extrair vetores.
- Previsões ficam vinculadas a imagem, manifesto e hashes/versões dos artefatos. Produto diferente do modelo não é misturado. ANOMALY mantém referência desconhecida sem classe de defeito conhecido.
- Calibração exige previsões completas de calibration e gera justificativa, hashes e limitações. Confiança conhecida 0,8 e margem 0,05 continuam parâmetros fixos explícitos. Sem anomalias rotuladas, a fronteira de anomalia é uma heurística, não calibração desconhecida homologada.
- Avaliação com `--manifest` verifica verdade de referência e split test; métricas por classe e ANOMALY continuam separadas. O modo histórico sem manifesto fica marcado como não reproduzível.
- `package_demo` exige dados rastreáveis e declaração humana da origem. Um falso positivo ANOMALY em defeito conhecido não conta como anomalia desconhecida demonstrada. Pacote incompleto ou sintético retorna código diferente de zero e não encerra a etapa 15.

## Comandos exatos após receber os dados

Execute na raiz do I8. O dataset deve estar em `dataset/real/manifest.csv`, com caminhos relativos ao manifesto; nenhum arquivo real é criado por este roteiro. Use `dataset/manifest.example.csv` apenas como estrutura. Se houver exatamente as 369 imagens da entrega anterior, confirme a alegação com `--expected-count 369`; se o conjunto mudou, documente a nova quantidade, sem completar artificialmente linhas.

Os comandos abaixo geram **novos** artefatos em `reports/repro-001/`; não sobrescrevem os históricos de `models/`. Registre o commit I8/A1, versão Python, dependências, versão Torch/torchvision, dispositivo e hashes dos pesos oficiais usados. Os pesos devem estar acessíveis; ausência de Torch/pesos/dados é bloqueio, não motivo para substituir inferência por um mock.

```bash
uv sync --extra dev
mkdir -p reports/repro-001/artefatos
uv run python -m scripts.prepare_dataset dataset/real/manifest.csv --expected-count 369 --inventory reports/repro-001/inventario.json
uv run python -m scripts.build_normal_model --product caixa_papelao --manifest dataset/real/manifest.csv --output reports/repro-001/artefatos --model-version normal-repro-001 --device cpu
uv run python -m scripts.train_classifier --manifest dataset/real/manifest.csv --taxonomy ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/content.json --taxonomy-descriptor ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/descriptor.json --taxonomy-version defects-a1-1.0.0 --product caixa_papelao --artifact-version classifier-repro-001 --seed 0 --output reports/repro-001/artefatos/classifier.json
uv run python -m scripts.predict_manifest --manifest dataset/real/manifest.csv --split calibration --normal-model reports/repro-001/artefatos/normal_caixa_papelao_normal-repro-001.json --classifier reports/repro-001/artefatos/classifier.json --taxonomy ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/content.json --taxonomy-descriptor ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/descriptor.json --taxonomy-version defects-a1-1.0.0 --device cpu --output reports/repro-001/calibration.jsonl
uv run python -m scripts.calibrate_policy --input reports/repro-001/calibration.jsonl --manifest dataset/real/manifest.csv --product caixa_papelao --normal-version normal-repro-001 --classifier-version classifier-repro-001 --taxonomy-version defects-a1-1.0.0 --policy-version policy-repro-001 --known-confidence 0.8 --uncertain-margin 0.05 --output reports/repro-001/artefatos/policy.json
uv run python -m scripts.predict_manifest --manifest dataset/real/manifest.csv --split test --normal-model reports/repro-001/artefatos/normal_caixa_papelao_normal-repro-001.json --classifier reports/repro-001/artefatos/classifier.json --policy reports/repro-001/artefatos/policy.json --taxonomy ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/content.json --taxonomy-descriptor ../a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0/descriptor.json --taxonomy-version defects-a1-1.0.0 --device cpu --output reports/repro-001/test.jsonl
uv run python -m scripts.evaluate reports/repro-001/test.jsonl --manifest dataset/real/manifest.csv --output reports/repro-001/evaluation.json
```

Antes de gerar a demonstração, preencha `dataset/real/proveniencia.json` a partir do exemplo: `natureza=real_declarada`, origem/licença/responsável reais e o SHA-256 exato do manifesto. Essa declaração é um aceite humano, não prova automática produzida pelo programa. Não use a opção `real_declarada` para imagens geradas nos testes.

```bash
uv run python -m scripts.package_demo --manifest dataset/real/manifest.csv --predictions reports/repro-001/test.jsonl --provenance dataset/real/proveniencia.json --output reports/repro-001/demonstracao.json
```

Se faltar qualquer resultado, o pacote lista os ausentes e fica BLOQUEADA. ANOMALY precisa de exemplo desconhecido rotulado corretamente; UNCERTAIN é abstenção do modelo e não uma classe rotulada. O operador deve revisar imagens e diagnósticos antes do aceite. Este pacote é uma demonstração de inferência em arquivos; não comprova entrega ao A1, Kafka, P2 ou hardware.

## Reproduzir o inventário e testar validações

```bash
python -m scripts.inventory_local_data --output docs/evidencias/etapas-11-15/inventario-local.json
python -m pytest -q tests/test_experiment_provenance.py tests/test_contracts_6c.py tests/test_kafka_contract_1_1_candidate.py tests/test_kafka_contract_2_0.py
```

Os testes de validação usam imagens sintéticas temporárias explicitamente identificadas. Eles não contam como dados reais nem como demonstração industrial dos quatro resultados. Os modelos, política e métricas históricos permanecem intactos.

Resultado local deste incremento: **22 testes novos aprovados**; seleção de regressão offline com contratos, publisher e replay: **161 aprovados**. Não somar os números: os 22 estão incluídos nos 161. Um aviso de depreciação pytest-asyncio apareceu sem falha. A suíte de inferência completa não foi executada porque Torch não está instalado neste ambiente. Nenhuma execução de treino/avaliação real ou de Kafka/PostgreSQL foi alegada. O primeiro inventário e os testes com arquivos temporários precisaram de acesso fora das restrições do sandbox; nenhum teste foi modificado para contornar permissões.
