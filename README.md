# BairroIQ — Inteligência Geográfica para Moradia e Negócios

> Projeto de Engenharia de Dados e DataOps para integrar informações urbanas de São Paulo e, futuramente, permitir comparações transparentes entre regiões.

## Sobre o projeto

O **BairroIQ** busca transformar dados dispersos sobre moradia, segurança, infraestrutura e condições socioeconômicas em informações úteis para decidir onde morar ou trabalhar na cidade de São Paulo.

A proposta do produto é apresentar indicadores comparáveis, um ranking explicável e perfis urbanos identificados por técnicas de clusterização. **O ranking, a clusterização e a aplicação web ainda não estão implementados.** A etapa atual é a construção e a validação das bases de dados.

### Problema de negócio

A escolha de uma região envolve custo de moradia, segurança, mobilidade, equipamentos urbanos, serviços e oportunidades. As informações vêm de fontes distintas, com metodologias, períodos e granularidades territoriais diferentes. Compará-las diretamente, sem tratamento, pode gerar conclusões enganosas.

**Pergunta orientadora:** qual região de São Paulo atende melhor a diferentes prioridades de moradia ou trabalho, considerando critérios, restrições e qualidade dos dados?

### Pilares de análise

| Pilar | Objetivo |
| --- | --- |
| Custo de vida | Referências de preços de moradia e custos disponíveis. |
| Segurança | Indicadores públicos de ocorrências criminais. |
| Mobilidade | Transporte público e conectividade urbana. |
| Infraestrutura | Equipamentos públicos, saúde, educação, cultura e espaços urbanos. |
| Empregos e serviços | Atividades econômicas, estabelecimentos e indicadores socioeconômicos. |

### Escopo geográfico

O recorte inicial é o município de **São Paulo**, priorizando seus **96 distritos oficiais** para análises territoriais compatíveis. Uma ressalva fundamental: **bairro imobiliário não é necessariamente distrito administrativo**. A base de imóveis permanece na granularidade original até existir um mapeamento territorial auditável.

### Produto planejado

Uma aplicação web para consultar indicadores, comparar regiões, visualizar mapas, explorar rankings e consultar fontes e limitações metodológicas. Essas funcionalidades pertencem às próximas etapas do projeto.

---

## Status do projeto

| Componente | Situação | Evidência / observação |
| --- | --- | --- |
| Infraestrutura e catálogo | Implementados | Schemas `bronze`, `silver`, `gold`, `observability` e Volume no Unity Catalog. |
| Bronze | Implementada | Cinco fontes com tabelas Delta populadas. |
| Silver — IBGE | Publicada e validada | Indicadores censitários por distrito. |
| Silver — SSP-SP | Publicada e validada | Associação espacial das ocorrências aos distritos. |
| Silver — GeoSampa | Publicada e validada | Equipamentos urbanos por distrito. |
| Silver — ObservaSampa | Publicada e validada | Indicadores municipais com ano preservado. |
| Silver — Imóveis | Publicada e validada | Preços mensais por bairro de origem e transação. |
| CI/CD | Implementado | Testes, validação de Bundles e deploy automatizado de Jobs. |
| Gold | **Pendente** | Schema existente; indicadores consolidados e ranking não publicados. |
| Interface web | **Pendente** | Produto interativo ainda não desenvolvido. |

