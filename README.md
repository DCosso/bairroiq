# Atlas Sampa

**Plataforma de inteligência territorial para explorar e comparar os 96 distritos administrativos da cidade de São Paulo.**

O **Atlas Sampa** transforma dados públicos de origens distintas em uma experiência de análise territorial. O produto permite explorar características dos distritos, comparar indicadores e ajustar a importância de critérios como mobilidade, serviços públicos, verde e lazer e ocorrências criminais registradas. O objetivo é tornar diferenças territoriais compreensíveis, sem apresentar uma classificação universal de melhores e piores regiões.

O código está organizado no repositório técnico **BairroIQ**, que reúne engenharia de dados, modelagem analítica, Machine Learning, infraestrutura, automação, governança e aplicação web. A distinção entre o nome comercial Atlas Sampa e o identificador técnico BairroIQ preserva a rastreabilidade dos artefatos e contratos já implementados, sem exigir alterações artificiais nas estruturas existentes.

**Estado da implementação em novembro de 2026:** Lakehouse com dados reais implementado, Gold distrital auditada, Star Schema Delta materializado, modelos de agrupamento territorial comparados, Consumer V2 materializado, aplicativo Streamlit V2 homologado privadamente e arquitetura Lambda da SSP implementada com publicação reconciliada.

A solução adota processamento sob demanda e publicação analítica controlada. O processamento de novas versões da fonte não implica atualização automática da Gold, dos modelos ou do aplicativo. Essa separação é intencional, pois permite preservar a reprodutibilidade dos resultados e avaliar o impacto de alterações antes de incorporá-las ao produto.

A disponibilização pública do aplicativo não está autorizada nesta versão, e o agendamento da Lambda permanece pausado.

## Acesse o Atlas Sampa

