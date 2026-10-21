# Migração 6c — S3-01 e S3-02

O I8 publica `ods.i8.piece_analysis` como evento EV-SINAL estrito na versão
`1.0`. O módulo `src.contracts` constrói e valida o envelope e o payload sem
executar inferência. Os quatro resultados são `CONFORMING`, `NON_CONFORMING`,
`ANOMALY` e `UNCERTAIN`; `defect_class` existe somente em `NON_CONFORMING`.

`artifact_version` identifica o modelo/engine usado. `taxonomy_version`
identifica, separadamente, o `DEFECT_TAXONOMY` carregado. O evento não contém
mídia, consequência de triagem, nome, descrição ou severidade. Evidência é
solicitada pelo A1 ao S4 em outro fluxo.

O módulo `src.taxonomy` carrega arquivos locais exportados pelo A1/B5, exige a
versão configurada, verifica os oito campos do descritor e o SHA-256 dos bytes
do conteúdo, recusa IDs duplicados e mantém a resolução por versão histórica.
Ele não baixa conteúdo da URI e não publica nada no registro B5.

A função antiga `aplicar_triagem_limiar_duplo` permanece somente como legado e
não alimenta o novo publicador. A política de negócio e a revisão pertencem ao
A1/S3-08; P7 é pan-tilt e não deve ser tratado como ejetor.

Os contratos ainda não comprovam publicação em broker, registro externo B5,
entrada P4/I1/P2 nem integração S4/S5/P7. Esses limites não foram simulados como
produção.

## Verificação

```powershell
python -m pip install -r requirements-contracts.txt
python -m pytest -q tests/test_contracts_6c.py
```