**Marco recente:** a [Silver Imóveis v1 foi integrada no PR #29](https://github.com/DCosso/bairroiq/pull/29), com 33 testes unitários, validação real no Databricks e publicação manual verificada. O [CD pós-merge](https://github.com/DCosso/bairroiq/actions/runs/41746876808) foi concluído com sucesso.

---

## Arquitetura de dados

O BairroIQ adota a arquitetura **Medallion** em Delta Lake:

| Camada | Responsabilidade | Situação |
| --- | --- | --- |
| **Bronze** | Preservar as informações das fontes e suas estruturas de origem. | Cinco tabelas Delta populadas. |
| **Silver** | Validar, tipar, padronizar e enriquecer informações, respeitando o grão e a temporalidade de cada fonte. | Cinco conjuntos temáticos publicados, com validações específicas. |
| **Gold** | Consolidar métricas comparáveis e disponibilizá-las ao produto. | A desenvolver. |

A observabilidade funciona como uma área independente, registrando evidências de qualidade e execução.

### Unity Catalog

O catálogo utilizado é `workspace`, com os schemas:

- `workspace.bronze`
- `workspace.silver`
- `workspace.gold`
- `workspace.observability`

Arquivos de origem são armazenados no Volume gerenciado:

```text
/Volumes/workspace/bronze/raw/
```

### Princípios de modelagem

- **Grão explícito:** manter a chave e a granularidade de cada fonte antes de agregações.
- **Temporalidade preservada:** não atribuir a um ano valores observados em outro.
- **Dados ausentes explícitos:** valores `NULL` não são convertidos automaticamente em zero.
- **Geografia comprovada:** usar códigos oficiais ou correspondência espacial validada, não aproximações por nomes.
- **Reprodutibilidade:** código e testes versionados; validações que comparam a transformação com a tabela publicada.
- **Publicação controlada:** validações de leitura não alteram as tabelas Silver.

O desenho de futuras camadas analíticas poderá empregar Star Schema, Wide Tables e processamento incremental conforme as necessidades do produto.

---

## Tecnologias

| Tecnologia | Utilização |
| --- | --- |
| GitHub | Repositório, branches e Pull Requests. |
| GitHub Actions | Integração contínua, verificações e entrega contínua. |
| Terraform / HCP Terraform | Infraestrutura como código e gerenciamento remoto de estado. |
| Databricks Free / Serverless | Desenvolvimento e execução dos pipelines. |
| Apache Spark / PySpark | Transformação e validação de dados. |
| Unity Catalog | Organização e governança de recursos. |
| Delta Lake | Armazenamento transacional e versionamento dos dados. |
| Databricks Asset Bundles | Configuração e implantação versionada de Jobs. |
| Python / SQL | Processamento, testes, validações e automação. |
| Service Principal + OAuth | Autenticação dos workflows de deploy. |

---

## Infraestrutura como código — Terraform

Os recursos são definidos declarativamente, versionados e gerenciados com Terraform. O **HCP Terraform** é utilizado para o estado remoto.

### Recursos provisionados

- Schemas `workspace.bronze`, `workspace.silver`, `workspace.gold` e `workspace.observability`.
- Volume gerenciado `workspace.bronze.raw`.

As tabelas de auditoria são criadas por scripts SQL ou pelas rotinas dos pipelines, conforme cada componente.

### Verificações realizadas

Validação de configuração, provisionamento inicial, testes de idempotência e verificação de consistência da infraestrutura. O objetivo é reduzir configuração manual, preservar rastreabilidade e permitir reprodução do ambiente.

---

## Ingestão — camada Bronze

A ingestão inicial utiliza o Volume `/Volumes/workspace/bronze/raw/` e preserva os dados recebidos das fontes.

| Diretório | Fonte | Conteúdo |
| --- | --- | --- |
| `ibge/` | IBGE | Dados censitários e referências territoriais. |
| `ssp/` | SSP-SP | Informações de segurança pública. |
| `observasampa/` | ObservaSampa | Indicadores municipais. |
| `imoveis/` | Referências imobiliárias | Dados mensais do mercado imobiliário. |
| `geosampa/` | GeoSampa | Equipamentos e informações territoriais. |

### Tabelas Bronze versionadas por DDL

| Fonte | Tabela |
| --- | --- |
| GeoSampa | `workspace.bronze.geo_sampa` |
| IBGE | `workspace.bronze.ibge_agregados_basico_distritos` |
| Imóveis | `workspace.bronze.imoveis` |
| ObservaSampa | `workspace.bronze.observa_sampa` |
| SSP-SP | `workspace.bronze.dados_criminais_unificado_ssp` |

Os cinco DDLs estão em [`barrioiq_pipeline/sql/bronze/`](barrioiq_pipeline/sql/bronze/). O executor [`bronze_ddl_runner.py`](barrioiq_pipeline/bronze_ddl_runner.py) verifica exatamente os cinco arquivos permitidos e usa `CREATE TABLE IF NOT EXISTS`, sem substituir tabelas preexistentes.

**Nota de linhagem:** a transformação Silver do IBGE usa `workspace.bronze.ibge_agregados_basico_v2`, que não deve ser confundida com a tabela `workspace.bronze.ibge_agregados_basico_distritos` definida no DDL inicial. O runner aponta explicitamente para a versão utilizada na transformação.

### Controles de ingestão

As rotinas de ingestão contemplam requisições HTTP com retentativas, downloads em blocos, validação de integridade, SHA-256, ETag e Last-Modified quando disponíveis, comparação de arquivos e preservação de versões existentes diante de falhas.

A auditoria da ingestão é armazenada em `workspace.observability.raw_ingestion_runs`.

**Importante:** o Job de DDLs Bronze administra estruturas; **não é responsável por baixar arquivos nem recarregar os registros reais**.

---

## Transformação — camada Silver

As cinco transformações abaixo foram publicadas e verificadas com dados reais no Databricks. As regras e a granularidade variam por fonte; elas **não compõem ainda uma tabela Gold unificada**.

### Inventário Silver

| Fonte | Tabela Silver | Grão / finalidade |
| --- | --- | --- |
| **IBGE — Censo 2022** | `workspace.silver.ibge_agregados_basicos_v2` | Indicadores demográficos por distrito oficial. |
| **SSP-SP** | `workspace.silver.ssp_ocorrencias_distrito` | Ocorrências georreferenciadas, com código e nome do distrito. |
| **GeoSampa** | `workspace.silver.geosampa_equipamentos_distrito` | Quantidades de equipamentos urbanos por distrito. |
| **ObservaSampa** | `workspace.silver.observasampa_indicadores_distrito` | Distrito, indicador e ano de referência. |
| **Imóveis** | `workspace.silver.imoveis_bairro_mensal` | Mês, bairro de origem e tipo de transação. |

### 1. Silver IBGE — base distrital

- **Origem efetiva do runner:** `workspace.bronze.ibge_agregados_basico_v2`.
- **Destino:** `workspace.silver.ibge_agregados_basicos_v2`.
- **Cobertura territorial esperada:** 96 distritos da cidade de São Paulo.
- **Transformação:** tipagem e padronização dos indicadores censitários, preservando códigos e nomes oficiais.
- **Implementação:** [`silver_ibge_runner.py`](barrioiq_pipeline/silver_ibge_runner.py) e [`001_ibge_agregados_basicos.sql`](barrioiq_pipeline/sql/silver/001_ibge_agregados_basicos.sql).
- **Controle:** validação, comparação com a Silver e publicação explícita com auditoria.

### 2. Silver SSP-SP — associação espacial

- **Fonte da verificação:** `workspace.silver.ssp_ocorrencias`, tabela intermediária já tratada.
- **Destino:** `workspace.silver.ssp_ocorrencias_distrito`.
- **Referência:** malha oficial de distritos do IBGE, mantida no Volume, e tabela Silver IBGE.
- **Transformação:** correspondência espacial por latitude/longitude para adicionar `CD_DIST` e `NM_DIST`; não depende apenas da semelhança entre nomes de bairros.
- **Implementação:** [`silver_ssp_spatial_runner.py`](barrioiq_pipeline/silver_ssp_spatial_runner.py).
- **Controle:** `--check` recompõe a associação espacial em memória e compara o resultado com a tabela existente, sem gravar arquivos ou tabelas.

A fonte é baseada em registros de ocorrências. Seus números não devem ser interpretados como taxas de criminalidade por habitante sem denominadores, recortes temporais e regras analíticas apropriadas.

### 3. Silver GeoSampa — equipamentos por distrito

- **Origem:** `workspace.bronze.geo_sampa`.
- **Destino:** `workspace.silver.geosampa_equipamentos_distrito`.
- **Referências:** códigos da Silver IBGE e nomes oficiais da malha distrital do IBGE.
- **Transformação:** padronização de **42 indicadores** de equipamentos e infraestrutura urbana, cobrindo os **96 distritos**.
- **Implementação:** [`silver_geosampa_runner.py`](barrioiq_pipeline/silver_geosampa_runner.py).
- **Controle:** `--check` compara a transformação com o destino; publicação exige `--apply --confirm-publish`.

As contagens representam os indicadores disponibilizados pela fonte. Uma futura pontuação de infraestrutura precisará avaliar normalizações adequadas, como população, área ou demanda por serviço.

### 4. Silver ObservaSampa — indicadores e anos preservados

- **Origem:** `workspace.bronze.observa_sampa`.
- **Referência:** `workspace.silver.geosampa_equipamentos_distrito`.
- **Destino:** `workspace.silver.observasampa_indicadores_distrito`.
- **Grão:** distrito + indicador + ano.
- **Transformação:** correspondência territorial, conversão controlada de valores numéricos e preservação do período original de cada indicador.
- **Implementação:** [`silver_observasampa_runner.py`](barrioiq_pipeline/silver_observasampa_runner.py).
- **Controle:** `--check` somente leitura e publicação explícita; não substitui silenciosamente tabelas divergentes.

**Restrição metodológica:** um indicador apurado em 2021 não pode ser tratado como valor observado em 2026. As comparações temporais serão definidas na camada analítica.

### 5. Silver Imóveis v1 — preços mensais por bairro de origem

- **Origem:** `workspace.bronze.imoveis`.
- **Destino:** `workspace.silver.imoveis_bairro_mensal`.
- **Grão:** `mes` + `bairro` + `transacao`.
- **Modalidades:** `venda` e `aluguel`.
- **Implementação:** [`silver_imoveis_runner.py`](barrioiq_pipeline/silver_imoveis_runner.py).
- **Testes:** [`test_silver_imoveis_runner.py`](tests/test_silver_imoveis_runner.py), **33 testes unitários**.
- **CI dedicado:** [`silver-imoveis-ci.yml`](.github/workflows/silver-imoveis-ci.yml).

#### Perfil dos dados na validação inicial (03/11/2026)

| Métrica | Resultado |
| --- | ---: |
| Registros | **29.612** |
| Nomes distintos de bairros na origem | **1.626** |
| Meses | **14** |
| Período coberto | **set/2025 a out/2026** |
| Registros de venda | **18.747** |
| Registros de aluguel | **10.865** |
| Conjuntos de preço válidos | **26.372** (89,06%) |
| Conjuntos com `p25_m2`, `mediana_m2` e `p75_m2` nulos | **3.240** (10,94%) |
| Chaves duplicadas `mes + bairro + transacao` | **0** |

Nos 3.240 registros sem preço, **os três valores de preço estão simultaneamente nulos**. Eles são preservados com o status `TRES_PRECOS_NULOS`, sem imputação ou conversão para zero. Os registros válidos recebem `PRECO_VALIDO` após verificação de valores positivos e ordenação dos percentis.

A Silver mantém o bairro original e acrescenta `bairro_normalizado` como apoio à padronização textual. **Isso não é um vínculo distrital.** O mapeamento dos 1.626 nomes para os 96 distritos exigirá uma etapa territorial independente, com documentação das correspondências e cobertura.

O runner valida nulidade, tipos, percentis, métricas não negativas, unicidade e cobertura mínima da base. `--check` não grava dados; `--apply --confirm-publish` cria a tabela quando ainda não existe e **bloqueia sobrescrita de destino divergente**.

O primeiro processamento foi validado com dados reais no Databricks, publicado manualmente e novamente conferido. A implementação foi integrada à `main` pelo [PR #29](https://github.com/DCosso/bairroiq/pull/29).

### Execução e segurança das transformações

Os runners têm contratos distintos, documentados em cada arquivo. Exemplos de uso para as transformações que oferecem ambos os modos:

```bash
# Validar sem publicar
python silver_imoveis_runner.py --check
python silver_geosampa_runner.py --check
python silver_observasampa_runner.py --check

# Publicação explícita — somente após validação e revisão
python silver_imoveis_runner.py --apply --confirm-publish
```

A validação é feita antes de publicar. **Não existe atualização automática de todas as tabelas Silver a cada merge.** O deploy de Jobs e a publicação ou atualização de dados são responsabilidades distintas.

---

## CI/CD — GitHub Actions e Databricks Bundles

### Integração contínua (CI)

O repositório executa verificações para:

- Testes Python e regras de Data Quality.
- Validação dos cinco DDLs Bronze.
- Análise de configurações Terraform.
- Validação estrutural dos Databricks Asset Bundles.
- Testes específicos das transformações Silver (incluindo os 33 testes da Silver Imóveis).

A estratégia utiliza branches, Pull Requests e verificações automatizadas. As regras de aprovação e revisão dependem da configuração vigente da proteção da `main`.

### Entrega contínua (CD)

O workflow [`databricks-cd-deploy.yml`](.github/workflows/databricks-cd-deploy.yml) autentica com Service Principal e OAuth, valida e implanta o Bundle e verifica os Jobs publicados. Na configuração atual, o workflow também **executa automaticamente o Job de DDLs Bronze** após o deploy aprovado; os Jobs de verificação Silver não são disparados automaticamente pelo CD.

### Jobs versionados no Bundle

| Job | Finalidade | Execução após deploy |
| --- | --- | --- |
| `bairroiq-smoke-job` | Verificação sintética de ambiente/qualidade. | Não iniciada automaticamente pelo deploy da Bronze. |
| Bronze DDL Job | Validação e aplicação controlada dos cinco DDLs. | **Disparado pelo CD.** |
| Silver IBGE Check | Revalidar a transformação IBGE. | Manual. |
| Silver SSP Check | Revalidar a associação espacial SSP. | Manual. |
| Silver ObservaSampa Check | Revalidar indicadores municipais. | Manual. |
| Silver GeoSampa Check | Revalidar equipamentos distritais. | Manual. |

São **seis Jobs versionados**, incluindo **quatro Jobs de checagem Silver**. A **Silver Imóveis ainda não possui Job no Bundle**: seu runner e seu CI estão versionados, e a publicação inicial foi manual.

Os recursos estão declarados em [`barrioiq_pipeline/resources/`](barrioiq_pipeline/resources/). As validações `--check` não devem modificar tabelas nem arquivos. Não há agendamento recorrente próprio para esses Jobs.

O [CD da integração da Silver Imóveis](https://github.com/DCosso/bairroiq/actions/runs/41746876808) finalizou com sucesso após o PR #29.

### Fluxo de contribuição

`Branch → Código e testes → CI → Pull Request → Checks → Merge → CD`

---

## Análise exploratória — histórico das fontes

As informações abaixo documentam levantamentos exploratórios anteriores. **Os totais de arquivos brutos não são necessariamente equivalentes aos totais das tabelas Silver publicadas.**

### Segurança pública (SSP-SP)

O levantamento inicial analisou seis arquivos disponibilizados pela SSP-SP:

| Arquivo | Registros informados | Colunas informadas | Tamanho |
| --- | ---: | ---: | ---: |
| `CelularesSubtraidos_2026.xlsx` | 10.211 | 33 | 61,7 MB |
| `DadosProdutividade_2026.xlsx` | 10.211 | 33 | 110,5 MB |
| `MDIP_2026.xlsx` | 10.211 | 33 | 2,0 MB |
| `ObjetosSubtraidos_2026.xlsx` | 10.211 | 33 | 288,4 MB |
| `SPDadosCriminais_2026.xlsx` | 10.211 | 33 | 120,4 MB |
| `VeiculosSubtraidos_2026.xlsx` | 10.211 | 33 | 37,8 MB |

*Dimensões reportadas no levantamento inicial, não uma medição atual da Silver.*

### IBGE — Censo Demográfico 2022

O levantamento exploratório inicial registrou **10.698 registros** e **28 colunas** no conjunto então analisado. A Silver distrital possui um contrato próprio e não deve ser confundida com aquele recorte bruto.

### ObservaSampa — indicadores municipais

A amostra exploratória inicial possuía **1.434 registros** e **4 colunas**: `Nome`, `Região`, `Período` e `Resultado`. Incluía indicadores de vulnerabilidade socioeconômica, habitação e segurança urbana.

Entre os indicadores levantados estavam famílias em extrema pobreza e baixa renda, unidades habitacionais entregues, auxílio-aluguel, domicílios em favelas, atendimento habitacional provisório, câmeras do Projeto City Câmeras e ações da Campanha do Desarmamento.

---

## Qualidade, observabilidade e auditoria

### Data Quality

O projeto possui testes com PySpark e dados sintéticos que verificam chaves nulas, duplicidades, campos obrigatórios, valores inválidos, consistência das transformações e cenários de sucesso/falha.

O Job sintético de qualidade possui tarefas `validar_ambiente` e `validar_qualidade`, com execução dependente e registro de resultados. Os testes sintéticos não substituem a execução dos validadores Silver contra dados reais.

### Tabelas de observabilidade

| Tabela | Uso |
| --- | --- |
| `workspace.observability.data_quality_runs` | Métricas, status e erros dos testes de qualidade. |
| `workspace.observability.raw_ingestion_runs` | Fonte, arquivo, hash, metadados HTTP e resultado da ingestão. |
| `workspace.observability.bronze_ddl_runs` | Aplicação, status e rastreabilidade dos DDLs Bronze. |
| `workspace.observability.silver_ibge_runs` | Auditoria das publicações controladas da Silver IBGE. |

As rotinas registram eventos de validação como `IMOVEIS_SILVER_VALIDATED`, `IMOVEIS_SILVER_CHECK_SUCCESS` e `IMOVEIS_SILVER_APPLY_SUCCESS`, permitindo identificar o resultado de cada etapa nos logs. **Isso não significa que todas as Silver mantenham uma tabela de auditoria persistente própria.**

### Evidências DORA

O repositório possui um workflow inicial para coletar evidências de entregas. Ainda não representa a medição completa dos quatro indicadores DORA (frequência de deploy, lead time, taxa de falha de mudança e tempo de recuperação).

---

## Governança e limitações

- Código, testes, configurações e infraestrutura versionados.
- Publicações Silver protegidas contra alterações acidentais, conforme o runner de cada fonte.
- Rastreabilidade de snapshots Delta onde implementada.
- Granularidades e períodos preservados antes de criar indicadores comparativos.
- Validações específicas para qualidade e limites territoriais.
- Custos e recursos considerados de acordo com a proposta de desenvolvimento em plataformas gratuitas.


---

## Referências de implementação

- [Pipelines e arquivos Python](barrioiq_pipeline/)
- [Definições dos Jobs](barrioiq_pipeline/resources/)
- [DDL Bronze](barrioiq_pipeline/sql/bronze/)
- [SQL Silver IBGE](barrioiq_pipeline/sql/silver/)
- [Workflows do GitHub Actions](.github/workflows/)
- [Testes automatizados](tests/)
- [PR #29 — Silver Imóveis](https://github.com/DCosso/bairroiq/pull/29)
