# BairroIQ — Inteligência Geográfica para Moradia e Negócios

## Sobre o projeto

O BairroIQ é um projeto de Engenharia de Dados que busca integrar indicadores públicos para apoiar decisões sobre onde morar ou trabalhar na cidade de São Paulo.

A solução pretende transformar dados dispersos em informações comparáveis por meio de um ranking explicável e de técnicas de clusterização, permitindo identificar regiões com características urbanas semelhantes.

## Problema de negócio

A escolha de uma região para morar ou trabalhar envolve fatores como custo de vida, segurança, mobilidade, infraestrutura, oportunidades de emprego e serviços.

Entretanto, essas informações estão distribuídas em diferentes fontes, com variações de metodologia, atualização e granularidade geográfica, dificultando uma análise integrada.

O BairroIQ busca responder à seguinte pergunta:

**Qual é a melhor região de São Paulo para morar ou trabalhar, considerando orçamento, segurança, mobilidade, infraestrutura, oportunidades e estilo de vida?**

## Objetivo

Desenvolver um MVP que demonstre a integração de dados públicos, o cálculo reproduzível de um ranking, a explicação dos resultados e a identificação de perfis urbanos por clusterização.

## Pilares de análise

| Pilar | Objetivo |
|---|---|
| Custo de vida | Analisar referências de preços de moradia e outros custos disponíveis. |
| Segurança | Avaliar indicadores públicos relacionados à criminalidade. |
| Mobilidade | Investigar transporte público e conectividade urbana. |
| Infraestrutura | Considerar parques, equipamentos urbanos e serviços públicos. |
| Empregos e serviços | Analisar atividades econômicas, estabelecimentos e oportunidades. |

## Escopo geográfico

O escopo inicial será a cidade de São Paulo. A análise priorizará os distritos oficiais quando esse for o nível territorial compatível entre as fontes, com possibilidade de expansão para bairros conforme a disponibilidade de dados.

## Entrega final

O produto será uma aplicação web interativa para:

- Consultar e explorar o ranking das regiões.
- Comparar áreas por dimensão.
- Visualizar indicadores e mapas.
- Identificar perfis urbanos por clusterização.
- Consultar fontes, metodologia e limitações dos resultados.

## Arquitetura e tecnologias previstas

O projeto contemplará uma arquitetura Lambda em nuvem, com caminhos de processamento batch e incremental, camadas Bronze, Silver e Gold, modelagem Star Schema e Wide Table, além de CI/CD e infraestrutura como código.

## Arquitetura de dados

O projeto adota a **arquitetura Medallion**, organizada em três camadas:

| Camada | Responsabilidade | Situação |
|---|---|---|
| Bronze | Receber e preservar os dados brutos das fontes públicas.
| Silver | Limpar, padronizar, validar e integrar os dados.
| Gold | Disponibilizar indicadores consolidados para análises e aplicações. 

A infraestrutura contempla também uma camada independente de observabilidade.

### Organização no Unity Catalog

Os recursos estão organizados no catálogo `workspace`:

- `workspace.bronze`
- `workspace.silver`
- `workspace.gold`
- `workspace.observability`

Foi criado o Volume gerenciado:

`/Volumes/workspace/bronze/raw/`

A evolução arquitetural prevê processamento batch e incremental, conforme os requisitos acadêmicos, além de modelagem Star Schema e Wide Table.

---

## Tecnologias utilizadas

| Tecnologia | Finalidade |
|---|---|
| GitHub | Versionamento, colaboração e revisão de código por Pull Requests. |
| GitHub Actions | Automação de integração e entrega contínuas. |
| Terraform | Provisionamento e gerenciamento da infraestrutura como código. |
| HCP Terraform | Gerenciamento remoto do estado Terraform. |
| Databricks Free | Ambiente de execução dos pipelines de dados. |
| Apache Spark / PySpark | Processamento distribuído e transformação de dados. |
| Unity Catalog | Organização e governança dos recursos de dados. |
| Delta Lake | Persistência transacional e auditoria. |
| Databricks Bundles | Definição e publicação versionada de Jobs. |
| Python | Ingestão de fontes, validação e automações. |
| Service Principal + OAuth | Autenticação das automações de deploy. |

---

## Infraestrutura como código — Terraform

A infraestrutura do BairroIQ é gerenciada por **Terraform**, permitindo que os recursos sejam definidos de forma declarativa, versionados e reproduzidos.

### Recursos provisionados

- Schema `workspace.bronze`.
- Schema `workspace.silver`.
- Schema `workspace.gold`.
- Schema `workspace.observability`.
- Volume gerenciado `workspace.bronze.raw`.

O **HCP Terraform** é utilizado para gerenciamento remoto do estado da infraestrutura.

As tabelas de auditoria são criadas por definições SQL e rotinas de inicialização dos pipelines.

### Validações realizadas

- Inicialização e validação do Terraform.
- Verificação das configurações dos recursos.
- Provisionamento inicial.
- Testes de idempotência.
- Verificação da consistência da infraestrutura existente.

### Benefícios

- Rastreabilidade das mudanças.
- Redução de configurações manuais.
- Reprodutibilidade do ambiente.
- Infraestrutura versionada.
- Facilidade de manutenção e evolução.

---

## CI/CD — Integração e entrega contínuas

O BairroIQ possui pipelines automatizados utilizando **GitHub Actions** e **Databricks Bundles**.

### Integração contínua (CI)

As alterações submetidas ao repositório passam por verificações automatizadas, incluindo:

- Testes Python.
- Validação de qualidade de dados.
- Verificações de Terraform.
- Validação das configurações dos Databricks Bundles.
- Verificações de consistência do código e dos artefatos de implantação.

