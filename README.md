# BairroIQ — Inteligência Territorial para Decisões Mais Inteligentes

**Plataforma de inteligência geográfica e análise de dados urbanos para São Paulo.**

O BairroIQ é um projeto de Engenharia de Dados, Analytics e DataOps que integra informações públicas e imobiliárias para construir uma visão multidimensional das regiões de São Paulo.

Seu objetivo é transformar dados fragmentados em informações confiáveis, comparáveis e explicáveis, apoiando decisões sobre **onde morar, investir ou estabelecer um negócio**.

O projeto utiliza uma arquitetura de dados em nuvem, pipelines de processamento distribuído, governança e automação de qualidade.

**Status atual:** infraestrutura e base analítica implementadas. Aplicação web e modelos de recomendação em desenvolvimento futuro.

---

## Principais entregas

O BairroIQ já possui uma base analítica georreferenciada, publicada e validada no Databricks, consolidando informações demográficas, socioeconômicas, urbanas, criminais e imobiliárias.

| Indicador | Resultado |
|---|---:|
| Distritos administrativos de São Paulo | **96** |
| Atributos disponíveis na base analítica | **254** |
| Indicadores socioeconômicos integrados | **104** |
| Categorias de ocorrências criminais | **41** |
| Indicadores de equipamentos urbanos | **42** |
| Indicadores de infraestrutura normalizados | **42** |
| Distritos com coordenadas geográficas | **96 (100%)** |
| Registros na base imobiliária mensal | **29.612** |
| Localidades imobiliárias identificadas | **1.626** |
| Jobs configurados no Databricks Bundle | **7** |

### O que foi construído

- **Data Lakehouse:** arquitetura Medallion com camadas Bronze, Silver e Gold utilizando Databricks, Apache Spark e Delta Lake.
- **Integração multifuente:** consolidação de dados do IBGE, GeoSampa, ObservaSampa, SSP-SP e referências do mercado imobiliário.
- **Base analítica geográfica:** tabela com 254 atributos para os 96 distritos oficiais do município.
- **Georreferenciamento:** cálculo de centroides geográficos a partir da malha distrital oficial do IBGE 2022.
- **Associação territorial:** processo de correspondência entre bairros imobiliários e distritos administrativos, utilizando OpenStreetMap e validação dos vínculos.
- **Data Quality:** testes automatizados de integridade, consistência, granularidade, cobertura e conformidade dos dados.
- **DataOps e CI/CD:** pipelines de integração contínua, validação de Databricks Asset Bundles e deploy controlado.
- **Governança:** contratos de dados, documentação das 254 colunas, comentários no Unity Catalog, rastreabilidade e versionamento Delta.

---

## Arquitetura da solução

O projeto utiliza a arquitetura **Medallion**, organizando o processamento em três camadas.

```text
                   FONTES DE DADOS
                          |
          +---------------+---------------+
          |               |               |
        IBGE          GeoSampa        SSP-SP
          |               |               |
     ObservaSampa    Mercado Imobiliário
          |               |
          +-------+-------+
                  |
                  v
          BRONZE | Raw Data
       Dados originais preservados
                  |
                  v
          SILVER | Trusted Data
      Limpeza, tipagem, padronização
       e enriquecimento territorial
                  |
                  v
          GOLD | Analytics
       96 distritos oficiais
         254 atributos
       Coordenadas geográficas
                  |
                  v
        CAMADA DE CONSUMO
              (futura)
       Mapas e comparativos
       Rankings explicáveis
       Recomendações regionais
```

### Camadas de dados

| Camada | Responsabilidade | Implementação |
|---|---|---|
| Bronze | Ingestão e preservação dos dados originais | Delta Lake e volumes gerenciados |
| Silver | Tratamento, validação e enriquecimento | PySpark, SQL e processamento geoespacial |
| Gold | Consolidação dos indicadores por distrito | Wide Table com 254 colunas |
| Consumo | Visualização e recomendação territorial | Planejado |

O processamento foi desenvolvido no Databricks, com governança pelo Unity Catalog.

---

## Fontes de informação

| Fonte | Dados utilizados | Aplicação |
|---|---|---|
| **IBGE** | População, domicílios, características demográficas e malha distrital | Perfil populacional e referência territorial |
| **GeoSampa** | Equipamentos públicos e infraestrutura urbana | Disponibilidade de serviços por distrito |
| **ObservaSampa** | Indicadores sociais, econômicos, educacionais e urbanos | Condições socioeconômicas |
| **SSP-SP** | Registros de ocorrências criminais | Indicadores de segurança pública |
| **Mercado imobiliário** | Anúncios, preços por metro quadrado e modalidades de transação | Análise de oferta e preços de imóveis |
| **OpenStreetMap** | Referências geográficas de localidades | Apoio à associação entre bairros e distritos |

Os indicadores mantêm as características e os períodos de referência de suas respectivas fontes.

### Integração territorial

Uma das dificuldades técnicas do projeto é a diferença entre os bairros utilizados pelo mercado imobiliário e os distritos administrativos oficiais.

Para tratar essa incompatibilidade, foi implementado um processo de associação territorial com validação e homologação de correspondências.

Na validação mais recente:

