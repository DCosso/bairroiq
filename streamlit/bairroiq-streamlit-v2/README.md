# Atlas Sampa

Aplicação Streamlit para explorar distritos de São Paulo, montar cenários,
comparar indicadores e consultar perfis urbanos. Os dados demonstrativos são
usados por padrão; no Databricks Apps, o app consulta os dados publicados no
Unity Catalog.

## Executar localmente

No PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abra `http://localhost:8501`. Para verificar o código e rodar os testes:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check app.py bairroiq pages tests
python -m unittest discover -s tests
```

## Publicar no Databricks Apps

O `app.yaml` já configura a inicialização do Streamlit e a tabela
`workspace.gold.bairroiq_frontend_v1`. Faça deploy desta pasta mantendo
`app.yaml`, `app.py` e `requirements.txt` na raiz publicada.

1. Adicione ao app um recurso **SQL Warehouse** com a chave `sql-warehouse` e
   permissão **Can use**.
2. Conceda à identidade de serviço do app `USE CATALOG` no catálogo `workspace`,
   `USE SCHEMA` no schema `gold` e `SELECT` na tabela.
3. O app autentica pelo OAuth do Databricks Apps. Não configure token pessoal
   no deployment.

O adaptador está em `bairroiq/databricks.py`. Para executar localmente usando
Databricks, configure `BAIRROIQ_DATA_PROVIDER=databricks`, host e HTTP path em
`.streamlit/secrets.toml` (use o arquivo de exemplo como referência). O provedor
local padrão é `sample`; credenciais não devem ser publicadas.

### Dados usados pelo app

Somente linhas com `publicacao_autorizada = true` são consultadas. O adaptador
seleciona o maior `snapshot_id` publicado, portanto esse identificador deve
ordenar os snapshots por recência. Se isso não for verdade, publique uma coluna
de data/hora e ajuste o critério de seleção.

| Coluna no Databricks | Campo interno | Uso |
| --- | --- | --- |
| `distrito` | `neighborhood` | Nome exibido nas telas e filtros |
| `cd_dist` | `district_code` | Código de referência |
| `latitude`, `longitude` | Mesmos nomes | Coordenadas do distrito |
| `empregos` | `formal_jobs_score` | Pontuação de emprego |
| `seguranca` | `safety_score` | Pontuação de segurança |
| `roubos` | `robbery_index` | Índice exibido nos detalhes |
| `mobilidade` | `mobility_score` | Pontuação de mobilidade |
| `perfil_id`, `cluster`, `tipo_territorio` | Mesmos nomes | Metadados para uso futuro |
| `snapshot_id`, `publicacao_autorizada` | Filtro de publicação | Escolha e autorização dos dados |

Confirme com quem publica a tabela a escala e a unidade de `empregos`,
`seguranca`, `mobilidade` e `roubos`, para que filtros e rótulos tenham a mesma
interpretação. Iluminação LED, arborização e custo de vida não existem nessa
tabela e aparecem como indisponíveis, sem valores inventados. O histórico
também fica vazio até existir uma fonte com data/período e valores históricos.

Os polígonos do mapa ficam em `bairroiq/district_boundaries.geojson`. A base de
demonstração contém limites de sete distritos; outros distritos só aparecem no
mapa depois que seus polígonos forem adicionados. Sem polígono, continuam
disponíveis nas listas e nos cálculos. Butantã, Lapa e Tatuapé usam formas
explicitamente ilustrativas nos dados demonstrativos.

## Organização do código

- `app.py` configura a navegação; `pages/` contém as páginas Streamlit.
- `bairroiq/provider.py` seleciona um provedor pelo `DataProviderFactory`;
  `sample_data.py` e `databricks.py` implementam as fontes de dados.
- `bairroiq/scoring.py` concentra as regras no `ScenarioScoringService`.
- `bairroiq/map_data.py` reúne operações cartográficas no
  `DistrictMapService`; as páginas permanecem como pontos de entrada da
  interface Streamlit.
- `bairroiq/ui.py` contém os componentes visuais compartilhados.
