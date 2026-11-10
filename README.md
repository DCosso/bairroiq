# Atlas Sampa

**Plataforma de inteligência territorial para explorar e comparar os 96 distritos administrativos da cidade de São Paulo.**

O **Atlas Sampa** transforma dados públicos de diferentes origens em uma experiência interativa de análise territorial.

O produto permite explorar características dos distritos, comparar indicadores urbanos e personalizar critérios relacionados à segurança, mobilidade, verde e lazer e serviços públicos.

O objetivo é facilitar a compreensão das diferenças territoriais de São Paulo, sem estabelecer uma classificação universal de melhores e piores regiões.

O projeto técnico está organizado no repositório **BairroIQ**, que reúne engenharia de dados, modelagem analítica, Machine Learning, infraestrutura como código, automação, governança, observabilidade e desenvolvimento de aplicações.

## Acesse o Atlas Sampa

**[Abrir aplicativo interativo](https://atlas-sampa.streamlit.app/)**

O aplicativo está disponível publicamente e pode ser acessado por computadores e dispositivos móveis, sem necessidade de cadastro.

Entre as funcionalidades disponíveis estão:

- Exploração dos 96 distritos administrativos de São Paulo.
- Visualização territorial em mapa interativo.
- Personalização de critérios e prioridades.
- Rankings calculados conforme as preferências selecionadas.
- Comparação de indicadores entre distritos.
- Exploração de nove perfis territoriais identificados por Machine Learning.
- Consulta às fontes e limitações dos indicadores.

A versão pública utiliza um **snapshot estático, auditado e autorizado**, contendo 96 registros e 15 campos agregados.

Os dados foram produzidos no Databricks e publicados em um formato independente de consultas contínuas ao SQL Warehouse.

Essa decisão mantém a aplicação pública desacoplada da infraestrutura de processamento, reduzindo dependências operacionais e preservando a reprodutibilidade dos resultados.

A aplicação privada integrada ao Databricks permanece preservada.

**Estado do projeto em novembro de 2026:** Lakehouse implementado, Gold distrital auditada, Star Schema Delta materializado, experimentos de Machine Learning concluídos, Consumer V2 validado, aplicativo Streamlit publicado, arquitetura Lambda da SSP executada e reconciliada, testes automatizados e infraestrutura declarativa versionados.

A arquitetura adota atualização sob demanda e publicação analítica controlada. O processamento de uma nova versão de qualquer fonte não implica necessariamente uma nova versão da Gold, dos modelos ou do aplicativo.

## 1. Problema de negócio

A avaliação de uma região para morar, trabalhar, investir ou estabelecer atividades depende de múltiplos fatores.

Características como mobilidade, infraestrutura urbana, serviços públicos, densidade populacional, dinâmica imobiliária e ocorrências criminais representam dimensões diferentes do território.

Embora existam fontes públicas relevantes para essas análises, os dados normalmente apresentam limitações de integração.

Entre as principais dificuldades identificadas estão:

- Dados distribuídos entre diferentes portais e instituições.
- Formatos heterogêneos de armazenamento e disponibilização.
- Diferentes granularidades geográficas.
- Períodos de referência que não coincidem.
- Ausência de identificadores territoriais padronizados.
- Necessidade de tratamento de coordenadas e geometrias.
- Indicadores expressos em escalas e unidades incompatíveis.
- Dificuldade de reprodução das análises.
- Limitações de cobertura em determinadas fontes.

Esses problemas dificultam comparações consistentes entre regiões.

A utilização isolada de um indicador também pode produzir interpretações inadequadas.

Por exemplo, um distrito que apresenta muitos equipamentos públicos pode possuir grande população e, consequentemente, uma disponibilidade relativa menor quando os equipamentos são analisados por habitante.

Da mesma forma, números absolutos de ocorrências criminais não devem ser comparados sem considerar a população e as limitações da própria fonte.

### 1.1. Proposta de solução

O Atlas Sampa consolida informações territoriais em uma arquitetura de dados capaz de integrar, padronizar, validar e disponibilizar indicadores para análise.

A unidade territorial escolhida corresponde aos **96 distritos administrativos oficiais de São Paulo**.

Essa decisão foi motivada pela disponibilidade de códigos geográficos estáveis, limites territoriais verificáveis e indicadores associados à divisão administrativa.

A utilização dos distritos também reduz ambiguidades relacionadas a nomes comerciais de bairros, que podem variar entre fontes e não possuir limites geográficos equivalentes.

### 1.2. Valor entregue

A plataforma oferece uma experiência de exploração territorial baseada em dados.

O usuário pode definir quais critérios considera mais importantes e visualizar como essas prioridades modificam os resultados comparativos.

O aplicativo não pretende determinar qual região é universalmente melhor.

Sua proposta é disponibilizar informações comparáveis e permitir que diferentes preferências produzam diferentes perspectivas sobre o território.

Essa abordagem separa a interpretação estatística dos dados das escolhas individuais.

## 2. Resultados técnicos e escopo validado

| Componente | Resultado |
|---|---|
| Abrangência territorial | 96 distritos oficiais de São Paulo |
| Tabela analítica principal | `workspace.gold.distritos_wide` |
| Granularidade da Gold | Uma linha por distrito |
| Atributos na Gold | 254 colunas |
| Coordenadas geográficas | 96 distritos com latitude e longitude válidas |
| Modelo dimensional | 4 dimensões e 3 tabelas de fatos |
| Total de registros dimensionais e factuais | 1.365 |
| Machine Learning | Comparação entre K-Means e Ward |
| Modelo selecionado | K-Means com 9 grupos |
| Consumer V2 privado | 96 registros e 20 campos |
| Snapshot público | 96 registros e 15 campos |
| Aplicativo | Streamlit publicado no Community Cloud |
| Arquitetura Lambda | Batch, Speed e Serving no Databricks |
| Publicação SSP validada | 250.606 ocorrências |
| Cobertura da publicação Lambda | 96 distritos, 9 meses e 2 categorias |
| Reconciliação Lambda | 1.728 linhas com zero divergências |
| Versionamento | GitHub e Delta Lake |
| CI/CD | GitHub Actions e Databricks Asset Bundles |
| Infraestrutura como código | Terraform e HCP Terraform |
| Governança | Unity Catalog, contratos e documentação |
| Observabilidade | Logs, auditorias, Jobs e tabelas Delta |
| Política de atualização | Processamento sob demanda e publicação controlada |

Os resultados representam diferentes produtos de dados e não devem ser interpretados como se todos estivessem associados ao mesmo período estatístico.

A Gold consolida os indicadores utilizados na construção de seu snapshot.

A Serving da arquitetura Lambda representa uma publicação independente da SSP.

O aplicativo público utiliza uma fotografia aprovada do Consumer V2, sem recomputar os modelos ou atualizar automaticamente os indicadores.

## 3. Arquitetura da solução

O Atlas Sampa utiliza uma arquitetura **Data Lakehouse baseada no padrão Medallion**, implementada no Databricks com Apache Spark, Delta Lake e Unity Catalog.

O fluxo principal é organizado em camadas:

`Fontes → Raw → Bronze → Silver → Gold → Produtos analíticos → Aplicação`

A arquitetura integra diferentes responsabilidades.

A ingestão recebe e preserva os dados de origem.

As transformações tratam problemas de qualidade, padronizam informações e realizam associações territoriais.

A Gold consolida os indicadores e disponibiliza uma estrutura adequada para análises.

O Star Schema organiza informações para consultas dimensionais.

O Machine Learning identifica padrões de semelhança territorial.

O Consumer fornece um contrato específico para a aplicação.

Paralelamente, a arquitetura Lambda processa republicações da base de ocorrências criminais da SSP.

### 3.1. Por que utilizar uma arquitetura Lakehouse

O projeto trabalha com dados heterogêneos, incluindo arquivos tabulares, indicadores estatísticos, informações geográficas e dados estruturados.

Uma arquitetura exclusivamente relacional exigiria maior adaptação dos diferentes formatos de entrada.

Por outro lado, um Data Lake sem mecanismos transacionais dificultaria a garantia de consistência e a rastreabilidade das transformações.

O Lakehouse combina flexibilidade de armazenamento e recursos de organização analítica.

O Delta Lake oferece controle transacional por tabela, histórico de versões e mecanismos verificáveis de leitura e escrita.

O Apache Spark permite executar transformações em Python e SQL utilizando um mecanismo comum de processamento.

O Unity Catalog organiza objetos, metadados, documentação e permissões.

### 3.2. Separação entre engenharia e consumo

O aplicativo não consulta diretamente as fontes originais nem precisa reconstruir as transformações executadas na plataforma.

Os dados são preparados e materializados antes do consumo.

Essa separação reduz o acoplamento entre engenharia e apresentação.

Também permite que novos indicadores sejam avaliados e versionados sem alterar automaticamente a experiência disponível ao usuário.

### 3.3. Separação entre atualização e publicação

Uma decisão arquitetural importante foi não tratar uma nova ingestão como autorização automática para atualizar os produtos analíticos.

As fontes possuem diferentes frequências de atualização.

Os dados censitários, por exemplo, possuem ciclos longos, enquanto registros criminais podem receber novas publicações mensalmente.

Entretanto, a frequência de atualização de uma fonte não necessariamente corresponde à frequência necessária de atualização do produto.

Uma nova publicação pode conter alterações que não modificam significativamente os resultados.

Em outros casos, alterações pequenas podem afetar indicadores, rankings ou classificações de distritos.

Por esse motivo, a promoção de novas versões deve considerar qualidade, compatibilidade temporal e relevância analítica.

O processamento permanece separado da decisão de publicação.

## 4. Tecnologias e decisões técnicas

| Tecnologia | Aplicação |
|---|---|
| Python | Ingestão, validação e processamento |
| SQL | Transformações, consultas e auditorias |
| Apache Spark | Processamento de dados |
| PySpark | Transformações distribuídas |
| Delta Lake | Persistência transacional e versionamento |
| Databricks | Plataforma de processamento e desenvolvimento |
| Unity Catalog | Organização, metadados e permissões |
| GeoPandas | Processamento geográfico |
| OpenStreetMap | Apoio à correspondência territorial |
| scikit-learn | Machine Learning não supervisionado |
| Pandas | Análises, validações e testes |
| GitHub | Repositório e controle de versão |
| GitHub Actions | Integração contínua e testes |
| Databricks Asset Bundles | Definição declarativa de Jobs |
| Terraform | Infraestrutura como código |
| HCP Terraform | Gerenciamento do estado da infraestrutura |
| Streamlit | Aplicação interativa |
| Plotly | Gráficos e visualizações |

A escolha das ferramentas considerou integração, reprodutibilidade, capacidade de validação e disponibilidade de recursos para desenvolvimento.

O projeto não depende de uma plataforma de streaming contínuo para atender ao comportamento das fontes utilizadas.

Essa decisão reduz complexidade operacional, embora a utilização de recursos como processamento serverless, SQL Warehouse e hospedagem ainda exija atenção aos limites e custos de cada ambiente.

## 5. Fontes de dados e integração territorial

O projeto integra fontes públicas com características distintas.

| Fonte | Informações utilizadas | Considerações |
|---|---|---|
| IBGE | População, densidade, domicílios e malha geográfica | Referência territorial oficial |
| GeoSampa | Infraestrutura e equipamentos urbanos | Cadastros não medem necessariamente capacidade de atendimento |
| ObservaSampa | Indicadores urbanos e socioeconômicos | Referências temporais variáveis |
| SSP-SP | Ocorrências de roubos e furtos | Registros administrativos possuem limitações |
| Mercado imobiliário | Estoque e indicadores de imóveis | Cobertura territorial parcial |
| OpenStreetMap | Referências geográficas de localidades | Apoio à associação espacial |

### 5.1. Padronização geográfica

A principal unidade de integração é o código oficial `CD_DIST`.

A adoção desse identificador evita depender exclusivamente de nomes territoriais.

A malha oficial dos distritos foi utilizada para validar os limites geográficos e realizar associações espaciais.

Os dados originais foram processados considerando os sistemas de referência adequados.

Para cálculos métricos, foi utilizado o sistema **EPSG:31983**.

As geometrias e coordenadas destinadas à visualização foram disponibilizadas em **EPSG:4326**.

Essa separação evita realizar cálculos de distância e centroide diretamente em coordenadas expressas em graus.

### 5.2. Integração imobiliária

Uma das principais dificuldades foi associar nomes comerciais de bairros aos distritos oficiais.

Os nomes utilizados em anúncios imobiliários não possuem necessariamente limites geográficos oficiais.

Por esse motivo, uma associação exclusivamente textual poderia produzir correspondências incorretas.

Foi desenvolvido um processo de identificação, comparação e validação de localidades com apoio de referências geográficas.

Na auditoria documentada foram identificados:

| Indicador | Resultado |
|---|---:|
| Localidades imobiliárias | 1.626 |
| Correspondências aprovadas | 93 |
| Estoque imobiliário total | 70.706 |
| Estoque associado | 28.085 |
| Cobertura do estoque | 39,72% |

A cobertura parcial foi mantida explicitamente.

Não foram realizadas atribuições arbitrárias para aumentar artificialmente a quantidade de imóveis associados.

A limitação de cobertura deve ser considerada em qualquer análise baseada nos indicadores imobiliários.

### 5.3. Integração das ocorrências criminais

Os registros da SSP foram tratados e associados aos distritos a partir de informações geográficas.

As verificações incluem validade das coordenadas, correspondência com o município de São Paulo e associação à malha oficial.

Registros sem correspondência distrital válida permanecem identificáveis para auditoria e não são distribuídos arbitrariamente entre distritos.

A arquitetura também preserva a distinção entre contagens de ocorrências e taxas normalizadas por população.

## 6. Engenharia de dados e arquitetura Medallion

### 6.1. Raw

A camada Raw preserva os arquivos recebidos das fontes, juntamente com informações técnicas de coleta e identificação.

A preservação da origem permite reproduzir transformações e comparar diferentes versões de uma publicação.

Quando aplicável, o conteúdo dos arquivos é identificado por hashes SHA256.

Essa abordagem permite reconhecer arquivos idênticos mesmo quando seus nomes ou datas de coleta são diferentes.

### 6.2. Bronze

A Bronze representa a primeira estruturação dos dados.

Essa camada mantém informações necessárias à rastreabilidade e evita aplicar interpretações analíticas prematuras.

Os processos de ingestão verificam estruturas esperadas, campos obrigatórios e compatibilidade com os contratos das fontes.

A separação por origem facilita a identificação de falhas específicas.

### 6.3. Silver

A Silver concentra tratamento, padronização e enriquecimento.

As principais atividades incluem:

- Conversão e validação de tipos.
- Padronização de nomes e códigos.
- Tratamento de valores ausentes.
- Verificação de cardinalidade.
- Identificação de registros duplicados.
- Associação espacial de registros.
- Padronização de unidades.
- Validação da cobertura geográfica.
- Verificação da consistência dos dados.

Valores ausentes não são automaticamente interpretados como zero.

A ausência de informação pode representar uma situação diferente de uma contagem efetivamente igual a zero.

### 6.4. Gold Wide

A principal tabela analítica é:

`workspace.gold.distritos_wide`

A tabela contém **96 registros e 254 colunas**.

Sua granularidade é de uma linha por distrito administrativo.

A Wide Table foi escolhida para facilitar análises territoriais que utilizam diferentes indicadores simultaneamente.

Essa estrutura também favorece experimentos de Machine Learning, nos quais as observações são organizadas em linhas e as características utilizadas pelo modelo são disponibilizadas em colunas.

A chave territorial utiliza `CD_DIST`.

Os indicadores possuem documentação de origem, descrição, unidade, tratamento e limitações.

### 6.5. Temporalidade da Gold

A Gold não possui uma única data estatística válida para todas as suas colunas.

Dados censitários, informações urbanas, indicadores imobiliários e registros criminais podem possuir períodos de referência diferentes.

A data de processamento não deve ser confundida com a data de observação de cada indicador.

Por esse motivo, não foi criada uma coluna temporal universal artificial.

O histórico técnico do Delta Lake permite rastrear as versões da tabela, mas não substitui a documentação dos períodos de origem.

**Documentação:** [Dicionário completo da Gold](docs/dicionario_gold_distritos_wide.md).

## 7. Modelagem dimensional: Star Schema

A Wide Table oferece uma estrutura conveniente para exploração e Machine Learning.

Entretanto, também foi implementado um modelo dimensional para consultas analíticas estruturadas.

O modelo utiliza uma constelação de fatos, com quatro dimensões e três tabelas de fatos.

| Tabela | Responsabilidade | Registros |
|---|---|---:|
| `bairroiq_dim_snapshot` | Controle dos snapshots | 1 |
| `bairroiq_dim_distrito` | Identificação territorial | 96 |
| `bairroiq_dim_perfil` | Cadastro de perfis | 9 |
| `bairroiq_dim_indicador` | Metadados dos indicadores | 11 |
| `bairroiq_fato_distrito_indicador` | Indicadores por distrito | 1.056 |
| `bairroiq_fato_distrito_perfil` | Associação dos perfis | 96 |
| `bairroiq_fato_prioridade_ocorrencias` | Prioridades relativas de ocorrências | 96 |
| **Total** | **4 dimensões e 3 fatos** | **1.365** |

As estruturas são materializadas em Delta Lake no schema `workspace.gold`.

### 7.1. Controle de granularidade

Cada tabela possui um grão definido.

A fato de indicadores, por exemplo, representa a associação entre snapshot, distrito e indicador.

A fato de perfis representa a associação entre snapshot e distrito.

Essa organização permite realizar análises sem confundir níveis de agregação.

### 7.2. Controle de snapshots

As relações utilizam identificadores de snapshot.

Essa decisão reduz o risco de combinar dados de diferentes versões analíticas.

O registro na dimensão de snapshot é realizado somente após a verificação das demais estruturas.

O procedimento funciona como um marcador de conclusão da materialização.

Entretanto, as escritas em diferentes tabelas não representam necessariamente uma única transação distribuída.

Uma eventual falha intermediária exige validação do estado das estruturas antes da disponibilização do snapshot.

### 7.3. Temporalidade dimensional

Não foi criada uma dimensão calendário artificial a partir da data de execução.

A decisão decorre da existência de diferentes períodos estatísticos nos indicadores da Gold.

Criar uma data de referência universal poderia sugerir comparabilidade temporal inexistente.

**Documentação:** [Contrato do Star Schema Delta](docs/modelagem/star_schema_v1_delta_contrato.md).

## 8. Machine Learning e perfis territoriais

O Machine Learning do Atlas Sampa tem como objetivo identificar padrões de semelhança entre distritos.

O problema foi tratado como **agrupamento não supervisionado**.

Não existe uma variável objetivo validada que permita identificar, de maneira universal, qual distrito é ideal para determinada pessoa.

Criar essa variável artificialmente introduziria premissas subjetivas no treinamento.

Por esse motivo, o projeto compara algoritmos de clusterização em vez de construir um modelo supervisionado de classificação ou previsão.

### 8.1. Algoritmos avaliados

Foram utilizados:

**K-Means:** algoritmo que organiza observações em grupos por meio da proximidade com centros representativos.

**Ward:** abordagem de agrupamento hierárquico que realiza fusões sucessivas procurando controlar o aumento da variabilidade interna dos grupos.

A comparação considerou diferentes quantidades de clusters, com avaliações de `K` entre 2 e 12.

Também foram examinadas distribuição dos grupos, estabilidade, separação estatística e interpretabilidade.

### 8.2. Preparação dos dados

Os experimentos utilizaram indicadores territoriais selecionados da Gold.

As variáveis passaram por tratamentos adequados às suas características e por padronização antes da aplicação dos algoritmos.

As transformações permitiram reduzir diferenças de escala entre indicadores originalmente expressos em unidades distintas.

O tratamento dos dados não modifica a Gold original.

A configuração candidata de nove grupos utiliza uma transformação específica para o eixo de densidade, incluindo `log1p` e winsorização entre os percentis P10 e P90.

Os parâmetros e o hash do dataset são registrados na documentação técnica.

### 8.3. Avaliação dos resultados

| Métrica | Como interpretar | K-Means K9 | Ward K8 |
|---|---|---:|---:|
| Silhouette | Coesão e separação; maior é melhor | 0,194467 | 0,193960 |
| Davies-Bouldin | Similaridade entre grupos; menor é melhor | 1,334164 | 1,202354 |
| ARI mediana | Estabilidade sob reamostragem; maior é melhor | 0,470918 | 0,629504 |
| Menor grupo | Quantidade mínima de distritos | 6 | 4 |
| Maior grupo | Quantidade máxima de distritos | 22 | 23 |
| Silhouettes individuais negativas | Observações próximas de outras classificações | 3 | 10 |

As configurações comparadas possuem diferenças de pré-processamento, de forma que os resultados não isolam exclusivamente o efeito de cada algoritmo.

O Ward apresentou resultados superiores em algumas métricas, especialmente Davies-Bouldin e estabilidade.

Portanto, a escolha do K-Means não representa superioridade estatística universal.

### 8.4. Por que escolhemos K-Means K9

O objetivo inicial do produto era oferecer aproximadamente dez perfis territoriais.

Entretanto, a quantidade desejada de perfis não constitui prova de que existam dez agrupamentos naturais nos dados.

Nos experimentos com dez clusters foram identificados grupos muito pequenos, inclusive agrupamentos unitários em determinadas configurações.

Essa distribuição dificultaria a interpretação e a utilização dos perfis na experiência do usuário.

O K-Means com nove grupos apresentou uma distribuição mais adequada ao produto, com agrupamentos contendo entre 6 e 22 distritos.

Também apresentou apenas três observações com Silhouette individual negativa.

A escolha considerou:

- Granularidade adequada para exploração territorial.
- Ausência de grupos unitários na configuração selecionada.
- Distribuição mais equilibrada dos distritos.
- Facilidade de interpretação dos perfis.
- Possibilidade de operacionalização do modelo.
- Compatibilidade com a experiência de comparação territorial.

A separação estatística global permanece limitada, como indicado pelo valor de Silhouette.

A estabilidade também apresenta sensibilidade à composição dos dados.

Essas limitações fazem parte da interpretação técnica do modelo.

### 8.5. Perfis territoriais

O resultado foi organizado em nove perfis comerciais, com nomes destinados à compreensão do usuário final.

| Perfil | Nome | Distritos |
|---|---|---:|
| P01 | Mais Praças, Vida Urbana | 9 |
| P02 | Praças em Regiões Menos Densas | 7 |
| P03 | Áreas Pouco Povoadas | 6 |
| P04 | Menos Roubos e Furtos | 22 |
| P05 | Transporte Coletivo em Destaque | 7 |
| P06 | Muitos Moradores por Km² | 8 |
| P07 | Empregos em Destaque | 12 |
| P08 | Mais Moradores, Menos Transporte | 19 |
| P09 | Escolas e UBS por Habitante | 6 |
| **Total** | | **96** |

Os nomes são rótulos descritivos de características relativas identificadas no conjunto de dados.

Eles não representam classificações definitivas de qualidade de vida.

O perfil relacionado a menores registros de roubos e furtos não implica ausência de criminalidade ou garantia de segurança individual.

Da mesma forma, o perfil associado a empregos utiliza informações históricas e não garante disponibilidade atual de vagas.

### 8.6. Casos de fronteira

Foram identificados três distritos com Silhouette individual negativa na configuração K-Means K9:

- Mooca.
- Socorro.
- Lajeado.

Essas observações permaneceram nos grupos originalmente atribuídos pelo algoritmo.

Não foram realizadas realocações manuais para melhorar artificialmente os resultados.

### 8.7. Machine Learning e experiência do usuário

Os perfis são utilizados para exploração e comparação territorial.

A personalização do aplicativo é um mecanismo separado.

O usuário pode modificar pesos e critérios sem alterar os clusters produzidos pelo Machine Learning.

Assim, a aplicação combina duas abordagens distintas:

**Agrupamento territorial:** identificação de semelhanças entre distritos.

**Personalização:** cálculo de prioridades conforme critérios definidos pelo usuário.

Essa separação evita confundir clusterização com recomendação supervisionada.

A metodologia, as métricas, os experimentos e as auditorias estão documentados em [Machine Learning](docs/ml/).

## 9. Consumer V2 e aplicação Streamlit

A Gold possui 254 atributos e representa a estrutura analítica ampla do projeto.

Entretanto, disponibilizar todos esses campos diretamente ao aplicativo aumentaria o acoplamento entre armazenamento, engenharia e apresentação.

Por esse motivo, foi criada uma camada específica de consumo:

`workspace.gold.bairroiq_frontend_v2`

A tabela privada possui **96 registros e 20 campos físicos**, incluindo metadados de auditoria.

### 9.1. Contrato do Consumer V2

O Consumer fornece as informações necessárias à aplicação.

Entre elas estão:

- Código oficial do distrito.
- Nome do distrito.
- Latitude e longitude.
- Identificador e descrição do perfil territorial.
- Indicadores de personalização.
- Informações complementares.
- Identificador de snapshot.
- Controle de publicação.
- Metadados de auditoria.

O aplicativo não precisa recalcular os percentis da Gold ou executar novamente o Machine Learning.

### 9.2. Dimensões de personalização

O aplicativo oferece quatro critérios principais.

| Critério | Campo |
|---|---|
| Verde e lazer | `green_leisure_score` |
| Segurança | `safety_score` |
| Mobilidade | `mobility_score` |
| Serviços públicos | `public_services_score` |

Esses índices utilizam escala relativa de 0 a 100.

Os pesos definidos pelo usuário determinam a importância relativa de cada critério na composição do ranking personalizado.

Empregos formais, densidade populacional e registros de roubos são apresentados como informações complementares.

Esses indicadores não entram automaticamente na pontuação ponderada das quatro dimensões.

### 9.3. Aplicativo privado integrado ao Databricks

O Streamlit V2 foi homologado em ambiente privado no Databricks.

Essa versão utiliza uma conexão autenticada com o SQL Warehouse para consultar o Consumer materializado.

A leitura verifica os contratos do snapshot e os metadados de auditoria.

O acesso permanece sujeito às permissões configuradas no ambiente.

A homologação privada ocorreu em 8 de novembro de 2026 e incluiu verificações de mapa, filtros, rankings, comparação e perfis.

### 9.4. Aplicativo público

**Acesso:** https://atlas-sampa.streamlit.app/

A versão pública utiliza o Streamlit Community Cloud.

O aplicativo consome uma exportação estática aprovada do Consumer V2, organizada em 96 registros e 15 campos agregados.

Os arquivos estão versionados no repositório:

`streamlit/bairroiq-streamlit-v2/data/public_consumer_v2.csv`

`streamlit/bairroiq-streamlit-v2/data/public_release.json`

O manifesto registra a autorização declarada para divulgação, a identificação do snapshot e os hashes de integridade.

O provedor público verifica o conteúdo antes de disponibilizá-lo à interface.

O aplicativo público não necessita de credenciais do Databricks, não acessa diretamente o SQL Warehouse e não executa consultas ao Lakehouse durante a navegação.

### 9.5. Preservação do Consumer original

O Consumer V2 privado mantém `publicacao_autorizada = false`.

Esse estado não foi alterado artificialmente para disponibilizar o aplicativo.

A autorização de exposição pública foi aplicada especificamente à exportação agregada, utilizando um manifesto separado.

Essa decisão preserva o contrato original e distingue a homologação privada da autorização de um produto público derivado.

### 9.6. Experiência responsiva

A aplicação possui uma camada de adaptação para telas menores, com ajustes de navegação, disposição de cartões, filtros e visualizações.

O código mobile está organizado em:

`streamlit/bairroiq-streamlit-v2/bairroiq/assets/mobile.css`

A arquitetura preserva o comportamento principal da versão desktop e adapta a apresentação aos dispositivos móveis.

A aplicação dispõe de cinco áreas principais:

1. Personalizar cenário.
2. Explorar / Mapa.
3. Comparar regiões.
4. Perfis Urbanos.
5. Fontes.

A utilização do QR Code permite acessar a mesma aplicação pública pelo celular, sem necessidade de cadastro.

**Documentação:** [Aplicação Streamlit V2](streamlit/bairroiq-streamlit-v2/README.md).

## 10. Arquitetura Lambda para atualização da SSP

A SSP disponibiliza arquivos anuais que podem receber atualizações e republicações.

Essas republicações podem conter novos registros e correções retroativas.

Um processo que apenas substituísse o arquivo anterior perderia informações sobre as mudanças ocorridas entre versões.

Para resolver esse problema, foi implementada uma arquitetura Lambda com armazenamento versionado da origem, recomputação Batch, cálculo de diferenças Speed e publicação de uma Serving reconciliada.

### 10.1. Coleta e versionamento

O coletor consulta a publicação da SSP por HTTPS.

Os arquivos são validados e preservados na Raw com identificação por SHA256.

Quando o conteúdo é idêntico ao de uma versão previamente armazenada, não há necessidade de criar uma nova cópia lógica.

O versionamento permite comparar publicações e reconstruir resultados anteriores.

### 10.2. Batch

A camada Batch recalcula a publicação completa.

As ocorrências são consolidadas por:

- Ano estatístico.
- Mês estatístico.
- Distrito.
- Categoria de ocorrência.

A estrutura de saída mantém as combinações esperadas para os distritos, meses e tipos de ocorrência identificados.

Essa estratégia permite reconstruir integralmente os indicadores a partir da versão da fonte.

### 10.3. Speed

A camada Speed identifica diferenças entre versões.

O processamento compara a multiplicidade de hashes dos registros.

Essa decisão evita pressupor que o número do boletim de ocorrência represente uma chave única global.

A comparação identifica inclusões, exclusões e alterações do conteúdo.

A Speed implementada não corresponde a um serviço de streaming contínuo.

Ela representa o processamento de diferenças entre publicações completas da fonte.

### 10.4. Serving

A Serving disponibiliza os resultados reconciliados.

A validação utiliza a identidade:

`Batch anterior + Speed = Batch atual`

As contagens são verificadas por chave de agregação.

A atualização do controle de publicação ocorre somente após a gravação e verificação dos resultados.

Essa abordagem reduz o risco de declarar uma versão concluída antes de sua disponibilização.

### 10.5. Objetos físicos

| Componente | Objeto |
|---|---|
| Bronze | `workspace.bronze.ssp_ingestao_v2` |
| Staging | `workspace.bronze.atlas_sampa_ssp_stage_v2` |
| Silver privada | `workspace.silver.atlas_sampa_ssp_v2` |
| Batch | `workspace.observability.atlas_sampa_ssp_batch_v1` |
| Speed | `workspace.observability.atlas_sampa_ssp_speed_v1` |
| Serving | `workspace.observability.atlas_sampa_ssp_serving_v1` |
| Controle de publicação | `workspace.observability.atlas_sampa_ssp_publication_v1` |

### 10.6. Resultados da execução

A execução auditada da arquitetura Lambda apresentou:

| Indicador | Resultado |
|---|---:|
| Ano estatístico | 2026 |
| Meses presentes | 9 |
| Distritos | 96 |
| Tipos de ocorrência | 2 |
| Linhas Batch | 1.728 |
| Linhas Serving | 1.728 |
| Ocorrências publicadas | 250.606 |
| Divergências Batch e Serving | 0 |
| Divergências de reconciliação | 0 |
| **Resultado** | **Aprovado** |

A validação demonstra consistência para a publicação auditada.

Isso não elimina a necessidade de novos testes quando a SSP modificar estrutura, conteúdo ou regras de disponibilização.

### 10.7. Por que a Lambda permanece desacoplada da Gold

O Atlas Sampa é uma plataforma de análise territorial, não um sistema de monitoramento criminal em tempo real.

Seus produtos analíticos são construídos com snapshots consistentes de indicadores que possuem diferentes referências temporais.

Uma nova publicação da SSP não deve provocar automaticamente a substituição de indicadores utilizados por modelos e consumidores já homologados.

A arquitetura separa duas responsabilidades.

A primeira é manter as publicações da fonte atualizadas, versionadas e auditáveis.

A segunda é decidir quando novas informações devem ser incorporadas ao produto analítico.

A Lambda atende à primeira responsabilidade.

A Gold e os consumidores seguem um processo de publicação independente e controlado.

Essa separação permite preservar a reprodutibilidade dos resultados, reduzir reprocessamentos desnecessários e evitar inconsistências temporais.

### 10.8. Frequência de atualização e impacto estatístico

Uma nova publicação da SSP pode acrescentar registros sem alterar substancialmente os indicadores relativos dos distritos.

Entretanto, esse comportamento não pode ser presumido.

O impacto depende da distribuição geográfica das ocorrências, das transformações aplicadas e da sensibilidade dos modelos.

O K-Means K9 apresentou separação limitada e estabilidade moderada.

Portanto, determinadas alterações nos dados podem modificar a composição dos agrupamentos.

A política arquitetural não afirma que novas informações sejam estatisticamente irrelevantes.

Ela estabelece que novas publicações devem ser avaliadas antes da promoção aos produtos analíticos.

Uma política de avaliação de impacto pode considerar mudanças nas taxas, nos rankings, na composição dos clusters e na consistência temporal.

Esse conjunto de critérios representa uma diretriz de governança, não uma automação de promoção já implementada.

### 10.9. Consistência temporal

A publicação auditada da Lambda possui nove meses estatísticos de 2026.

Alguns indicadores utilizados anteriormente na Gold consideram janelas de doze meses.

Substituir diretamente uma janela por outra produziria uma comparação temporal incompatível.

Além disso, a Gold, os resultados do Machine Learning, o Star Schema e o Consumer possuem identificadores e contratos associados a seus snapshots.

Uma nova versão da fonte pode exigir a reconstrução e a validação desses componentes.

Por esse motivo, a Serving da Lambda não substitui automaticamente os dados do aplicativo.

### 10.10. Execução sob demanda

O Job `atlas-sampa-ssp-lambda` possui configuração de agendamento mensal para o dia 10, às 10h, no fuso `America/Sao_Paulo`.

Entretanto, o agendamento permanece **PAUSED**.

A atualização pode ser executada manualmente quando houver necessidade de verificar uma nova publicação da SSP.

Essa decisão reduz consumo desnecessário de processamento e mantém o controle operacional em um ambiente de desenvolvimento.

A implantação do código da Lambda também é independente da sua execução.

A execução de uma nova publicação não autoriza automaticamente a atualização da Gold ou do aplicativo público.

**Documentação:** [Arquitetura Lambda SSP](barrioiq_pipeline/atlas_sampa/ssp/LAMBDA.md).

## 11. Governança, qualidade e observabilidade

O projeto utiliza mecanismos de governança para preservar rastreabilidade, qualidade e clareza sobre as limitações dos dados.

A implementação inclui contratos técnicos, documentação de metadados, controles de acesso, validações de integridade e registros de execução.

### 11.1. Catálogo e metadados

O Unity Catalog é utilizado para organizar as estruturas analíticas.

A Gold possui documentação de suas 254 colunas.

Os metadados incluem descrições, unidades, origens, regras de cálculo e limitações de interpretação.

A utilização de um catálogo reduz a dependência de conhecimento informal sobre o significado dos indicadores.

### 11.2. Contratos de dados

Cada camada possui expectativas explícitas sobre suas estruturas.

Entre os elementos verificados estão:

- Existência de campos obrigatórios.
- Tipos de dados esperados.
- Cardinalidade.
- Unicidade de identificadores.
- Ausência de nulos em campos críticos.
- Intervalos numéricos válidos.
- Consistência geográfica.
- Integridade de snapshots.
- Compatibilidade entre dados e consumidores.

Quando uma condição obrigatória não é atendida, o processamento deve falhar de forma explícita.

Essa abordagem reduz o risco de propagação silenciosa de inconsistências.

### 11.3. Data Quality

As regras de qualidade são aplicadas conforme as necessidades de cada camada.

Na ingestão, são verificadas estrutura e origem.

Na Silver, são verificadas padronização, correspondências e consistência territorial.

Na Gold, são verificados schema, cardinalidade e indicadores.

Nos produtos dimensionais, são analisadas integridade e compatibilidade dos snapshots.

No Consumer, são verificadas as condições necessárias para apresentação na interface.

Na Lambda, é executada a reconciliação algébrica entre Batch, Speed e Serving.

### 11.4. Versionamento e reprodutibilidade

O Delta Lake preserva histórico técnico das tabelas.

Hashes SHA256 identificam conteúdos e versões de dados.

Os produtos analíticos utilizam identificadores explícitos de snapshot.

Essa combinação permite relacionar resultados a versões específicas de suas fontes.

O snapshot público também possui um manifesto com informações de autorização e integridade.

Sua validação impede que modificações no arquivo publicado sejam aceitas silenciosamente.

### 11.5. Observabilidade

A observabilidade está distribuída entre os componentes do projeto.

Os processos de engenharia produzem logs e evidências de execução.

Os Jobs do Databricks permitem acompanhar histórico, falhas e resultados.

O GitHub Actions registra testes, validações e implantações.

O schema `workspace.observability` contém estruturas utilizadas pela arquitetura Lambda e por auditorias.

Entre os elementos de observabilidade estão:

- Logs de execução.
- Status dos Jobs.
- Contagens de registros.
- Validação de cardinalidade.
- Resultados de contratos.
- Histórico Delta.
- Hashes de conteúdo.
- Reconciliação de publicações.
- Resultados dos workflows de CI/CD.
- Evidências de alterações no código.

A observabilidade implementada é adequada ao ambiente de desenvolvimento e homologação.

Não deve ser confundida com uma operação produtiva de monitoramento contínuo com garantias formais de disponibilidade.

### 11.6. Segurança e uso responsável

O projeto utiliza fontes públicas, mas a origem pública dos dados não elimina a necessidade de avaliar sua exposição.

A aplicação pública disponibiliza informações agregadas por distrito.

Ela não apresenta registros individuais de boletins de ocorrência ou endereços de pessoas.

O pipeline Lambda evita incluir informações detalhadas de ocorrências em logs de auditoria.

Os objetos privados do Databricks permanecem sujeitos às permissões do ambiente.

A publicação externa utiliza um conjunto específico de campos agregados previamente autorizado.

O controle lógico de publicação não substitui as permissões efetivas de infraestrutura.

## 12. CI/CD e infraestrutura como código

O projeto utiliza GitHub Actions para validações automatizadas e controle das alterações.

Os workflows contemplam componentes de engenharia, qualidade, modelagem, Machine Learning, aplicação e infraestrutura.

### 12.1. Integração contínua

Os processos de CI executam verificações antes da integração de código.

Essas verificações incluem testes automatizados, validação sintática e conferência de contratos.

O objetivo é detectar incompatibilidades antes que uma alteração seja incorporada à branch principal.

A aprovação dos testes não substitui a homologação funcional no ambiente de execução.

### 12.2. Databricks Asset Bundles

Os Jobs são definidos por arquivos versionados.

O Databricks Asset Bundles permite validar e implantar configurações de maneira controlada.

Essa abordagem reduz divergências entre a configuração dos recursos e o código disponível no repositório.

A arquitetura Lambda possui um Bundle independente do pipeline principal.

A separação evita que alterações específicas do processamento SSP modifiquem inadvertidamente os demais componentes.

### 12.3. Terraform

O Terraform é utilizado para declarar recursos de infraestrutura.

O código contempla schemas das camadas analíticas, estruturas de observabilidade e recursos de armazenamento.

O HCP Terraform é utilizado no gerenciamento do estado e dos processos associados à infraestrutura como código.

Os workflows executam verificações como formatação, inicialização e validação das configurações.

Essas verificações demonstram consistência do código declarativo, mas não comprovam isoladamente a criação de todos os recursos.

A comprovação de provisionamento deve considerar o estado da infraestrutura e os recursos existentes no ambiente.

### 12.4. Controle entre deploy e execução

O projeto separa validação, implantação e execução.

Um commit não precisa provocar automaticamente uma nova carga de dados.

A mesma lógica é aplicada à publicação analítica.

A atualização de uma fonte não precisa modificar automaticamente um produto utilizado por usuários.

Essa decisão favorece rastreabilidade, reprodutibilidade e controle operacional.

## 13. Como reproduzir e validar

A reprodução do projeto pode ocorrer por testes locais com dados sintéticos ou por validação no ambiente Databricks utilizando as tabelas reais.

Os testes sintéticos verificam contratos e comportamento do código.

Eles não substituem as auditorias dos dados reais.

### 13.1. Repositório

Código-fonte:

https://github.com/DCosso/bairroiq

Os diretórios principais contêm scripts de engenharia, arquivos SQL, notebooks, testes e definições de infraestrutura.

### 13.2. Testes automatizados

Os testes são executados pelo GitHub Actions.

O repositório inclui validações de código Python, contratos de dados, modelagem, integração da aplicação e configuração de infraestrutura.

Os workflows representam a referência principal para reprodução dos testes com as dependências e os comandos esperados.

### 13.3. Notebooks técnicos

Os notebooks disponíveis no repositório incluem:

- `notebooks/BairroIQ.ipynb`
- `notebooks/EDA.ipynb`
- `notebooks/00_environment_smoke.ipynb`

Esses arquivos documentam etapas de exploração, desenvolvimento e verificação do ambiente.

O repositório também contém scripts e runners utilizados na implementação dos pipelines.

### 13.4. Aplicação demonstrativa local

O aplicativo pode ser executado localmente utilizando um provedor de dados demonstrativos.

O modo `sample` utiliza registros sintéticos e não representa os indicadores reais dos 96 distritos.

### 13.5. Aplicação pública com dados reais

A versão pública utiliza o provedor:

`BAIRROIQ_DATA_PROVIDER=public_snapshot`

O conjunto de dados aprovado está disponível no diretório:

`streamlit/bairroiq-streamlit-v2/data/`

A aplicação valida o manifesto e a integridade do arquivo antes de disponibilizar os dados.

O provedor público não necessita de credenciais do Databricks.

**Acesso:** https://atlas-sampa.streamlit.app/

### 13.6. Aplicação privada integrada

A execução privada pode utilizar o provedor Databricks, com configuração de acesso e permissões apropriadas.

Esse modo consulta o Consumer V2 materializado.

A configuração de prévia interna não deve ser utilizada como mecanismo de liberação pública.

### 13.7. Validação da Lambda

A auditoria da Lambda deve verificar a publicação selecionada, as contagens consolidadas e a reconciliação entre Batch, Speed e Serving.

O apontador de publicação identifica a versão vigente.

A versão atual não deve ser inferida apenas pela ordenação de hashes ou pela data de gravação.

Os procedimentos estão documentados em [LAMBDA.md](barrioiq_pipeline/atlas_sampa/ssp/LAMBDA.md).

## 14. Organização do repositório

A estrutura do repositório separa desenvolvimento, dados, documentação, aplicação e automação.

**Diretórios e componentes principais:**

| Diretório | Conteúdo |
|---|---|
| `.github/workflows/` | CI/CD e validações automatizadas |
| `infra/` | Infraestrutura declarativa |
| `EDA/` | Análises exploratórias |
| `notebooks/` | Notebooks técnicos |
| `barrioiq_pipeline/` | Engenharia de dados e processamento |
| `barrioiq_pipeline/atlas_sampa/ssp/` | Arquitetura Lambda SSP |
| `docs/arquitetura/` | Documentação arquitetural |
| `docs/consumo/` | Contratos e auditorias dos consumidores |
| `docs/governanca/` | Governança e validações |
| `docs/ml/` | Metodologia e resultados de Machine Learning |
| `docs/modelagem/` | Modelagem dimensional |
| `streamlit/bairroiq-streamlit-v2/` | Aplicativo Atlas Sampa |
| `tests/` | Testes automatizados |

### Documentação técnica

- [Dicionário completo da Gold](docs/dicionario_gold_distritos_wide.md)
- [Contrato estruturado da Gold](docs/dicionario_gold_distritos_wide.json)
- [Metodologia do catálogo de perfis](docs/ml/metodologia_catalogo_perfis_v3.md)
- [Comparação entre algoritmos](docs/ml/metodologia_comparacao.md)
- [Revisão semântica dos perfis](docs/governanca/encerramento_auditoria_semantica_v3.md)
- [Contrato do Star Schema Delta](docs/modelagem/star_schema_v1_delta_contrato.md)
- [Auditoria do Consumer V2](docs/consumo/BairroIQ_Frontend_V2_Auditoria_Leitura.sql)
- [Aplicação Streamlit V2](streamlit/bairroiq-streamlit-v2/README.md)
- [Arquitetura Lambda SSP](barrioiq_pipeline/atlas_sampa/ssp/LAMBDA.md)

## 15. Responsabilidades técnicas e colaboração

O desenvolvimento do Atlas Sampa reúne atividades de engenharia de dados, Analytics, ciência de dados, desenvolvimento de aplicações e DataOps.

### Engenharia de dados

Responsável por ingestão, transformação, padronização, modelagem, versionamento e qualidade dos dados.

### Analytics

Responsável pela definição dos indicadores, regras de interpretação, unidades e análises territoriais.

### Ciência de dados

Responsável pela seleção de variáveis, preparação dos dados, experimentação de algoritmos e avaliação dos perfis territoriais.

### Desenvolvimento de aplicação

Responsável pela organização da experiência do usuário, visualização, navegação, filtros, comparações e adaptação mobile.

### DataOps e plataforma

Responsável por integração contínua, infraestrutura como código, automação, observabilidade e controle de implantação.

Essas responsabilidades não exigem necessariamente um profissional exclusivo por função.

A utilização de contratos e versionamento facilita a colaboração, a revisão cruzada e a integração das entregas.

## 16. Limitações e critérios de uso

O Atlas Sampa é uma plataforma de exploração territorial baseada em dados públicos e indicadores agregados.

A aplicação não oferece previsão individual de criminalidade, avaliação de imóveis, garantia de disponibilidade de serviços ou determinação universal de qual região é melhor.

Os indicadores apresentam limitações de período, cobertura e metodologia.

A cobertura imobiliária documentada é parcial.

Determinados indicadores socioeconômicos utilizam referências históricas.

A taxa de registros criminais não representa integralmente todos os eventos de criminalidade.

Os nove perfis territoriais representam classificações exploratórias produzidas por Machine Learning não supervisionado.

As métricas demonstram limitações de separação e estabilidade, que devem ser consideradas na interpretação.

Os nomes comerciais dos perfis não representam certificações de segurança, qualidade de vida ou disponibilidade de oportunidades.

A personalização do aplicativo utiliza índices relativos e pesos definidos pelos usuários.

Seus resultados não constituem avaliações oficiais dos distritos.

### 16.1. Limitações da publicação pública

A aplicação pública utiliza um snapshot estático aprovado.

Isso significa que os dados não são atualizados automaticamente durante a navegação.

A execução de novos processos de engenharia não altera imediatamente os indicadores apresentados.

Novas versões podem ser disponibilizadas após validação, versionamento e autorização.

O aplicativo público utiliza os dados agregados aprovados, sem acesso direto às tabelas privadas do Databricks.

A disponibilização pública de novos indicadores exige avaliação específica de qualidade, exposição e interpretação.

### 16.2. Limitações da arquitetura Lambda

A arquitetura Lambda possui uma publicação real e reconciliada da SSP.

Entretanto, seu caminho Speed não corresponde a streaming contínuo de eventos em tempo real.

Ele calcula diferenças entre versões completas da fonte.

A Lambda permanece desacoplada da Gold e não realiza promoção automática aos produtos analíticos.

Seu agendamento permanece pausado, com execução sob demanda.

### 16.3. Política de atualização

O processamento de uma nova versão e a decisão de publicar um novo produto analítico são eventos distintos.

Essa separação permite preservar a consistência dos snapshots, controlar o consumo computacional e avaliar alterações antes de incorporá-las aos indicadores e modelos.

A política não pressupõe que os resultados permaneçam estatisticamente invariáveis.

Mudanças relevantes podem exigir novas materializações, experimentos e validações.

### 16.4. Considerações finais

O Atlas Sampa demonstra uma arquitetura integrada de dados que combina:

- Ingestão multifuente.
- Processamento e padronização territorial.
- Arquitetura Lakehouse.
- Modelagem dimensional.
- Machine Learning não supervisionado.
- Arquitetura Lambda.
- Governança e qualidade.
- Observabilidade.
- CI/CD e infraestrutura como código.
- Aplicação web interativa.
- Publicação de dados agregados com controle de versão.

A solução preserva a separação entre processamento, análise e consumo, permitindo que os resultados sejam rastreáveis e que a evolução do produto ocorra de maneira controlada.