🌐 **[Abrir aplicativo interativo](https://atlas-sampa.streamlit.app/)**

Explore os 96 distritos de São Paulo, personalize suas prioridades, compare regiões e conheça os nove perfis territoriais identificados por Machine Learning.

O aplicativo é público, gratuito e funciona em computadores e celulares, sem necessidade de cadastro.

A versão pública utiliza um snapshot estático, auditado e autorizado dos indicadores territoriais. A arquitetura de dados permanece no Databricks, com atualizações sob demanda.


## 1. Problema de negócio

A escolha de uma região para morar, investir ou estabelecer atividades depende de fatores que dificilmente podem ser avaliados por um único indicador. Mobilidade, infraestrutura urbana, serviços públicos, densidade populacional, dinâmica imobiliária e ocorrências criminais representam dimensões distintas do território.

Embora existam fontes públicas relevantes para essas análises, os dados são disponibilizados em formatos diferentes, com granularidades geográficas incompatíveis e períodos de referência próprios.

Essa fragmentação dificulta comparações consistentes e frequentemente leva à utilização isolada de indicadores que não representam integralmente as condições de uma região.

O Atlas Sampa foi concebido para reduzir essas limitações por meio de uma arquitetura capaz de integrar dados heterogêneos, padronizar referências territoriais e disponibilizar informações analíticas em uma interface compreensível.

A solução adota os **96 distritos administrativos oficiais do município de São Paulo** como unidade de análise.

Essa escolha foi motivada pela existência de códigos geográficos estáveis, limites territoriais verificáveis e disponibilidade de indicadores públicos associados à divisão administrativa.

A utilização de distritos também reduz a ambiguidade provocada pelos nomes de bairros comerciais, que podem variar entre fontes e não necessariamente possuem limites geográficos equivalentes.

O produto não pretende determinar qual distrito é universalmente melhor. Em vez disso, disponibiliza informações comparáveis e permite que diferentes pessoas atribuam pesos distintos aos critérios que consideram importantes.

Essa abordagem separa a interpretação dos dados da preferência individual, evitando transformar indicadores estatísticos em recomendações absolutas.

## 2. Resultados técnicos e escopo validado

| Componente | Resultado |
|---|---|
| Abrangência territorial | 96 distritos oficiais de São Paulo |
| Tabela analítica principal | `workspace.gold.distritos_wide` |
| Granularidade da Gold | Uma linha por distrito |
| Atributos na Gold | 254 colunas |
| Coordenadas geográficas | 96 distritos com latitude e longitude |
| Modelo dimensional | 4 dimensões e 3 tabelas de fatos |
| Machine Learning | K-Means com 9 grupos, comparado com Ward |
| Consumer do aplicativo | `workspace.gold.bairroiq_frontend_v2` |
| Estrutura do Consumer V2 | 96 registros e 20 campos |
| Aplicativo | Streamlit V2 homologado privadamente |
| Arquitetura Lambda | Batch, Speed e Serving no Databricks |
| Publicação SSP validada | 250.606 ocorrências |
| Cobertura SSP publicada | 96 distritos, 9 meses e 2 categorias |
| Reconciliação Lambda | 1.728 linhas Batch e Serving, com 0 divergências |
| CI/CD | GitHub Actions e Databricks Asset Bundles |
| Infraestrutura como código | Terraform e HCP Terraform |
| Observabilidade | Logs, auditorias, histórico de Jobs e tabelas Delta |
| Política de atualização | Processamento sob demanda e publicação controlada |

Os resultados representam diferentes produtos de dados e não devem ser interpretados como se todos estivessem associados a uma mesma data de referência.

A Gold consolida os indicadores disponíveis no momento da construção de seu snapshot. A Serving da Lambda representa uma publicação independente e versionada da SSP.

Essa separação preserva a consistência entre dados, modelos e consumidores analíticos.

## 3. Arquitetura da solução

O Atlas Sampa utiliza uma arquitetura **Data Lakehouse baseada no padrão Medallion**, implementada no Databricks com Apache Spark, Delta Lake e Unity Catalog.

O fluxo principal organiza os dados nas camadas Raw, Bronze, Silver e Gold. A partir da Gold são disponibilizados modelos dimensionais, experimentos de Machine Learning e uma camada específica de consumo para o aplicativo.

Paralelamente, foi implementada uma arquitetura Lambda para processar versões da base de ocorrências criminais da SSP.

A coexistência dessas duas arquiteturas não representa duplicação desnecessária de componentes. Elas atendem a responsabilidades distintas.

O Lakehouse organiza a ingestão, transformação, qualidade e disponibilização analítica de múltiplas fontes. A Lambda resolve especificamente o problema de processar republicações de dados, identificar alterações e reconciliar diferentes versões de uma mesma fonte.

### 3.1. Por que utilizar uma arquitetura Lakehouse

A escolha do Lakehouse foi motivada pela necessidade de trabalhar com dados heterogêneos, incluindo arquivos tabulares, indicadores estatísticos, dados geográficos e informações estruturadas.

Uma arquitetura baseada exclusivamente em banco de dados relacional exigiria maior adaptação inicial dos diferentes formatos de entrada. Por outro lado, um Data Lake sem mecanismos de controle transacional dificultaria a garantia de consistência entre versões e processos.

O Lakehouse combina a flexibilidade de armazenamento de um Data Lake com recursos de organização, versionamento e consulta associados a ambientes analíticos estruturados.

O **Delta Lake** foi escolhido por oferecer controle transacional por tabela, histórico de versões e operações verificáveis de escrita.

O **Apache Spark**, por sua vez, fornece um mecanismo comum para processamento, transformação e validação dos dados, permitindo utilizar Python e SQL na mesma arquitetura.

O **Unity Catalog** organiza os objetos, seus metadados, contratos e permissões de acesso, reduzindo a dependência de conhecimento informal sobre o significado de cada tabela.

### 3.2. Separação entre processamento e publicação

Uma decisão importante foi não tratar a conclusão de uma ingestão como autorização automática para atualizar todos os consumidores.

O Atlas Sampa trabalha com indicadores que possuem diferentes frequências de atualização e diferentes períodos estatísticos.

Enquanto os dados censitários apresentam ciclos longos de atualização, bases imobiliárias e registros de ocorrências podem ser modificados com maior frequência.

Entretanto, **a frequência de atualização de uma fonte não é necessariamente igual à frequência necessária de atualização do produto analítico**.

Um novo arquivo pode conter registros adicionais sem alterar substancialmente os indicadores consolidados. Em outros casos, uma alteração relativamente pequena pode afetar posições em rankings ou a composição de determinados clusters.

Por esse motivo, o processamento de novas versões foi desacoplado da publicação da Gold e dos consumidores.

O objetivo não é presumir que mudanças frequentes sejam estatisticamente irrelevantes, mas permitir que sua relevância seja avaliada antes da promoção.

Essa separação também reduz reprocessamentos desnecessários, controla o consumo computacional e preserva a capacidade de reproduzir resultados anteriores.

## 4. Tecnologias e decisões técnicas

| Tecnologia | Aplicação e justificativa |
|---|---|
| Python | Ingestão, validações, transformação e processamento geoespacial |
| SQL | Transformações declarativas, agregações e auditorias |
| Apache Spark e PySpark | Processamento distribuído e integração das camadas |
| Delta Lake | Persistência transacional, histórico e versionamento |
| Databricks | Ambiente integrado de processamento e execução |
| Unity Catalog | Organização, metadados e controle de acesso |
| GeoPandas | Operações espaciais e associação de coordenadas aos distritos |
| OpenStreetMap | Apoio à correspondência territorial de localidades imobiliárias |
| scikit-learn | Modelagem e avaliação de agrupamentos territoriais |
| GitHub | Versionamento, revisão e integração de código |
| GitHub Actions | Testes automatizados, validação e deploy controlado |
| Databricks Asset Bundles | Definição declarativa de Jobs e distribuição de código |
| Terraform | Definição de recursos de infraestrutura |
| HCP Terraform | Gerenciamento do estado e execução de infraestrutura como código |
| Streamlit | Desenvolvimento da experiência web |
| Plotly | Visualização interativa e comparação de indicadores |

A seleção das tecnologias priorizou integração entre componentes, reprodutibilidade, facilidade de validação e compatibilidade com os recursos de desenvolvimento disponíveis.

O projeto não depende de uma infraestrutura dedicada de streaming contínuo para atender ao comportamento das fontes utilizadas.

Essa decisão reduz a complexidade operacional, embora não elimine a necessidade de validar custos de processamento, SQL Warehouse e hospedagem da aplicação em cada ambiente.

## 5. Fontes de dados e integração territorial

O produto integra informações de diferentes fontes, preservando suas características e limitações metodológicas.

| Fonte | Dados utilizados | Considerações |
|---|---|---|
| IBGE | População, domicílios, densidade e malha territorial | Referência oficial dos distritos |
| GeoSampa | Equipamentos e infraestrutura urbana | Equipamentos cadastrados não representam necessariamente capacidade de atendimento |
| ObservaSampa | Indicadores socioeconômicos e urbanos | Períodos de referência variam por indicador |
| SSP-SP | Ocorrências criminais | Registros administrativos não equivalem à totalidade dos eventos reais |
| Mercado imobiliário | Estoque e indicadores de anúncios | Cobertura geográfica parcial |
| OpenStreetMap | Referências geográficas de localidades | Utilizado como apoio à associação territorial |

### 5.1. Padronização geográfica

Um dos principais desafios foi integrar fontes que utilizam diferentes identificadores territoriais.

A divisão oficial do IBGE considera 96 distritos administrativos. Já algumas bases imobiliárias utilizam nomes comerciais de bairros, que não possuem correspondência direta com os distritos.

Uma associação exclusivamente textual poderia produzir correspondências incorretas e distorcer os indicadores.

Para reduzir esse risco, foi desenvolvido um processo de identificação de localidades, consulta a referências geográficas e validação explícita das associações.

Na última auditoria documentada foram identificadas:

| Indicador | Resultado |
|---|---:|
| Localidades imobiliárias | 1.626 |
| Correspondências aprovadas | 93 |
| Estoque total | 70.706 |
| Estoque associado | 28.085 |
| Cobertura do estoque | 39,72% |

A cobertura parcial foi mantida explicitamente.

Não foram realizadas atribuições arbitrárias dos imóveis sem correspondência aprovada, pois aumentar artificialmente a cobertura comprometeria a confiabilidade analítica.

### 5.2. Associação espacial das ocorrências

A associação geográfica das ocorrências utiliza coordenadas e a malha distrital oficial.

As geometrias são verificadas quanto à validade, sistema de referência e correspondência com os códigos oficiais dos distritos.

O processamento dos centroides utiliza **EPSG:31983** para cálculos métricos, com transformação posterior para **EPSG:4326**, utilizado na representação geográfica.

Essa estratégia evita realizar cálculos de centroide diretamente sobre coordenadas expressas em graus.

Registros sem correspondência espacial válida são preservados para auditoria e não são distribuídos arbitrariamente entre distritos.

## 6. Engenharia de dados e arquitetura Medallion

### 6.1. Raw e Bronze

A camada Raw preserva arquivos de origem e metadados de coleta.

A Bronze representa a primeira estruturação dos dados, mantendo informações suficientes para reconstruir a transformação realizada nas camadas seguintes.

Essa separação foi adotada porque arquivos públicos podem ser republicados com alterações retroativas.

Sobrescrever arquivos anteriores impediria identificar diferenças entre versões e dificultaria a reprodução de resultados históricos.

Quando aplicável, utiliza-se SHA256 para identificar o conteúdo da publicação, independentemente do nome do arquivo ou da data em que foi coletado.

A combinação de identificadores de versão e informações de origem permite controlar reexecuções e distinguir registros pertencentes a publicações diferentes.

### 6.2. Silver

A camada Silver concentra tratamento, padronização e enriquecimento.

Nela são executadas verificações de tipos, chaves, cardinalidade, cobertura e consistência geográfica.

Os processos foram separados por fonte porque cada conjunto de dados possui regras próprias.

Essa decisão reduz o acoplamento entre integrações e permite identificar falhas específicas sem comprometer silenciosamente as demais fontes.

Valores ausentes não são automaticamente convertidos em zero, pois ausência de informação e valor numérico nulo podem possuir significados diferentes.

### 6.3. Gold Wide

A principal tabela analítica é:

`workspace.gold.distritos_wide`

Ela possui **96 registros e 254 atributos**, mantendo uma linha por distrito administrativo.

A escolha de uma Wide Table foi motivada pelo padrão de consumo analítico do produto.

Consultas territoriais frequentemente precisam recuperar diversas características de um distrito simultaneamente. Para Machine Learning, também é conveniente trabalhar com observações organizadas em linhas e atributos disponíveis em colunas.

Uma estrutura ampla facilita esse tipo de consumo e reduz a necessidade de reconstruir repetidamente relações entre tabelas durante os experimentos.

A chave territorial é o código oficial `CD_DIST`, evitando dependência de nomes que possam apresentar diferenças de grafia.

### 6.4. Temporalidade da Gold

A Gold representa uma fotografia analítica construída com os indicadores disponíveis nas fontes.

Ela não possui uma única data estatística válida para todos os atributos.

Dados censitários, indicadores socioeconômicos, ocorrências criminais e informações imobiliárias podem possuir períodos distintos.

Criar uma coluna universal com a data da execução produziria uma interpretação incorreta, pois a data do processamento não corresponde necessariamente ao período de observação.

Por esse motivo, a Gold preserva os indicadores consolidados sem fabricar uma referência temporal única.

O histórico técnico do Delta Lake permite rastrear versões da tabela, mas não substitui a documentação dos períodos estatísticos de cada fonte.

O dicionário de dados detalha as definições, unidades, origens, cálculos e limitações das 254 colunas.

**Documentação:** [Dicionário completo da Gold](docs/dicionario_gold_distritos_wide.md).

## 7. Modelagem dimensional: Star Schema

A Wide Table foi construída para facilitar consultas territoriais amplas e experimentos analíticos.

Entretanto, ela não substitui uma modelagem dimensional apropriada para análises OLAP.

Por essa razão, o Atlas Sampa também possui um modelo dimensional materializado em Delta Lake, organizado como uma constelação de fatos.

A modelagem permite representar separadamente distritos, indicadores, perfis e prioridades, preservando os relacionamentos e a granularidade de cada estrutura.

| Tabela | Responsabilidade | Registros |
|---|---|---:|
| `bairroiq_dim_snapshot` | Controle de snapshots | 1 |
| `bairroiq_dim_distrito` | Identificação dos distritos | 96 |
| `bairroiq_dim_perfil` | Cadastro dos perfis | 9 |
| `bairroiq_dim_indicador` | Metadados dos indicadores | 11 |
| `bairroiq_fato_distrito_indicador` | Indicadores por distrito | 1.056 |
| `bairroiq_fato_distrito_perfil` | Associação aos perfis | 96 |
| `bairroiq_fato_prioridade_ocorrencias` | Prioridade relativa de ocorrências | 96 |
| **Total** | **4 dimensões e 3 fatos** | **1.365** |

A utilização do identificador `snapshot_id` nas relações evita combinar registros produzidos a partir de fotografias diferentes.

A dimensão de snapshot é registrada somente após as validações das demais estruturas, funcionando como marcador de conclusão.

Essa estratégia reduz o risco de consumo de materializações incompletas, embora as escritas nas diferentes tabelas não constituam uma única transação.

Também foi evitada a criação de uma dimensão calendário artificial a partir da data de execução, já que a Gold contém indicadores de períodos distintos.

Uma consulta OLAP sobre o modelo pode recuperar indicadores, distritos e unidades mantendo a rastreabilidade:

```sql
SELECT
    d.NM_DIST AS distrito,
    i.rotulo AS indicador,
    i.unidade,
    f.valor_numerico
FROM workspace.gold.bairroiq_fato_distrito_indicador f
JOIN workspace.gold.bairroiq_dim_distrito d
    ON f.snapshot_id = d.snapshot_id
   AND f.CD_DIST = d.CD_DIST
JOIN workspace.gold.bairroiq_dim_indicador i
    ON f.snapshot_id = i.snapshot_id
   AND f.indicador_sk = i.indicador_sk
ORDER BY distrito, indicador;
```

O contrato de materialização e as regras de integridade estão documentados em [Star Schema Delta](docs/modelagem/star_schema_v1_delta_contrato.md).

## 8. Machine Learning e perfis territoriais

O componente de Machine Learning tem como objetivo identificar semelhanças entre os distritos administrativos.

O projeto não dispõe de uma variável objetivo que permita determinar, de forma confiável, qual região seria ideal para determinada pessoa.

Criar rótulos supervisionados sem uma referência verificável introduziria premissas subjetivas no treinamento.

Por esse motivo, a abordagem selecionada foi **clusterização não supervisionada**.

Foram comparados os algoritmos **K-Means** e **agrupamento hierárquico Ward**, utilizando variáveis padronizadas e avaliações de diferentes quantidades de grupos.

### 8.1. Por que comparar K-Means e Ward

K-Means e Ward utilizam abordagens diferentes para organizar observações em grupos.

O K-Means busca centros representativos e atribui observações conforme a distância a esses centros.

Ward constrói agrupamentos hierárquicos por fusões sucessivas, procurando controlar o aumento da variabilidade interna.

A comparação entre ambos permite avaliar como diferentes estratégias de agrupamento respondem ao conjunto de características territoriais.

Foram analisados valores de `K` entre 2 e 12, considerando métricas de separação, distribuição dos grupos, estabilidade e interpretabilidade.

A seleção não foi determinada exclusivamente pelo maior valor de Silhouette.

### 8.2. Por que escolhemos K-Means com nove grupos

O produto tinha como objetivo inicial oferecer aproximadamente dez perfis territoriais.

Entretanto, esse número representava uma preferência de experiência do usuário, não uma quantidade de agrupamentos naturais previamente comprovada.

Nos experimentos com dez grupos surgiram agrupamentos muito pequenos, incluindo grupos unitários.

Isso dificultaria a interpretação e poderia criar categorias pouco representativas.

A configuração candidata **K-Means K9** apresentou uma distribuição de 6 a 22 distritos por grupo, sem grupos unitários e com somente três observações apresentando Silhouette individual negativa.

Além disso, K-Means oferece vantagens operacionais para classificar novas observações quando o tratamento dos dados e os parâmetros do modelo são preservados.

O algoritmo Ward apresentou resultados superiores em algumas métricas, especialmente estabilidade e Davies-Bouldin na configuração comparada.

Portanto, a escolha do K-Means não representa superioridade estatística universal.

Ela representa um compromisso entre granularidade do produto, distribuição dos grupos, facilidade operacional e interpretabilidade.

### 8.3. Avaliação dos modelos

| Métrica | Interpretação | K-Means K9 | Ward K8 |
|---|---|---:|---:|
| Silhouette | Coesão e separação, quanto maior melhor | 0,194467 | 0,193960 |
| Davies-Bouldin | Similaridade entre grupos, quanto menor melhor | 1,334164 | 1,202354 |
| Calinski-Harabasz | Relação entre dispersão interna e entre grupos | 27,193823 | Não consolidado nesta comparação |
| ARI mediana | Estabilidade da classificação sob reamostragem | 0,470918 | 0,629504 |
| Menor grupo | Número mínimo de distritos em um cluster | 6 | 4 |
| Maior grupo | Número máximo de distritos em um cluster | 22 | 23 |

As métricas correspondem às configurações documentadas dos experimentos e incluem diferenças de tratamento de variáveis. Portanto, a comparação não isola exclusivamente o efeito do algoritmo.

O valor de Silhouette do K-Means K9 indica separação limitada entre grupos.

A estabilidade ARI também revela sensibilidade à composição dos dados.

Essas limitações fazem parte da interpretação do modelo e não devem ser ocultadas.

### 8.4. Perfis territoriais

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

Os perfis são classificações exploratórias e não representam notas de qualidade territorial.

O perfil associado a menores índices de ocorrências não significa ausência de criminalidade nem garante que todos os seus distritos apresentem taxas inferiores em qualquer indicador isolado.

Da mesma forma, o perfil relacionado a empregos utiliza informações históricas e não representa necessariamente a disponibilidade atual de vagas.

Na auditoria foram identificados três distritos com Silhouette individual negativa: Mooca, Socorro e Lajeado.

Essas observações permaneceram nas classificações originais do algoritmo, sem realocação manual para melhorar artificialmente os resultados.

A metodologia e os resultados estão documentados em [Machine Learning](docs/ml/).

## 9. Consumer V2 e aplicação Streamlit

O aplicativo não consulta diretamente os 254 atributos da Gold.

Embora essa estrutura seja adequada para análises amplas, disponibilizar todo o seu conteúdo à interface aumentaria o acoplamento entre armazenamento, transformação e apresentação.

Por isso, foi materializada uma camada específica de consumo:

`workspace.gold.bairroiq_frontend_v2`

A tabela possui **96 registros e 20 campos**, incluindo métricas utilizadas na interface e metadados técnicos de auditoria.

Essa estrutura simplifica as consultas, estabiliza o contrato de dados e facilita a validação antes da apresentação das informações ao usuário.

O Consumer V1 permanece preservado como artefato anterior, enquanto o MVP homologado utiliza o Consumer V2.

### 9.1. Personalização da análise

A aplicação utiliza quatro critérios principais:

| Critério | Campo |
|---|---|
| Verde e lazer | `green_leisure_score` |
| Segurança | `safety_score` |
| Mobilidade | `mobility_score` |
| Serviços públicos | `public_services_score` |

Esses índices são disponibilizados em escala relativa de 0 a 100.

A personalização ocorre por meio de pesos definidos na interface.

Empregos formais, densidade populacional e taxas de roubos são apresentados como informações complementares, sem compor automaticamente os quatro critérios ponderados.

Essa separação evita misturar unidades físicas com indicadores relativos.

Os pesos não alteram os dados armazenados, não modificam a Gold e não reexecutam os modelos de Machine Learning.

O ranking é produzido a partir das preferências escolhidas pelo usuário e não constitui uma classificação oficial de qualidade de vida.

### 9.2. Funcionalidades implementadas

O MVP possui cinco experiências principais.

1. **Personalizar cenário:** definição de prioridades e pesos para os critérios territoriais.
2. **Explorar:** visualização dos 96 distritos, filtros e ranking personalizado.
3. **Comparar regiões:** análise de indicadores de diferentes distritos.
4. **Perfis urbanos:** exploração dos grupos identificados pelo Machine Learning.
5. **Fontes:** apresentação das origens e limitações dos indicadores.

A interface utiliza Streamlit e Plotly, com geometria distrital oficial disponível no projeto.

O acesso aos dados reais ocorre por uma integração de leitura com o Databricks SQL Warehouse.

Na homologação privada de 8 de novembro de 2026 foram validados mapa, filtros, ranking, comparação e visualização dos perfis.

A aplicação foi interrompida após a demonstração.

O Consumer mantém `publicacao_autorizada = false`. A prévia privada exige configuração e permissões específicas, e sua existência não representa autorização para publicação pública.

As instruções e os contratos da aplicação estão disponíveis em [Streamlit V2](streamlit/bairroiq-streamlit-v2/README.md).

## 10. Arquitetura Lambda para atualização da SSP

A SSP disponibiliza arquivos anuais que podem ser republicados ao longo do tempo.

Essas republicações podem incluir novos meses estatísticos e correções de registros anteriores.

Um processo que apenas substituísse o arquivo anterior perderia informações importantes sobre o histórico das alterações.

Para resolver esse problema foi implementada uma arquitetura Lambda com versionamento da origem, recomputação Batch, cálculo de diferenças Speed e publicação de uma Serving reconciliada.

### 10.1. Componentes da arquitetura

**Batch**

O caminho Batch recalcula as contagens da publicação completa por ano, mês estatístico, distrito e tipo de ocorrência.

Cada mês identificado gera uma grade com 96 distritos e duas categorias de crime.

As combinações sem ocorrências recebem contagem zero, mantendo a comparabilidade entre publicações.

**Speed**

O caminho Speed compara duas versões da fonte utilizando multiplicidades de hashes de conteúdo.

Essa decisão evita assumir incorretamente que o número do boletim de ocorrência representa uma chave única global.

O mecanismo identifica inclusões, exclusões e alterações, preservando a multiplicidade dos registros.

**Serving**

A Serving recebe os resultados reconciliados, verificando a identidade:

`Batch anterior + Speed = Batch atual`

Somente após a validação e a persistência da Serving o controle da versão vigente é atualizado.

A atualização do apontador por último reduz o risco de declarar uma publicação concluída antes de seu conteúdo estar disponível.

O caminho Speed implementado utiliza diferenças calculadas entre republicações completas da SSP. Ele não corresponde a um serviço de streaming contínuo de eventos em tempo real.

Essa característica é compatível com a disponibilização da fonte por arquivos periódicos.

### 10.2. Objetos físicos

| Componente | Objeto |
|---|---|
| Bronze | `workspace.bronze.ssp_ingestao_v2` |
| Staging | `workspace.bronze.atlas_sampa_ssp_stage_v2` |
| Silver privada | `workspace.silver.atlas_sampa_ssp_v2` |
| Batch | `workspace.observability.atlas_sampa_ssp_batch_v1` |
| Speed | `workspace.observability.atlas_sampa_ssp_speed_v1` |
| Serving | `workspace.observability.atlas_sampa_ssp_serving_v1` |
| Controle de publicação | `workspace.observability.atlas_sampa_ssp_publication_v1` |

O processamento seleciona registros de roubo e furto referentes ao município de São Paulo e utiliza associação espacial aos 96 distritos oficiais.

Registros que não possuem correspondência distrital válida permanecem auditáveis, mas não são somados arbitrariamente às contagens territoriais.

### 10.3. Resultado da execução

A primeira execução real da arquitetura Lambda foi concluída com sucesso no Databricks Serverless.

A auditoria da publicação identificou:

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
| **Resultado** | **APROVADO** |

Esses resultados comprovam a consistência da publicação auditada.

Não significam que futuras republicações manterão obrigatoriamente o mesmo layout, nem substituem testes de novos ciclos de atualização.

### 10.4. Por que a Lambda permanece desacoplada da Gold

A separação entre a arquitetura Lambda e a Gold principal é uma **decisão de governança e de controle do ciclo de vida dos dados**.

O Atlas Sampa não foi concebido como um sistema de monitoramento em tempo real. Sua proposta é disponibilizar fotografias territoriais consistentes e reproduzíveis para análises comparativas.

As fontes que alimentam o produto possuem diferentes cadências de atualização.

Dados censitários possuem ciclos longos de revisão, indicadores urbanos podem ser alterados conforme atualizações administrativas e registros criminais podem receber novas publicações mensalmente.

Entretanto, novas publicações não precisam necessariamente resultar em uma nova versão do produto.

Atualizar todos os componentes sempre que uma fonte for modificada poderia gerar reprocessamentos desnecessários, maior consumo computacional e mudanças frequentes nos resultados apresentados ao usuário.

Mais importante, uma atualização isolada poderia introduzir inconsistências entre períodos estatísticos, indicadores normalizados, agrupamentos territoriais e rankings personalizados.

A arquitetura foi, portanto, organizada em duas responsabilidades independentes.

A primeira é **manter as publicações da fonte atualizadas e auditáveis**.

A segunda é **decidir quando uma nova versão dos dados deve ser incorporada ao produto analítico**.

A Lambda atende à primeira responsabilidade, enquanto a Gold e os consumidores seguem um processo de publicação controlado.

Essa distinção permite processar novas informações sem alterar silenciosamente um snapshot já homologado.

### 10.5. Frequência da fonte e relevância analítica

A atualização de uma fonte não implica necessariamente uma alteração relevante nos resultados estatísticos do produto.

Por exemplo, uma nova publicação da SSP pode incluir milhares de ocorrências sem modificar substancialmente a ordenação relativa dos distritos.

Entretanto, essa estabilidade não pode ser presumida.

O impacto depende da distribuição territorial dos novos registros, dos indicadores utilizados e da sensibilidade dos modelos.

No caso do Atlas Sampa, o K-Means K9 apresentou separação limitada e estabilidade moderada. Portanto, alterações relativamente pequenas em determinadas variáveis podem afetar classificações de distritos próximos às fronteiras dos clusters.

Por essa razão, não consideramos correto afirmar que atualizações frequentes seriam necessariamente estatisticamente irrelevantes.

A decisão técnica é diferente: **uma nova publicação deve ser avaliada antes de provocar alterações nos modelos e produtos analíticos**.

Uma política de promoção orientada por impacto pode considerar mudanças nas taxas, posições relativas dos distritos, composição dos clusters e consistência temporal.

Esses critérios representam a diretriz de governança para futuras promoções e não devem ser confundidos com um mecanismo automático de avaliação de impacto já implementado.

### 10.6. Preservação da consistência temporal

A publicação homologada da Lambda contém nove meses estatísticos de 2026.

Alguns indicadores criminais utilizados anteriormente na Gold possuem janelas de referência de doze meses.

Substituir diretamente esses indicadores por contagens referentes a nove meses produziria uma comparação temporal incompatível.

Além disso, a Gold, o Star Schema, os resultados do Machine Learning e o Consumer V2 possuem versões e contratos identificados por hashes.

A atualização de uma fonte relevante para esses componentes exige avaliar as consequências sobre os dados derivados.

Por esse motivo, a Serving da Lambda não substitui automaticamente os dados da Gold.

A promoção exige uma decisão específica de publicação, com validação temporal, reconstrução dos componentes afetados e geração de novos snapshots quando necessário.

### 10.7. Política de execução sob demanda

O Job `atlas-sampa-ssp-lambda` possui configuração de execução mensal para o dia 10, às 10h, no fuso `America/Sao_Paulo`.

Entretanto, seu agendamento permanece **PAUSED**.

Essa condição é intencional.

A coleta e o processamento podem ser iniciados manualmente quando houver necessidade de verificar uma nova publicação da fonte.

A decisão reduz processamento desnecessário e permite controlar o consumo de recursos em um ambiente de desenvolvimento.

O fato de o Job possuir uma configuração de agendamento não significa que a aplicação esteja executando atualizações automáticas.

Da mesma forma, a execução manual da Lambda não autoriza a alteração do produto analítico.

O código da arquitetura Lambda, suas regras de validação e o procedimento operacional estão documentados em [LAMBDA.md](barrioiq_pipeline/atlas_sampa/ssp/LAMBDA.md).

## 11. Governança, qualidade e observabilidade

A governança do Atlas Sampa foi construída para preservar rastreabilidade, consistência e clareza sobre as limitações dos indicadores.

Cada camada possui contratos específicos de estrutura, granularidade, tipos, chaves e qualidade.

Os processos validam cardinalidade, campos obrigatórios, unicidade, coordenadas, intervalos numéricos e consistência entre fontes e destinos.

Quando uma condição obrigatória não é atendida, os processos são interrompidos em vez de produzir silenciosamente resultados inconsistentes.

### 11.1. Versionamento e reprodutibilidade

O Delta Lake preserva o histórico técnico das tabelas, enquanto hashes SHA256 permitem identificar conteúdos e snapshots.

A combinação desses mecanismos oferece rastreabilidade entre versões dos dados e resultados analíticos.

Os modelos de Machine Learning e os consumidores utilizam identificadores de snapshot explícitos.

Essa decisão evita que a atualização de uma tabela seja interpretada automaticamente como autorização para substituir classificações ou indicadores anteriores.

O versionamento também permite preservar evidências de resultados já apresentados.

### 11.2. Contratos e catálogo de dados

O Unity Catalog é utilizado para organizar objetos, permissões e metadados técnicos.

A Gold possui documentação de suas 254 colunas, incluindo origem, unidade, descrição e limitações.

Os contratos distinguem contagens absolutas, taxas por população, índices normalizados e valores descritivos.

Essa distinção evita operações analíticas inadequadas, como somar taxas de diferentes distritos ou interpretar índices relativos como quantidades físicas.

A documentação também registra que diferentes indicadores podem representar períodos estatísticos distintos.

### 11.3. Data Quality

A qualidade é verificada ao longo das camadas.

Na ingestão, são aplicadas validações de estrutura, conteúdo e versões dos arquivos.

Na Silver, são verificadas tipagem, consistência territorial e correspondências geográficas.

Na Gold, são validados schema, cardinalidade, chaves e integridade dos indicadores.

Nos produtos dimensionais e consumidores, os contratos verificam a compatibilidade com os snapshots de origem.

Na Lambda, a reconciliação entre Batch, Speed e Serving funciona como uma validação adicional de consistência.

Essas verificações não eliminam todas as limitações das fontes, mas tornam explícitas as condições necessárias para aceitar os resultados produzidos.

### 11.4. Observabilidade

A observabilidade é implementada em diferentes componentes da plataforma.

Os scripts produzem mensagens e eventos estruturados, permitindo identificar etapas executadas e falhas.

Os Jobs do Databricks mantêm histórico de execução e resultados.

O GitHub Actions registra testes, validações e implantações.

O schema `workspace.observability` contém estruturas destinadas a auditoria e aos resultados da arquitetura Lambda.

Também existem workflows de coleta de métricas operacionais e evidências de entrega.

A observabilidade adotada é compatível com o ambiente de desenvolvimento e com o caráter controlado das execuções.

Ela não deve ser confundida com monitoramento contínuo de uma operação de produção.

Da mesma forma, métricas DORA de produção não são apresentadas como plenamente mensuradas na ausência de uma operação produtiva instrumentada.

### 11.5. Segurança e uso responsável

O processamento utiliza dados públicos, mas isso não elimina a necessidade de avaliar riscos de exposição e interpretação.

A aplicação web trabalha com indicadores agregados por distrito, sem disponibilizar registros detalhados de boletins de ocorrência ou endereços individuais.

O pipeline Lambda evita incluir identificadores sensíveis e informações detalhadas de registros em seus logs.

O acesso aos dados é controlado por permissões do ambiente Databricks.

O campo `publicacao_autorizada` também funciona como controle lógico do produto, mas não substitui as permissões efetivas de acesso.

A publicação pública depende de avaliação específica de governança.

## 12. CI/CD e infraestrutura como código

O projeto utiliza GitHub Actions para executar validações de código e contratos antes da integração de alterações à branch `main`.

Os workflows contemplam componentes de engenharia de dados, qualidade, Machine Learning, modelagem, aplicação web e infraestrutura.

O objetivo é detectar problemas de compatibilidade antes que mudanças sejam disponibilizadas no ambiente Databricks.

### 12.1. Databricks Asset Bundles

As definições dos Jobs são mantidas em arquivos versionados no repositório.

O Databricks Asset Bundles permite validar e implantar essas configurações de maneira controlada.

Essa abordagem reduz divergências entre código revisado e recursos existentes no workspace.

O fluxo principal utiliza verificações antes de atualizar Jobs já implantados.

A arquitetura Lambda possui um Bundle independente e um workflow próprio de deploy manual.

Essa separação foi adotada para impedir que alterações específicas da SSP modifiquem inadvertidamente componentes do pipeline principal.

O deploy de código não implica execução automática dos dados.

### 12.2. Terraform

A infraestrutura como código utiliza Terraform para declarar recursos do ambiente Databricks.

O repositório contempla schemas das camadas Bronze, Silver e Gold, o schema Observability e o Volume Raw gerenciado.

A escolha do Terraform permite manter a descrição da infraestrutura sob controle de versão e reduzir dependências de configurações realizadas exclusivamente pela interface.

O workflow de CI executa verificações de formatação, inicialização sem backend remoto e validação da configuração.

Esses testes comprovam a consistência declarativa dos arquivos Terraform, mas não demonstram isoladamente que cada recurso foi efetivamente criado por uma execução de `terraform apply`.

A comprovação de provisionamento deve considerar o estado registrado no HCP Terraform e a correspondência com os recursos existentes no Databricks.

### 12.3. Controle operacional

O projeto separa três atividades: validar alterações, implantar código e executar processamento.

Essa divisão permite aprovar mudanças de forma independente e evita que um commit provoque automaticamente uma carga de dados potencialmente custosa.

A mesma lógica se aplica à atualização do produto analítico.

Uma nova versão da fonte pode ser processada e auditada sem ser imediatamente promovida ao Consumer.

Essa separação é especialmente relevante para preservar os resultados de experimentos e demonstrações realizadas com snapshots identificados.

## 13. Como reproduzir e validar

A reprodução do projeto possui dois níveis.

O primeiro utiliza testes automatizados com dados sintéticos, apropriados para verificar contratos e comportamento do código.

O segundo utiliza as tabelas reais no Databricks, permitindo validar materializações, cardinalidade, indicadores e consistência dos resultados.

Os testes sintéticos não substituem a auditoria dos dados reais.

### 13.1. Testes de engenharia e Machine Learning

```bash
git clone https://github.com/DCosso/bairroiq.git
cd bairroiq

python -m pip install -r barrioiq_pipeline/requirements-ml.txt

python -m unittest discover -s tests -p 'test_*.py' -v
```

Alguns testes possuem dependências específicas, documentadas nos workflows do GitHub Actions.

### 13.2. Aplicação demonstrativa

A aplicação Streamlit pode ser executada localmente utilizando dados demonstrativos.

```powershell
cd streamlit/bairroiq-streamlit-v2

python -m pip install -r requirements-dev.txt

$env:BAIRROIQ_DATA_PROVIDER = "sample"

python -m streamlit run app.py
```

O modo `sample` não representa o Consumer V2 materializado no Databricks.

Para a execução com dados reais é necessário configurar o provedor Databricks, as permissões de leitura e o ambiente de demonstração privada.

### 13.3. Validação da Serving da SSP

A versão vigente da publicação pode ser consultada por meio do controle de publicação.

```sql
SELECT
    p.ano,
    COUNT(s.CD_DIST) AS linhas,
    COUNT(DISTINCT s.CD_DIST) AS distritos,
    COUNT(DISTINCT s.mes) AS meses,
    COUNT(DISTINCT s.tipo) AS tipos,
    SUM(s.quantidade) AS ocorrencias
FROM workspace.observability.atlas_sampa_ssp_publication_v1 p
JOIN workspace.observability.atlas_sampa_ssp_serving_v1 s
    ON s.source_sha256 = p.source_sha256
   AND s.ano = p.ano
GROUP BY p.ano
ORDER BY p.ano DESC;
```

O controle de publicação identifica explicitamente a versão vigente, evitando inferir atualidade a partir da ordenação de hashes ou da data de gravação.

A auditoria completa da reconciliação deve verificar as contagens por chave entre Batch anterior, Speed, Batch atual e Serving.

## 14. Organização do repositório

```text
bairroiq/
|
|  README.md
|
|  .github/
|      workflows/
|          Testes e processos de CI/CD
|
|  infra/
|      Definições Terraform
|
|  EDA/
|      Análises exploratórias
|
|  notebooks/
|      Experimentos e validações
|
|  barrioiq_pipeline/
|      Runners de engenharia
|      SQL e transformações
|      Databricks Asset Bundles
|
|      atlas_sampa/
|          ssp/
|              Coletor versionado
|              Batch, Speed e Serving
|
|      resources/
|          Definições dos Jobs
|
|  docs/
|      arquitetura/
|      consumo/
|      governanca/
|      ml/
|      modelagem/
|      dicionario_gold_distritos_wide.md
|      dicionario_gold_distritos_wide.json
|
|  streamlit/
|      bairroiq-streamlit-v2/
|          Aplicação Atlas Sampa
|          Integração Databricks
|          Testes da interface
|
|  tests/
|      Testes automatizados
```

### Documentação técnica

- [Dicionário completo da Gold](docs/dicionario_gold_distritos_wide.md)
- [Contrato estruturado da Gold](docs/dicionario_gold_distritos_wide.json)
- [Metodologia de Machine Learning](docs/ml/metodologia_catalogo_perfis_v3.md)
- [Comparação entre K-Means e Ward](docs/ml/metodologia_comparacao.md)
- [Revisão semântica dos perfis](docs/governanca/encerramento_auditoria_semantica_v3.md)
- [Contrato do Star Schema](docs/modelagem/star_schema_v1_delta_contrato.md)
- [Auditoria do Consumer V2](docs/consumo/BairroIQ_Frontend_V2_Auditoria_Leitura.sql)
- [Aplicação Streamlit V2](streamlit/bairroiq-streamlit-v2/README.md)
- [Arquitetura Lambda SSP](barrioiq_pipeline/atlas_sampa/ssp/LAMBDA.md)

## 15. Responsabilidades técnicas e colaboração

O desenvolvimento do Atlas Sampa reúne competências de engenharia de dados, Analytics, ciência de dados, desenvolvimento de aplicações e DataOps.

A **engenharia de dados** responde pela ingestão, padronização, modelagem, versionamento e qualidade das informações.

A área de **Analytics** define indicadores, regras de cálculo, unidades e critérios de interpretação, além de produzir análises comparativas relevantes para o produto.

A **ciência de dados** atua na seleção de variáveis, preparação dos dados, desenvolvimento dos experimentos de Machine Learning e avaliação das classificações territoriais.

O desenvolvimento de **produto e frontend** transforma os resultados analíticos em recursos de navegação, visualização e personalização compreensíveis.

As atividades de **DataOps e plataforma** contemplam versionamento, testes automatizados, infraestrutura, implantação, segurança e observabilidade.

Essas responsabilidades não exigem necessariamente um profissional exclusivo para cada função.

A utilização de contratos explícitos entre os componentes facilita a colaboração, a revisão cruzada e a manutenção de consistência entre dados e experiência do usuário.

## 16. Limitações e critérios de uso

O Atlas Sampa foi validado como um MVP privado de exploração territorial.

A plataforma não oferece previsão de criminalidade, avaliação individual de imóveis, garantia de acesso a serviços ou determinação de qual região é ideal para determinada pessoa.

Os indicadores representam informações disponíveis nas fontes utilizadas e possuem limitações de cobertura, período e metodologia.

A cobertura imobiliária documentada é parcial, e determinados indicadores socioeconômicos utilizam referências históricas.

Os nove perfis territoriais representam agrupamentos exploratórios, não classificações definitivas da qualidade dos distritos.

Os resultados de Machine Learning também apresentam limitações de separação e estabilidade, que devem ser consideradas nas interpretações.

A arquitetura Lambda possui uma publicação real e reconciliada da SSP, mas não opera como streaming contínuo e não promove automaticamente seus resultados para a Gold.

Esse desacoplamento foi adotado para preservar a consistência dos snapshots e permitir que a incorporação de novas informações seja governada por critérios de qualidade, compatibilidade temporal e relevância analítica.

A política de atualização sob demanda não pressupõe que os indicadores sejam estatisticamente invariáveis.

Seu princípio é que **o processamento de uma nova versão e a decisão de publicar um novo produto analítico são eventos distintos**.

A primeira publicação Lambda foi homologada com zero divergências de reconciliação, e seu agendamento automático permanece pausado.

A disponibilização pública do aplicativo exige aprovação específica de governança, validação dos dados expostos e revisão das permissões de acesso.

O Atlas Sampa demonstra uma arquitetura de dados que combina integração multifuente, modelagem analítica, Machine Learning, governança e consumo interativo, preservando a rastreabilidade das decisões técnicas e a separação entre atualização operacional e publicação do produto.