| Métrica | Resultado |
|---|---:|
| Localidades imobiliárias inventariadas | 1.626 |
| Bairros com associação aprovada | 93 |
| Estoque imobiliário total da fonte | 70.706 |
| Estoque associado a distritos | 28.085 |
| Cobertura do estoque | 39,72% |

A cobertura é apresentada explicitamente para evitar interpretações incorretas. Os imóveis sem associação territorial aprovada não são distribuídos arbitrariamente entre distritos.

---

## Base analítica e georreferenciamento

O principal produto de dados é a tabela:

`workspace.gold.distritos_wide`

Ela consolida os indicadores disponíveis em uma estrutura com **uma linha por distrito administrativo**.

A tabela inclui informações de população, domicílios, infraestrutura, indicadores socioeconômicos, segurança pública, mercado imobiliário e localização geográfica.

### Coordenadas oficiais

Todos os 96 distritos possuem coordenadas de latitude e longitude obtidas a partir de centroides calculados sobre a malha oficial do IBGE 2022.

O processamento utiliza uma projeção métrica (EPSG:31983) para o cálculo dos centroides, com transformação posterior para WGS84 (EPSG:4326).

Esses pontos representam os centros geométricos dos distritos, e não endereços, centros comerciais ou concentrações populacionais.

### Exemplo de consulta

```sql
SELECT
    NM_DIST AS distrito,
    ibge_total_pessoas AS populacao_censo,
    imv_venda_estoque AS estoque_imoveis_venda,
    latitude,
    longitude
FROM workspace.gold.distritos_wide
ORDER BY NM_DIST;
```

A consulta exemplifica como combinar dados demográficos, imobiliários e geográficos em uma mesma estrutura analítica.

O [dicionário de dados completo](docs/dicionario_gold_distritos_wide.md) apresenta as definições, unidades, regras de cálculo, origens e limitações dos 254 atributos.

---

## Engenharia, qualidade e governança

O BairroIQ foi desenvolvido com foco em reprodutibilidade, confiabilidade e separação entre desenvolvimento, validação e publicação.

### Práticas implementadas

**Engenharia de Dados**

- Processamento distribuído com Apache Spark.
- Modelagem Medallion e tabelas Delta.
- Integração e normalização de múltiplas fontes.
- Processamento e validação geoespacial.
- Controle explícito da granularidade dos dados.

**Qualidade e governança**

- Testes de chaves nulas e duplicadas.
- Validação de schemas, tipos e valores.
- Verificação de consistência entre fontes e destinos.
- Contratos de dados documentados.
- Rastreabilidade de versões Delta.
- Comentários de campos e metadados no Unity Catalog.
- Validações estritas que falham quando detectam divergências.

**DataOps e automação**

- Controle de versão com Git e GitHub.
- Testes automatizados com GitHub Actions.
- Infraestrutura como código com Terraform.
- Definição dos Jobs por Databricks Asset Bundles.
- Workflows de CI/CD com validações de segurança.
- Separação entre testes somente leitura e operações de publicação.

A base Gold foi validada integralmente contra sua reconstrução a partir das fontes, com confirmação de identidade de schema e conteúdo.

A configuração de validação automatizada da Gold está versionada na branch de desenvolvimento e depende da integração e do deploy para atualização do job gerenciado.

---

## Stack tecnológica

| Categoria | Tecnologias |
|---|---|
| Cloud e processamento | Databricks, Apache Spark, PySpark |
| Armazenamento | Delta Lake, Unity Catalog |
| Linguagens | Python, SQL |
| Processamento geoespacial | GeoPandas, Shapely, PyProj |
| Infraestrutura como código | Terraform, HCP Terraform |
| Orquestração e deploy | Databricks Asset Bundles |
| CI/CD | GitHub Actions |
| Versionamento | Git, GitHub |
| Documentação e governança | Markdown, JSON, Unity Catalog |

O desenvolvimento prioriza tecnologias de código aberto e recursos gratuitos, respeitando as limitações operacionais de cada plataforma.

---

## Organização do repositório

```text
bairroiq/
|
|-- barrioiq_pipeline/
|   |-- sql/
|   |   |-- bronze/
|   |   `-- silver/
|   |
|   |-- resources/
|   |
|   |-- gold_distritos_wide_runner.py
|   |-- gold_distritos_wide_v4_runner.py
|   |-- gold_distritos_geo.py
|   |-- gold_distritos_wide_v4_strict_check.py
|   `-- distritos_centroides_ibge_2022.json
|
|-- tests/
|   `-- Testes automatizados
|
|-- docs/
|   |-- dicionario_gold_distritos_wide.md
|   `-- dicionario_gold_distritos_wide.json
|
|-- .github/
|   `-- workflows/
|
`-- README.md
```

Os scripts de processamento, testes e configurações de deploy são versionados para facilitar auditoria, evolução e reprodução dos componentes.

---

## Documentação técnica

- [Dicionário completo da Gold — Markdown](docs/dicionario_gold_distritos_wide.md)
- [Contrato de dados da Gold — JSON](docs/dicionario_gold_distritos_wide.json)
- [Pipelines de Engenharia de Dados](barrioiq_pipeline/)
- [Configurações dos Jobs](barrioiq_pipeline/resources/)
- [Testes automatizados](tests/)
- [Workflows de CI/CD](.github/workflows/)

---

**BairroIQ — Transformando dados urbanos em inteligência territorial.**
