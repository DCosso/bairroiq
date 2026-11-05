# BairroIQ — Contrato de consumo frontend v1 (seis colunas)

## Estado

**Exploratório, interno e somente leitura.** Este PR ajusta o contrato visual de 8 para 6 colunas após validação da versão física do Star Schema v1. Nenhuma escrita, criação de tabela, concessão de acesso ou publicação é realizada por `frontend_v1_runner.py`. A homologação editorial é responsabilidade do grupo.

## Fonte, grão e snapshot

- Uma linha por **distrito administrativo oficial do IBGE** (`CD_DIST`), nunca bairro imobiliário; 96 linhas previstas.
- Snapshot imutável: `v3.0.0-candidato|726091fefefa868fd5d0d2c6929b1d68c4849941f4c7510b4fee0d93a075d38b`.
- Fonte de consumo: exclusivamente sete tabelas físicas `workspace.gold.bairroiq_*`, validadas com `star_schema_v1_delta_runner.check(spark)`.
- O preflight lê e verifica a Gold original por hash; **não** extrai outra métrica live da Gold.
- Sem histórico temporal implícito: diferentes fontes e janelas; `snapshot_id` não equivale a uma data dos dados.

## Seis colunas visuais — ordem obrigatória

| Coluna | Fonte / cálculo | Escala e limitação |
|---|---|---|
| **Distrito** | `dim_distrito.NM_DIST` | Nome oficial de distrito do IBGE |
| **Empregos** | `percent_rank` do indicador de empregos formais entre os 96 distritos | Índice comparativo 0–100; dados de 2021, não vagas abertas |
| **Roubos** | Taxa SSP de roubos (art. 157) por 100 mil habitantes ÷ 100 | Registros por 1.000 habitantes; não prevê risco individual |
| **Segurança** | `100 - indice_ordenacao_ocorrencias` | Proxy relativa de roubos e furtos; não mede segurança geral |
| **Mobilidade** | Média dos percentis de metrô/ônibus/trem por 10 mil habitantes | Índice relativo 0–100; não mede tempo de viagem |
| **Cluster** | P01–P09 + nome exploratório do K-Means v3 | Grupo estatístico provisório, não ranking residencial |

**Retiradas da tabela principal:**
- Arborização: 96/96 valores sem indicador próprio validado. Não preencher com praça ou corredor verde.
- Iluminação LED: indicador existente e auditado na Gold (Delta versão 259, auditado em 05/11/2026), mas quase não diferencia os distritos (58/96 exatamente 100%, média 99,8653%). Permanece na Gold para eventual detalhe, fora do contrato v1.

Por isso o frontend v1 não depende mais de buscar a porcentagem LED na Gold atual. A auditoria técnica da versão 259 permanece válida, mas **não** é usada para congelar um campo de LED no consumidor de seis colunas.

## Campos técnicos — 13, ordem obrigatória

`snapshot_id`, `cd_dist`, `distrito`, `latitude`, `longitude`, `perfil_id`, `cluster`, `empregos`, `roubos`, `seguranca`, `mobilidade`, `tipo_territorio`, `publicacao_autorizada`.

- `publicacao_autorizada=False` e `tipo_territorio='DISTRITO_IBGE'`.
- Faixas 0–100 para emprego, segurança relativa e mobilidade; `roubos` é taxa com outra unidade.
- Perfil P04 permanece **provisório**; os três distritos de fronteira continuam na classificação original.
- As permissões do Unity Catalog serão revistas durante a homologação coletiva, antes da apresentação final, conforme decisão do grupo.

## Aceite

- Exatamente 96 distritos distintos, 9 clusters e 6 campos visuais, sem nulidade das métricas obrigatórias.
- Valores são produzidos apenas do snapshot Star Schema v1, sem recalcular classificação ML.
- Nenhuma escrita ou autorização de publicação neste contrato.
- Materializador físico `workspace.gold.bairroiq_frontend_v1` será implementado em PR independente, com check prévio e execução de escrita explicitamente confirmada.
