# Dependências de Ícaro — revisão de fechamento da Sprint 3

Consulta em 06/11/2026. Esta é uma fotografia dos repositórios, não homologação externa ou prova de disponibilidade em bancada.

| Dependência | Situação observada | Efeito no plano |
|---|---|---|
| A1 | PRs #9, #10 e #11 integrados; ingestão com limites, P7 fake e política candidata disponíveis | Reutilizar main. A candidata da atividade 16 permanece desativada |
| I8 | PR #8 integrado; PR #9 acrescentou auditoria e rastreabilidade das etapas 11–15 | Modelos históricos existem, mas as imagens/manifesto reais continuam ausentes no ambiente auditado |
| P2 | Biblioteca 0.2.0a3, contrato 1.1 e backend ONNX Runtime CPU publicados | Desbloqueia esta integração CPU da atividade 17; não comprova TensorRT |
| P4 | Captura, metadados, memória compartilhada, publicador Kafka e scripts de demonstração | Há base para entrada operacional; o adaptador I8 ainda precisa ser comprovado com os quadros reais |
| I1 | Contrato detections 1.0, pipeline, ingestão P4 e testes Docker publicados | Correlação disponível para integração; conferir modelo/detecções adequados à indústria |
| P6 | URL ods-26-2/p6 devolveu 404 e a busca acessível não encontrou repositório | Não foi possível verificar atualização; isso não prova inexistência do componente |
| S4 | Repositório usa master; captura, clipes, descritores, Kafka e demonstração de vídeo real implementados | Contrato/serviço permitem retomar atividades 19–20 com Samuel; acesso operacional ainda não foi testado por A1 |
| S5 | Serviço, contratos, agregações e consultas Kafka publicados | Atividade 23 pode avançar por contrato. Confirmar alimentação industrial: o serviço descreve entradas S1/S2, não I8/A1 diretamente |
| P7 | Mesmo driver pan-tilt; não há contrato de barramento implementado no driver | Atividade 24 integrada. Atividade 25 exige resolver ângulos/recusa/transporte com SIS-2 e dispor da bancada |
| B1 | Schemas publicados, incluindo S4/S5/P7; I8 do catálogo ainda usa piece_analysis | Não substituir o industrial 2.0 por esse legado; aceite/registro da versão industrial continua pendente |
| B2 | Repositório contém somente README de teste | Não há novo aceite/provisionamento verificável por esse repositório; manter guia Kafka e confirmação TRA-1/B2 |
| B5 | Pacotes publicados de EPI e placas; não foi localizado pacote I8 no inventário consultado | A exportação local deste incremento não equivale a publicar/homologar pacote no catálogo B5 |
| B6 | app-shell, overlay-player, alert-console e zone-editor com exemplos/testes | Samuel pode avaliar reutilização na atividade 27; não bloqueia esta prova P2 |

## Ordem prática

1. Revisar a integração I8/P2 CPU desta branch e suas provas Docker.
2. Obter com João localização dos dados, manifesto e proveniência para reproduzir 11–15; manter a política A1 candidata até aceite.
3. Completar entrada P4/I1 ou P6 e validar o pacote P2 aceito pela equipe para fechar 17.
4. Executar inferência real, Kafka, A1 e PostgreSQL para fechar 18. O teste de transporte sintético anterior não substitui esse passo.
5. Com Samuel, ligar S4/S5 por contratos nas atividades 19–23. Não inventar alimentação S5 a partir de eventos industriais incompatíveis.
6. Resolver o contrato físico P7 com SIS-2 antes da atividade 25; depois consolidar composição, regressão e medição 28–32.

Não foi acessado o broker compartilhado nem a VM Google Cloud nesta revisão.
