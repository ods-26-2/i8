# Sprint 3 — Atividade 10: extração e similaridade

O I8 agora reutiliza o mesmo extrator de características e a mesma preparação
da imagem na inferência e no motor de similaridade. O motor recebe a instância
existente; não carrega outra ResNet dentro do mesmo pipeline.

Isso evita comparar imagens preparadas de formas diferentes e carregar duas
redes para o mesmo trabalho. O I8 continua produzindo a análise; a decisão de
triagem da aplicação permanece no A1.

## Decisões que preservam a arquitetura

- O extrator oficial continua em `feature_extractor.FeatureExtractor`.
- Caminhos de arquivo e imagens em memória usam `preprocessing.transform_image`.
- O motor rejeita valores inválidos, vetores vazios/sem norma e dimensões incompatíveis.
- O import antigo `src.similarities_extractor` aponta para a mesma implementação.
- O helper antigo de aprovação/reprovação e o texto que tratava P7 como ejetor não foram incorporados.

O score usado pelo modelo normal na inferência continua com a fórmula e os
metadados existentes. Ele não foi trocado por cosseno, preservando o comportamento
das políticas atuais. O cosseno entre duas referências é uma operação separada,
identificada como `cosine-affine-v1`, agora no intervalo 0–1: iguais dão 1,
opostas dão 0 e ortogonais dão 0,5. Não misture esse score com os limiares do
modelo normal. Referências do motor antigo, que redimensionava diretamente para
224×224, devem ser extraídas novamente; seus resultados não são automaticamente
compatíveis com a transformação oficial.

## Provas e limites

A referência anterior passou em 148 testes; a nova versão passou em **171**,
incluindo validação de vetores, reaproveitamento do extrator, preservação do score
normal e instalação do wheel fora do repositório. Dois testes Kafka ficam
ignorados nessa suíte sem rede; a automação própria do publisher cobre o broker.

A medição local usou ResNet18 com pesos oficiais `IMAGENET1K_V1`, duas imagens
sintéticas, CPU x86_64 e duas threads. A mediana de extração ficou em cerca de
19 ms por imagem; o pico RSS do processo foi aproximadamente 406 MiB, incluindo
imports e carga dos pesos. Não são resultados de qualidade industrial, latência
do sistema inteiro ou desempenho na bancada final.

Consulte as [evidências e comandos Docker](../evidencias/s3-04/README.md).
O código segue em branch separada para revisão com João. A integração do novo
publisher com A1 e as atividades 17–18 permanecem como provas distintas.
