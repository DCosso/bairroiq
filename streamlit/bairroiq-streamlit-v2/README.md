Atlas Sampa
Aplicação web em Streamlit para explorar e comparar os 96 distritos administrativos oficiais de São Paulo a partir do produto de dados BairroIQ. A interface mantém a identidade visual Atlas Sampa e integra o Consumer V2 materializado no Databricks.
Status em 08/11/2026: MVP funcional homologado em ambiente privado, com deploy da branch `main` e testes de navegação concluídos. A homologação comprova o funcionamento da experiência demonstrativa, não a aprovação para publicação pública nem a exatidão absoluta de todos os indicadores.
Funcionalidades do MVP
Tela	Funcionalidade validada
Personalizar cenário	Configurar pesos para verde e lazer, segurança, mobilidade e serviços públicos
Explorar / Mapa	Visualizar os limites dos 96 distritos oficiais, aplicar filtros e consultar o Top 10 conforme o cenário
Comparar regiões	Selecionar distritos e comparar visualmente os indicadores disponíveis
Perfis Urbanos	Consultar os perfis territoriais dos distritos selecionados, densidade e resultados de indicadores
Fontes	Conhecer a origem geral dos dados e os limites de interpretação
O ranking personalizado é calculado pela interface a partir de quatro dimensões de 0 a 100. Empregos formais, densidade e taxas de roubos são apresentados como informações complementares, sem compor os pesos personalizados. Os nove perfis são resultados exploratórios de K-Means (K=9), previamente calculados na camada de dados, e não são recalculados no navegador.
Os perfis são rótulos descritivos de grupos com características semelhantes. Nenhum perfil é considerado o melhor por definição. O produto não oferece previsão de segurança individual, garantia de qualidade de vida ou recomendação residencial homologada.
Arquitetura resumida
```text
Fontes públicas e referências territoriais
                 |
          Bronze / Silver
                 |
         Gold distritos_wide
             96 distritos
                 |
       ML exploratório K=9
         Star Schema Delta
                 |
     Consumer V2 físico auditado
 workspace.gold.bairroiq_frontend_v2
          96 linhas, 20 campos
                 |
       Databricks SQL Warehouse
                 |
         Databricks Apps
      Streamlit | Atlas Sampa
```
Os polígonos oficiais dos 96 distritos são disponibilizados no arquivo `bairroiq/district_boundaries.geojson`. O Consumer V2 contém os atributos que alimentam as telas. O snapshot está congelado e em estado candidato. O aplicativo consulta os dados em modo somente leitura.
Contrato do Consumer V2
Tabela: `workspace.gold.bairroiq_frontend_v2`.
Granularidade: uma linha por distrito no snapshot selecionado.
Distritos: 96, com `cd_dist` e `neighborhood` únicos.
Perfis: 9, identificados por `perfil_id` e descritos por `cluster`.
Total de campos físicos: 20, incluindo quatro metadados de auditoria.
Controle de publicação: `publicacao_autorizada = false` no snapshot homologado privadamente.
Indicadores personalizados: `green_leisure_score`, `safety_score`, `mobility_score` e `public_services_score`.
Indicadores complementares: `formal_jobs_score`, `densidade_hab_km2` e `robberies_per_1000`.
Georreferenciamento: `latitude`, `longitude` e geometria GeoJSON dos distritos.
Auditoria: `versao_contrato`, `payload_sha256`, `sql_sha256` e `materializado_em_utc`.
O adaptador `bairroiq/databricks.py` lê a tabela, valida colunas, cardinalidade e integridade, e verifica a assinatura do conteúdo antes de entregá-lo à interface. Não reprocessa nem altera a Gold. O identificador do snapshot é fixado no contrato `bairroiq/consumer_v2.py`, sem inferir recência pela ordem alfabética do ID.
Cuidados com a interpretação
Os dados provêm de fontes e períodos de referência diferentes. Por exemplo, os empregos formais utilizados nessa versão têm referência histórica de 2021. Os índices de segurança não são probabilidades de vitimização; taxas de registros também não medem integralmente a criminalidade observada. Os resultados servem à exploração e à demonstração funcional do produto.
O MVP não dispõe de indicador validado de custo de moradia. O score de verde e lazer não equivale a uma medida de arborização de ruas. Não há histórico temporal de indicadores na interface, já que o Consumer V2 fornece um snapshot, e não uma série histórica.
Execução local com dados demonstrativos
Pré-requisitos: Python 3.12 e acesso à pasta `streamlit/bairroiq-streamlit-v2` do repositório.
No PowerShell:
```powershell
cd streamlit/bairroiq-streamlit-v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:BAIRROIQ_DATA_PROVIDER = "sample"
python -m streamlit run app.py
```
Abra `http://localhost:8501`. O modo `sample` utiliza registros demonstrativos e não representa uma validação dos 96 distritos reais nem da tabela Databricks.
Para executar os testes offline:
```powershell
python -m pip install -r requirements-dev.txt
python -m compileall -q app.py bairroiq pages tests
python -m unittest discover -s tests -p "test_*.py" -v
```
O workflow `.github/workflows/streamlit-v2-ci.yml` automatiza verificação sintática, testes unitários/contratuais e checagem da configuração de prévia interna. Esses testes não substituem a homologação visual no Databricks Apps.
Demonstração privada no Databricks Apps
A implantação validada utiliza:
Recurso	Configuração
Aplicativo	`bairroiq-v2-homolog-2`
Repositório	`DCosso/bairroiq`
Branch implantada	`main`
Commit homologado	`84e5918a820c8b8cb67fc7c906aa34e858217c23`
Caminho de código	`streamlit/bairroiq-streamlit-v2`
Provedor	`BAIRROIQ_DATA_PROVIDER=databricks`
SQL Warehouse	Recurso `sql-warehouse`, permissão `CAN_USE`
Tabela Delta	Recurso `consumer-v2`, permissão `SELECT`
Prévia interna	`BAIRROIQ_INTERNAL_PREVIEW=true`, exclusivamente em ambiente privado com acesso restrito
O arquivo `app.yaml` define o comando de inicialização, o SQL Warehouse e a tabela V2. A configuração de prévia não está habilitada no `app.yaml` versionado e só pode ser utilizada em uma implantação restrita e autorizada. A flag não substitui autenticação, permissões ou aprovação de publicação.
A identidade de serviço do aplicativo precisa das permissões adequadas no Unity Catalog (`USE CATALOG`, `USE SCHEMA`, `SELECT`) e no SQL Warehouse (`CAN_USE`). A implantação utiliza a autenticação da plataforma; não é necessário versionar tokens pessoais.
Iniciar, implantar e interromper
Exemplo usado na homologação, para um operador com CLI Databricks configurada e perfil `BAIRROIQ_HOMOLOG`:
```powershell
databricks apps start bairroiq-v2-homolog-2 --profile BAIRROIQ_HOMOLOG

databricks apps deploy bairroiq-v2-homolog-2 --json "@$env:USERPROFILE\Downloads\bairroiq-main-deploy.json" --profile BAIRROIQ_HOMOLOG

databricks apps stop bairroiq-v2-homolog-2 --profile BAIRROIQ_HOMOLOG
```
O arquivo `bairroiq-main-deploy.json` é local ao operador, foi usado no processo de homologação e não faz parte do repositório. Não publique arquivos com segredos, credenciais ou configurações sensíveis. Após a validação, interrompa o aplicativo. O SQL Warehouse possui ciclo de vida e cobrança separados, que devem ser verificados na plataforma.
Roteiro de validação funcional
Entrar no aplicativo privado com uma conta autorizada.
Em Explorar / Mapa, visualizar os 96 distritos sem seleção prévia, conferir o Top 10 e alterar filtros.
Em Comparar regiões, selecionar três distritos e confirmar a atualização dos gráficos.
Em Perfis Urbanos, selecionar distritos e conferir nome do perfil, densidade e indicadores.
Conferir a página Fontes e as ressalvas de interpretação.
Encerrar a demonstração e parar o aplicativo para evitar consumo desnecessário.
Na homologação de 08/11/2026 foram confirmados o deploy do commit citado na `main`, o mapa, o ranking, os filtros, a comparação e os perfis. O aplicativo foi desligado após o teste.
Organização do código
```text
streamlit/bairroiq-streamlit-v2/
|-- app.py                      Navegação Streamlit
|-- app.yaml                    Inicialização Databricks Apps
|-- requirements.txt            Dependências
|-- bairroiq/
|   |-- consumer_v2.py          Contrato do snapshot
|   |-- databricks.py           Leitura e validação física
|   |-- provider.py             Seleção e cache do provedor
|   |-- scoring.py              Personalização do cenário
|   |-- explore_logic.py        Consistência de filtros e ranking
|   |-- comparison_v2.py       Apoio à comparação
|   |-- map_data.py             Geometria e filtros do mapa
|   |-- ux_labels.py            Nomes de perfis
|   `-- district_boundaries.geojson
|-- pages/                     Telas de navegação
`-- tests/                     Testes offline
```
Limites de publicação
MVP homologado privadamente não é lançamento público. A tabela utilizada mantém `publicacao_autorizada = false`. Qualquer exposição externa, ampliação de permissões ou mudança para ambiente público depende de decisão explícita de governança e revisão dos riscos de interpretação. A integração à branch `main` não modifica esse estado.