As regras de proteção da branch `main` exigem revisão e aprovação por Pull Request, além dos checks configurados.

### Entrega contínua (CD)

Foi implementado um workflow de implantação automatizada para o Job de validação do Databricks.

A autenticação utiliza **Service Principal e OAuth**, sem necessidade de armazenar credenciais pessoais no código-fonte.

O processo utiliza Databricks Bundles para gerenciar a implantação do Job existente, evitando a criação indevida de recursos duplicados.

O deploy é controlado pelos workflows associados à branch `main` e pelas respectivas condições de execução.

### Fluxo de desenvolvimento

1. Criar uma branch a partir da `main`.
2. Desenvolver a funcionalidade.
3. Executar os testes.
4. Abrir um Pull Request.
5. Aguardar a execução dos workflows de CI.
6. Solicitar revisão e aprovação.
7. Integrar as alterações à `main`.
8. Executar os workflows de CD aplicáveis.

**Fluxo resumido:**

`Branch → Desenvolvimento → CI → Pull Request → Aprovação → Merge → CD`

Essa abordagem permite validar mudanças antes da integração e manter o histórico das entregas.

---

## Data Quality

Foi desenvolvido um pipeline inicial de validação utilizando **PySpark** e dados sintéticos.

### Regras implementadas

- Identificação de chaves nulas.
- Detecção de registros duplicados.
- Verificação de campos obrigatórios.
- Validação de valores inválidos.
- Consistência de agregações.
- Integridade dos resultados processados.

### Job de validação

O Job automatizado possui duas tarefas dependentes:

**1. `validar_ambiente`**

Verifica a execução e a disponibilidade do ambiente Spark.

**2. `validar_qualidade`**

Executa as regras de Data Quality e registra as métricas da execução.

### Testes realizados

Foram testados cenários de sucesso e falha, verificando:

- Execução completa do Job.
- Encadeamento correto das tarefas.
- Registro de métricas de qualidade.
- Persistência dos resultados em Delta Lake.
- Registro de erros simulados.
- Preservação do status de falha da execução.

O pipeline sintético valida a infraestrutura e o mecanismo de auditoria. A aplicação das regras às fontes reais faz parte da evolução do projeto.

---

## Observabilidade e auditoria

O BairroIQ possui uma camada dedicada ao acompanhamento das execuções e dos resultados dos pipelines.

### Auditoria de Data Quality

Tabela Delta:

`workspace.observability.data_quality_runs`

Armazena informações como:

- Identificador da execução.
- Data e horário.
- Pipeline executado.
- Status de sucesso ou falha.
- Quantidade de registros processados.
- Métricas de qualidade.
- Tempo de execução.
- Mensagens de erro.

### Auditoria da ingestão Bronze

Tabela Delta:

`workspace.observability.raw_ingestion_runs`

Registra informações relacionadas à ingestão dos arquivos:

- Identificador da execução.
- Data e horário.
- Fonte de dados.
- Nome do arquivo.
- URL de origem.
- Status da ingestão.
- Tamanho do arquivo.
- Hash SHA-256.
- ETag e Last-Modified, quando disponíveis.
- Duração do processamento.
- Mensagem de erro.

### Estados da ingestão

| Status | Significado |
|---|---|
| NOVO | Arquivo baixado pela primeira vez. |
| ATUALIZADO | Arquivo existente substituído por uma nova versão. |
| SEM_ALTERACAO | Download realizado sem alteração no conteúdo. |
| NAO_MODIFICADO | Fonte confirmou ausência de atualização via HTTP 304. |
| ERRO | Falha durante download, validação ou processamento. |

### Evidências DORA

O projeto possui um workflow inicial de coleta de evidências relacionadas às entregas automatizadas.

Essas informações apoiam a evolução para indicadores DORA, incluindo:

- Frequência de implantação.
- Lead time para mudanças.
- Taxa de falhas nas mudanças.
- Tempo de recuperação após falhas.

A coleta atual representa evidências iniciais de CI/CD, não uma medição completa dos quatro indicadores DORA.

---

## Ingestão de dados — Bronze

A ingestão inicial coleta dados de fontes públicas e os armazena no Volume:

`/Volumes/workspace/bronze/raw/`

### Fontes de dados

| Diretório | Fonte | Conteúdo |
|---|---|---|
| `ibge/` | IBGE | Indicadores demográficos e territoriais. |
| `ssp/` | SSP-SP | Dados de segurança pública. |
| `observasampa/` | ObservaSampa | Indicadores municipais. |
| `imoveis/` | Referências imobiliárias | Dados de mercado imobiliário. |
| `geosampa/` | GeoSampa | Dados geográficos e territoriais. |

### Controles implementados

O pipeline de ingestão contempla:

- Requisições HTTP com retentativas.
- Download em blocos.
- Verificação de integridade dos arquivos.
- Cálculo de hash SHA-256.
- Comparação com arquivos existentes.
- Verificação de atualizações por ETag e Last-Modified, quando disponíveis.
- Registro das execuções em Delta Lake.
- Tratamento de falhas.
- Preservação do arquivo existente em caso de falha no download ou na validação do novo conteúdo.
- Resumo dos resultados de cada execução.

---

## Governança e colaboração

O desenvolvimento segue práticas de **DataOps e DevOps**, incluindo:

- Versionamento de código e infraestrutura.
- Proteção da branch principal.
- Desenvolvimento em branches específicas.
- Revisão obrigatória por Pull Request.
- Verificações automatizadas antes do merge.
- Implantação controlada.
- Auditoria persistente.
- Separação entre infraestrutura, pipelines e dados.
**Stack proposta:** .

