# Evidências — atividade 17, integração I8/P2 CPU

Base I8: `55a808b1351fdd94ea039148b49fba1f478603e1`. P2 fixado em `fddf028c025b4a9be22d3a67696a13c0c65b9b0e`, biblioteca 0.2.0a3. A fotografia completa das dependências está em `dependencias.json`.

## Prova Docker local

- Imagem Python 3.11, Torch 2.15.0+cpu, NumPy 1.26.4, P2/ONNX Runtime reais.
- Limites do container: 2 CPUs e 3 GiB; execução sem rede, container removido com `--rm`.
- Regressão: **216 aprovados e 2 Kafka ignorados**. Relatório completo: `regressao.xml`.
- Seleção P2: **21 aprovados**, incluídos nos 216. Cinco executam P2 real; os demais verificam o contrato/ciclo de vida com doubles explicitamente identificados.
- Exportação ResNet18 sem camada classificadora, com pesos oficiais IMAGENET1K_V1; pacote MODEL validado e engine preparado pelo próprio `p2-build --cpu-only`.
- Três imagens sintéticas não quadradas e não uniformes: diferença absoluta máxima dos embeddings aproximadamente **3,82 × 10⁻⁶**. Tolerâncias: `atol=5e-5`, `rtol=1e-4`. Valores por imagem e latência de `p2.infer`: `equivalencia.json`.
- Uma quarta imagem sintética atravessa recorte/correlação, pipeline com artefatos históricos, decisão equivalente à de Torch e construção de evento industrial 2.0 em transporte de memória.
- Falhas verificadas: metadados/I/O/manifesto/hash incompatíveis, entrada/saída inválidas, engine ausente, erro runtime, handle liberado e falha na inicialização do transporte.

A primeira regressão completa encontrou o defeito já presente na base: caminho Windows `C:/...` não era recusado como absoluto no Linux. A correção usa `PureWindowsPath.drive`, preserva o teste existente e acrescenta unidade relativa e UNC. A segunda regressão completa passou; não houve relaxamento do teste.

Dois avisos de depreciação do exportador ONNX legado apareceram sem falhas. A exportação usa explicitamente esse exportador/opset 17 para produzir o grafo verificado pelo P2. Uma mudança de exportador deve repetir a prova de equivalência.

## Limites da evidência

Imagens sintéticas não demonstram precisão industrial, nem os quatro resultados reais. A taxonomia do teste de pipeline é um double com as três classes históricas; não há novo aceite da taxonomia. As métricas de `p2.infer` cobrem aquela chamada CPU, não pré-processamento, Kafka/A1 ou SLA industrial; três amostras não constituem benchmark de desempenho final.

Não houve teste Jetson/TensorRT, ligação operacional P4/I1/P6, broker compartilhado ou A1/PostgreSQL. A exportação local não foi registrada no B5. As atividades 17 e 18 permanecem abertas até suas provas completas.

[Comandos Linux/Docker e arquitetura](../../sprints/atividade-17-runtime-p2.md).
