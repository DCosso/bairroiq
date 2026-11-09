# Atlas Sampa | Atualização mensal SSP-SP | Lambda piloto

Nome comercial: **Atlas Sampa**. O repositório técnico continua **bairroiq**.

## Escopo

Este módulo é **um pipeline separado para validação acadêmica e homologação privada**.
Não altera o snapshot homologado do Atlas Sampa, nenhuma tabela `workspace.gold.*`,
nem `workspace.silver.ssp_ocorrencias[_distrito]` ou `workspace.bronze.dados_criminais_unificado_ssp`.
Os dados usados pela aplicação continuam congelados até que uma publicação
separada seja planejada e autorizada.

## Fluxo

1. `collector.py`: solicita o Excel anual diretamente à SSP por HTTPS, valida as
   abas e 30 colunas, grava `/Volumes/workspace/bronze/raw/ssp/versions/{year}/{sha}.xlsx`.
   Arquivo igual = mesmo SHA-256, sem duplicação na Raw.
2. `pipeline.py`: verifica a Bronze paralela `workspace.bronze.ssp_ingestao_v2`
   (já existe com 35 campos) e ingere snapshots ainda não presentes, usando
   staging própria `workspace.bronze.atlas_sampa_ssp_stage_v2`.
   Cada registro é identificado na versão pela combinação SHA do arquivo + aba + linha.
   **Essa chave não é a identidade da ocorrência entre versões**.
3. Silver privada `workspace.silver.atlas_sampa_ssp_v2`: seleciona ocorrências
   `Furto (art. 155)` ou `Roubo (art. 157)` no município IBGE 3550308,
   valida coordenadas e associa à malha dos 96 distritos oficiais por `within`.
   Registros sem distrito são preservados com `CD_DIST=NULL` e auditados,
   mas não entram nas contagens por distrito.
4. Batch `workspace.observability.atlas_sampa_ssp_batch_v1`: consolida
   a publicação completa por ano/mês estatístico, distrito e tipo de crime.
   Para todos os meses identificados, produz 96 × 2 combinações.
5. Speed `workspace.observability.atlas_sampa_ssp_speed_v1`: compara duas
   publicações com a **multiplicidade de hashes de linha**. Detecta inclusões,
   exclusões e alterações como inclusão + exclusão; acumula diferenças mensais
   por distrito. Não supõe que `NUM_BO` seja único.
6. Serving `workspace.observability.atlas_sampa_ssp_serving_v1`: recebe a
   versão reconciliada somente se `batch_antigo + speed = batch_atual`
   para cada grupo. O apontador `workspace.observability.atlas_sampa_ssp_publication_v1`
   é atualizado **por último**, após a gravação de toda a serving.

Esse piloto tem dois caminhos lógicos (reprocessamento batch e delta incremental)
com reconciliação na consulta. **Não é streaming de eventos em tempo real**.
O fornecedor republica arquivos completos; a atualização configurada é mensal.

## Limites e pré-requisitos

- Databricks com Unity Catalog, PySpark Serverless, rede HTTPS SSP e permissão
  de escrita em Volume Raw, Bronze paralela, Silver nova e schema Observability.
- A tabela `workspace.bronze.ssp_ingestao_v2` deve existir com **35 campos**,
  compatíveis com a staging de homologação já validada (814.900 registros, 2026).
- Shapefile oficial já disponível em
  `/Volumes/workspace/bronze/raw/ibge/malha_distritos_2022/shapefile/SP_distritos_CD2022.shp`.
- Software no Job: `openpyxl`, `geopandas`, `numpy`, `pandas`, `pyarrow`, com
  versões fixadas no contrato do recurso do Job.
- Por segurança, o código bloqueia mudanças de contrato, cardinalidade
  inesperada ou discordância da reconciliação. Uma execução interrompida no meio
  de uma Silver parcial pode exigir limpeza controlada somente das tabelas
  *novas*, antes de repetir. Não apagar tabelas oficiais.
- `record_sha256` identifica **conteúdo**, não necessariamente um BO único.
- Indicadores são contagens, **não taxas por 1.000 habitantes**; não confundir
  com as pontuações do aplicativo. Ausências de geolocalização são auditadas.
- Não publicar registros detalhados ou endereços em frontends públicos.
- Não existe atualização automática da Gold oficial ou do Streamlit.

## Bundle isolado

Este diretório é um **bundle separado**, `atlas_sampa_ssp_lambda`, independente do
`barrioiq_pipeline/databricks.yml` existente. Isso evita alterar as regras de
segurança e as sete definições de Jobs do CD principal.

O Job `atlas-sampa-ssp-lambda` usa `max_concurrent_runs: 1`, sem retries,
com cron `0 0 10 10 * ?`, fuso `America/Sao_Paulo`, **PAUSED**.
No repositório, `.github/workflows/atlas-sampa-ssp-lambda-deploy.yml` é disparado
**manualmente**, somente a partir de `main`, e faz o deploy do Job pausado.
Não há execução automática de pipeline no GitHub Actions.

### Roteiro operacional recomendado

1. Enviar todos os arquivos desta entrega na branch
   `feature/atlas-sampa-lambda-ssp`, incluindo o `excel_reader.py` atualizado.
2. Confirmar `Atlas Sampa - SSP Lambda CI` verde; criar PR e integrar à `main`.
3. Na página Actions, abrir **Atlas Sampa - SSP Lambda Manual Deploy**,
   escolher `main` e **Run workflow**. É um deploy isolado e com cron pausado.
4. No Databricks, localizar o Job com nome contendo `atlas-sampa-ssp-lambda`,
   validar que o agendamento continua **PAUSED**, e usar **Run now** para uma
   primeira execução controlada, monitorando logs e custos.
5. Verificar as tabelas privadas e a reconciliação antes de ativar `Resume`.
   O código inclui `--bootstrap-legacy` para tratar a versão original do Excel
   (outubro/2026) como linha de base do primeiro ciclo de 2026, se ainda não
   houver publicação desse ano. Após a primeira publicação, o bootstrap é ignorado.
6. Somente após homologação técnica, ativar o agendamento mensal **dia 10,
   10h em São Paulo**. Em 2027, revalidar o contrato anual da SSP.

### SQL de validação (somente leitura)

```sql
SELECT ano, source_sha256, publicado_em_utc
FROM workspace.observability.atlas_sampa_ssp_publication_v1
ORDER BY ano DESC;

SELECT source_sha256, ano, mes, tipo,
       SUM(quantidade) AS ocorrencias_em_distritos
FROM workspace.observability.atlas_sampa_ssp_serving_v1
GROUP BY source_sha256, ano, mes, tipo
ORDER BY ano, mes, tipo;

SELECT source_sha256, previous_sha256,
       SUM(adicionados) AS adicoes_sp,
       SUM(removidos) AS remocoes_sp
FROM workspace.observability.atlas_sampa_ssp_speed_v1
GROUP BY source_sha256, previous_sha256;
```

## Qualidade e observabilidade

`pipeline.py` emite eventos JSON sem números de BO nem endereço. Valida
SHA da fonte, 30/35 campos, unicidade de linha por snapshot, contagem por
arquivo, associação espacial, 96 distritos, grade 96×2×mês e reconciliação
algébrica Batch + Speed = Serving. As tabelas Delta preservam histórico dos
snapshots; a publicação vigente é definida pelo apontador, não pelo maior hash.

O job e todo o pipeline só devem ser usados por operadores autorizados.
